import collections.abc
import itertools
import logging
import pathlib
import re
from enum import Enum
from functools import reduce
from typing import Any, Iterable, Optional, Union, cast

from .learnt_types import (
    LCollection,
    LearntType,
    LLiteral,
    LMapping,
    LMissingTypedDictKey,
    LNone,
    LTuple,
    LType,
    LTypedDict,
    LUnion,
)
from .subtyping import is_subtype, is_subtype_or_equal
from .typedef_generation import PythonVersion, generate_typedef_rhs, new_type_name
from .utils import group_and_process, to_json_path

logger = logging.getLogger(__name__)


class TypeLearner:
    def __init__(
        self,
        max_literal_type_size: int = 10,
        max_literal_string_length: int = 512,
        learn_typed_dicts: bool = True,
        max_typed_dict_size: int = 100,
        max_recursive_type_depth: int = 10,
        no_literal_patterns: Optional[list[str]] = None,
    ) -> None:
        self.learnt_type: Optional[LearntType] = None
        self.observed_values = 0
        self.max_literal_type_size = max_literal_type_size
        self.max_literl_string_length = max_literal_string_length
        self.max_typed_dict_size = max_typed_dict_size
        self.learn_typed_dicts = learn_typed_dicts
        self.max_recursive_type_depth = max_recursive_type_depth
        self.no_literal_patterns = [re.compile(patt) for patt in no_literal_patterns or []]

    def _learn_variable_type(self, var: Any, _path: Optional[list[Union[str, int]]] = None) -> LearntType:
        path = _path or []
        # simple basic types learning
        if var is None:
            return LNone()
        if isinstance(var, (int, str, bytes, bool, Enum)):
            json_path = to_json_path(path)
            if (
                self.max_literal_type_size > 0
                and not any(no_literal_pattern.match(json_path) for no_literal_pattern in self.no_literal_patterns)
                and not (isinstance(var, str) and len(var) > self.max_literl_string_length)
            ):
                return LLiteral(var)
            else:
                return LType(type(var))

        # parametrized types learning with recursion
        if len(path) > self.max_recursive_type_depth:
            return LType(type(var))
        if isinstance(var, tuple):
            return LTuple(
                item_types=[self._learn_variable_type(item, _path=path + [index]) for index, item in enumerate(var)]
            )
        if isinstance(var, collections.abc.Mapping):
            learnt_value_type_by_key: dict[Any, LearntType] = {
                k: self._learn_variable_type(v, _path=path + [k]) for k, v in var.items()
            }
            learnt_key_types = [self._learn_variable_type(k, _path=path + [k]) for k in learnt_value_type_by_key.keys()]
            if (
                self.learn_typed_dicts
                and isinstance(var, dict)
                and all(is_subtype_or_equal(kt, LType(str)) for kt in learnt_key_types)
            ):
                return LTypedDict(learnt_value_type_by_key)
            else:
                return LMapping(
                    mapping_type=type(var),
                    key_type=self._reduce_simplifying(learnt_key_types),
                    value_type=self._reduce_simplifying(learnt_value_type_by_key.values()),
                )
        if isinstance(var, collections.abc.Collection):
            learnt_item_types = [
                self._learn_variable_type(item, _path=path + [index]) for index, item in enumerate(var)
            ]
            return LCollection(
                type(var),
                item_type=self._reduce_simplifying(learnt_item_types),
            )

        # opaque type as a fallback
        return LType(type_=type(var))

    def _reduce_simplifying(self, lts: Iterable[LearntType]) -> LearntType:
        if not lts:
            return LUnion([])
        return reduce(lambda lt1, lt2: self._simplify_learnt_type(LUnion([lt1, lt2])), lts)

    def _simplify_learnt_type(self, lt: LearntType) -> LearntType:
        lt_prev = lt
        while True:

            # flattening union type (Union[Union[str, int], bytes] => Union[str, int, bytes])
            if isinstance(lt, LUnion):
                flat_members: list[LearntType] = []
                for member_type in lt.member_types:
                    if isinstance(member_type, LUnion):
                        flat_members.extend(member_type.member_types)
                    else:
                        flat_members.append(member_type)
                lt = LUnion(flat_members)

            # deduplicating union types (Union[str, str, int] => Union[str, int])
            if isinstance(lt, LUnion):
                # can't use set because there's no hashability guarantee
                dedup_member_types: list[LearntType] = []
                for member in lt.member_types:
                    if member not in dedup_member_types:
                        dedup_member_types.append(member)
                lt = LUnion(dedup_member_types)

            # replacing exhaustive bool literal union with bool type (Union[Literal[True], Literal[False], ...] -> Union[bool, ...])
            if isinstance(lt, LUnion):
                literal_true = LLiteral(True)
                literal_false = LLiteral(False)
                if literal_true in lt.member_types and literal_false in lt.member_types:
                    lt = LUnion(
                        [m for m in lt.member_types if m != literal_true and m != literal_false] + [LType(bool)]
                    )

            # generalizing too large unions of literals (Literal[1, 2, 3, ...] => int)
            if isinstance(lt, LUnion):
                literal_members: list[LLiteral] = []
                other_members: list[LearntType] = []
                for member in lt.member_types:
                    if isinstance(member, LLiteral):
                        literal_members.append(member)
                    else:
                        other_members.append(member)
                if len(literal_members) > self.max_literal_type_size:
                    simple_type_members = [LType(type(lm.value)) for lm in literal_members]
                    lt = self._simplify_learnt_type(LUnion(simple_type_members + other_members))

            # merge same-length tuples in a union (tuple[str, int] | tuple[float, bool] => tuple[str | float, int | bool])
            if isinstance(lt, LUnion):

                def generalize_same_length_tuples(lts: list[LearntType]) -> list[LearntType]:
                    if not lts or not all(isinstance(lt, LTuple) for lt in lts):
                        return lts
                    union_tuples = cast(list[LTuple], lts)
                    result_tuple = union_tuples[0]
                    for member in union_tuples:
                        for idx in range(len(result_tuple.item_types)):
                            result_tuple.item_types[idx] = self._simplify_learnt_type(
                                LUnion([result_tuple.item_types[idx], member.item_types[idx]])
                            )
                    return [result_tuple]

                lt = LUnion(
                    member_types=group_and_process(
                        lt.member_types,
                        group_key=lambda lt: len(lt.item_types) if isinstance(lt, LTuple) else None,
                        group_processor=generalize_same_length_tuples,
                    )
                )

            # merging same-type collections (list[int] | list[str] -> list[int | str])
            if isinstance(lt, LUnion):

                def merge_same_type_collections(lts: list[LearntType]) -> list[LearntType]:
                    if not lts or not all(isinstance(lt, LCollection) for lt in lts):
                        return lts
                    union_learnt_collections = cast(list[LCollection], lts)
                    return [
                        LCollection(
                            collection_type=union_learnt_collections[0].collection_type,
                            item_type=self._simplify_learnt_type(
                                LUnion([collection.item_type for collection in union_learnt_collections])
                            ),
                        )
                    ]

                lt = LUnion(
                    member_types=group_and_process(
                        lt.member_types,
                        group_key=lambda lt: lt.collection_type if isinstance(lt, LCollection) else None,
                        group_processor=merge_same_type_collections,
                    )
                )

            # merging typed dicts in a union
            if isinstance(lt, LUnion):

                def merge_typed_dicts(lts: list[LearntType]) -> list[LearntType]:
                    if not lts or not all(isinstance(lt, LTypedDict) for lt in lts):
                        return lts
                    union_typed_dicts = cast(list[LTypedDict], lts)
                    return [
                        LTypedDict(
                            {
                                k: self._simplify_learnt_type(
                                    LUnion([ltd.fields.get(k, LMissingTypedDictKey()) for ltd in union_typed_dicts])
                                )
                                for k in itertools.chain.from_iterable(lt.fields.keys() for lt in union_typed_dicts)
                            }
                        )
                    ]

                lt = LUnion(
                    member_types=group_and_process(
                        lt.member_types,
                        group_key=lambda lt: 1 if isinstance(lt, LTypedDict) else 0,
                        group_processor=merge_typed_dicts,
                    )
                )

            # demoting typed dicts to mappings if they are too large or if there are already regular mappings
            def demote_typed_dict_to_mapping(lt: LearntType) -> LearntType:
                if not isinstance(lt, LTypedDict):
                    return lt
                else:
                    union_value_type = self._simplify_learnt_type(LUnion(list(lt.fields.values())))
                    if isinstance(union_value_type, LUnion):
                        union_value_type = LUnion(
                            [vt for vt in union_value_type.member_types if vt != LMissingTypedDictKey()]
                        )
                    return LMapping(mapping_type=dict, key_type=LType(str), value_type=union_value_type)

            if isinstance(lt, LUnion):
                if any(
                    isinstance(member, LMapping)
                    or (isinstance(member, LTypedDict) and len(member.fields) > self.max_typed_dict_size)
                    for member in lt.member_types
                ):
                    lt = LUnion([demote_typed_dict_to_mapping(member) for member in lt.member_types])

            if isinstance(lt, LTypedDict) and len(lt.fields) > self.max_typed_dict_size:
                lt = demote_typed_dict_to_mapping(lt)

            # merging mappings in a union
            if isinstance(lt, LUnion):

                def merge_same_type_mappings(lts: list[LearntType]) -> list[LearntType]:
                    if not lts or not all(isinstance(lt, LMapping) for lt in lts):
                        return lts
                    union_mappings = cast(list[LMapping], lts)
                    return [
                        LMapping(
                            mapping_type=union_mappings[0].mapping_type,
                            key_type=self._simplify_learnt_type(LUnion([m.key_type for m in union_mappings])),
                            value_type=self._simplify_learnt_type(LUnion([m.value_type for m in union_mappings])),
                        )
                    ]

                lt = LUnion(
                    member_types=group_and_process(
                        lt.member_types,
                        group_key=lambda lt: lt.mapping_type if isinstance(lt, LMapping) else None,
                        group_processor=merge_same_type_mappings,
                    )
                )

            # removing union members that are subtypes of other members (Union[str, int, bool] => Union[str, int])
            # NOTE: this is done after merging everything
            if isinstance(lt, LUnion):
                lt = LUnion(
                    [
                        member
                        for member in lt.member_types
                        if not any(is_subtype(member, other_member) for other_member in lt.member_types)
                    ]
                )

            # recursing into union members
            # if isinstance(lt, LUnion):
            # lt = LUnion([self._simplify_learnt_type(m) for m in lt.member_types])

            # simplifying trivial unions (Union[T] -> T)
            if isinstance(lt, LUnion):
                if len(lt.member_types) == 1:
                    lt = lt.member_types[0]

            if lt == lt_prev:
                return lt  # the last iteration was noop - postprocessing done
            else:
                lt_prev = lt  # running next iteration

    def observe(self, value: Any) -> None:
        lt = self._learn_variable_type(value)
        if self.learnt_type is None:
            self.learnt_type = lt
        else:
            self.learnt_type = LUnion([self.learnt_type, lt])
        self.learnt_type = self._simplify_learnt_type(self.learnt_type)
        self.observed_values += 1

    def generate_type_definitions(
        self, filename: pathlib.Path, type_name: str, doc: str, target_version: PythonVersion = PythonVersion.PY38
    ):
        type_name = new_type_name(type_name, {})
        if self.learnt_type is None:
            raise RuntimeError("Unable to generate type definition before at least one value is observed")
        if filename.exists():
            raise FileExistsError(str(filename))
        imports: set[tuple[str, str]] = set()
        dependency_typedefs: dict[str, str] = dict()
        typedef_rhs = generate_typedef_rhs(self.learnt_type, type_name, target_version, imports, dependency_typedefs)
        text_blocks: list[str] = []

        text_blocks.append(
            '"""\n'
            + f"This file contains Python 3.{target_version}+ type definitions generated by {self.__class__.__qualname__} "
            + f"from {self.observed_values} observed values\n"
            + f"> {doc}\n"
            + '"""'
        )

        imports_block: list[str] = []
        for module, value in sorted(sorted(imports, key=lambda m_v: m_v[0]), key=lambda m_v: m_v[1]):
            imports_block.append(f"from {module} import {value}")
        text_blocks.append("\n".join(imports_block))

        text_blocks.extend(dependency_typedefs.values())

        if typedef_rhs != type_name:
            text_blocks.append(f"{type_name} = {typedef_rhs}")

        filename.write_text("\n\n".join(text_blocks))
