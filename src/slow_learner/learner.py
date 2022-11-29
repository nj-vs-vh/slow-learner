import itertools
import logging
from enum import Enum
from typing import Any, Optional, cast

from .learnt_types import LearntType, LLiteral, LTuple, LType, LUnion
from .subtyping import is_subtype, is_subtype_or_equal

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
        # deduplicating union types (can't use set because there's no hashability guarantee)
        if isinstance(lt, LUnion):
            # deduplicating union types (can't use set because there's no hashability guarantee)
            dedup_member_types: list[LearntType] = []
            for member in lt.member_types:
                if member not in dedup_member_types:
                    dedup_member_types.append(member)
            lt = LUnion(dedup_member_types)

        # removing union members that are subtypes of other members
        if isinstance(lt, LUnion):
            lt = LUnion(
                [
                    member
                    for member in lt.member_types
                    if not any(is_subtype(member, other_member) for other_member in lt.member_types)
                ]
            )

        # generalizing too large unions of literals (Literal[1, 2, 3] => int)
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

        # generalizing same-length tuples (tuple[str, int] | tuple[float, bool] => tuple[str | float, int | bool])
        if isinstance(lt, LUnion):
            tuple_len = lambda lt: len(lt.item_types) if isinstance(lt, LTuple) else -1
            new_members: list[LearntType] = []
            for tuple_length, member_types_group in itertools.groupby(
                sorted(lt.member_types, key=tuple_len), key=tuple_len
            ):
                if tuple_length == -1:
                    new_members.extend(member_types_group)
                else:
                    same_length_tuple_members = cast(list[LTuple], list(member_types_group))
                    union_tuple = same_length_tuple_members[0]
                    for member in same_length_tuple_members:
                        for idx in range(tuple_length):
                            union_tuple.item_types[idx] = self._postprocess_learnt_type(
                                self._union_learnt_types(union_tuple.item_types[idx], member.item_types[idx])
                            )
                    new_members.append(union_tuple)
            lt = LUnion(new_members)

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
