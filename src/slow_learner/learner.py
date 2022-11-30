import functools
import collections.abc
import logging
from enum import Enum
from typing import Any, Optional, cast

from .learnt_types import LearntType, LLiteral, LTuple, LType, LUnion, LCollection
from .subtyping import is_subtype, is_subtype_or_equal
from .utils import group_and_process

logger = logging.getLogger(__name__)


class TypeLearner:
    def __init__(self, max_literal_type_size: int = 10) -> None:
        self.learnt_type: Optional[LearntType] = None
        self.max_literal_type_size = max_literal_type_size

    def _learn_variable_type(self, var: Any) -> LearntType:
        if isinstance(var, (int, str, bytes, bool, Enum)) or var is None:
            return LLiteral(value=var)
        if isinstance(var, tuple):
            return LTuple(item_types=[self._learn_variable_type(item) for item in var])
        if isinstance(var, collections.abc.Collection):
            return LCollection(
                type(var),
                self._postprocess_learnt_type(LUnion([self._learn_variable_type(item) for item in var])),
            )
        return LType(type_=type(var))

    def _union_learnt_types(self, lt1: LearntType, lt2: LearntType) -> LearntType:
        if is_subtype_or_equal(lt1, lt2):
            return lt2
        if is_subtype_or_equal(lt2, lt1):
            return lt1

        if isinstance(lt2, LUnion):
            if isinstance(lt1, LUnion):
                return LUnion(lt1.member_types + lt2.member_types)
            else:
                lt1, lt2 = lt2, lt1
        if isinstance(lt1, LUnion):  # lt2 is guaranteed to not be LUnion here
            return LUnion([lt2, *lt1.member_types])

        return LUnion([lt1, lt2])

    def _postprocess_learnt_type(self, lt: LearntType) -> LearntType:
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
                lt = self._postprocess_learnt_type(LUnion(simple_type_members + other_members))

        # generalizing same-length tuples in a union (tuple[str, int] | tuple[float, bool] => tuple[str | float, int | bool])
        if isinstance(lt, LUnion):

            def generalize_same_length_tuples(lts: list[LearntType]) -> list[LearntType]:
                if not lts or not all(isinstance(lt, LTuple) for lt in lts):
                    return lts
                union_tuples = cast(list[LTuple], lts)
                result_tuple = union_tuples[0]
                for member in union_tuples:
                    for idx in range(len(result_tuple.item_types)):
                        result_tuple.item_types[idx] = self._postprocess_learnt_type(
                            self._union_learnt_types(result_tuple.item_types[idx], member.item_types[idx])
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
                union_collections = cast(list[LCollection], lts)
                union_item_type = functools.reduce(
                    self._union_learnt_types, (coll.item_type for coll in union_collections)
                )
                return [
                    LCollection(
                        collection_type=union_collections[0].collection_type,
                        item_type=self._postprocess_learnt_type(union_item_type),
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

        return lt

    def observe(self, value: Any) -> None:
        lt = self._learn_variable_type(value)
        if self.learnt_type is None:
            self.learnt_type = lt
        else:
            self.learnt_type = self._union_learnt_types(self.learnt_type, lt)
        self.learnt_type = self._postprocess_learnt_type(self.learnt_type)
