import collections.abc
import functools
import logging
from enum import Enum
from typing import Any, Optional, cast

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
from .utils import group_and_process

logger = logging.getLogger(__name__)


class TypeLearner:
    def __init__(
        self, max_literal_type_size: int = 10, learn_typed_dicts: bool = True, max_typed_dict_size: int = 100
    ) -> None:
        self.learnt_type: Optional[LearntType] = None
        self.max_literal_type_size = max_literal_type_size
        self.max_typed_dict_size = max_typed_dict_size
        self.learn_typed_dicts = learn_typed_dicts

    def _learn_variable_type(self, var: Any) -> LearntType:
        if var is None:
            return LNone()
        if isinstance(var, (int, str, bytes, bool, Enum)):
            return LLiteral(value=var)
        if isinstance(var, tuple):
            return LTuple(item_types=[self._learn_variable_type(item) for item in var])
        if isinstance(var, collections.abc.Mapping):
            value_type_by_key: dict[Any, LearntType] = {k: self._learn_variable_type(v) for k, v in var.items()}
            key_types = [self._learn_variable_type(k) for k in value_type_by_key.keys()]
            if self.learn_typed_dicts and isinstance(var, dict) and all(kt == LType(str) for kt in key_types):
                return LTypedDict(value_type_by_key)
            else:
                return LMapping(
                    mapping_type=type(var),
                    key_type=self._simplify_learnt_type(LUnion(key_types)),
                    value_type=self._simplify_learnt_type(LUnion(list(value_type_by_key.values()))),
                )
        if isinstance(var, collections.abc.Collection):
            return LCollection(
                type(var),
                self._simplify_learnt_type(LUnion([self._learn_variable_type(item) for item in var])),
            )
        return LType(type_=type(var))

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

            # removing union members that are subtypes of other members (Union[str, int, bool] => Union[str, int])
            if isinstance(lt, LUnion):
                lt = LUnion(
                    [
                        member
                        for member in lt.member_types
                        if not any(is_subtype(member, other_member) for other_member in lt.member_types)
                    ]
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

            # generalizing same-length tuples in a union (tuple[str, int] | tuple[float, bool] => tuple[str | float, int | bool])
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

            # generalizing same-type collections (list[int] | list[str] -> list[int | str])
            if isinstance(lt, LUnion):

                def generalize_same_type_collections(lts: list[LearntType]) -> list[LearntType]:
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
                        group_processor=generalize_same_type_collections,
                    )
                )

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
