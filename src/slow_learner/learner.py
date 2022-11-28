import logging
from enum import Enum
from typing import Any, Optional, Type

from .learnt_types import LearntType, LLiteral, LTuple, LType, LUnion
from .subtyping import is_subtype, is_subtype_or_equal

logger = logging.getLogger(__name__)


class TypeLearner:
    def __init__(self, max_literal_type_size: int = 10, max_distinct_tuple_variants: int = 10) -> None:
        self.result: Optional[LearntType] = None
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
        if isinstance(lt, LUnion):
            # generalizing too large unions of literals (Literal[1, 2, 3] => int)
            literal_members: list[LLiteral] = []
            other_members: list[LearntType] = []
            for member in lt.member_types:
                if isinstance(member, LLiteral):
                    literal_members.append(member)
                else:
                    other_members.append(member)
            if len(literal_members) > self.max_literal_type_size:
                simple_type_members = [LType(type(lm.value)) for lm in literal_members]
                lt = LUnion(simple_type_members + other_members)

            # deduplicating union types (can't use set because there's no hashability guarantee)
            dedup_member_types: list[LearntType] = []
            for member in lt.member_types:
                if member not in dedup_member_types:
                    dedup_member_types.append(member)
            lt = LUnion(dedup_member_types)

            # removing union members that are subtypes of other members
            lt = LUnion(
                [
                    member
                    for member in lt.member_types
                    if not any(is_subtype(member, other_member) for other_member in lt.member_types)
                ]
            )

            # simplifying trivial unions (Union[T] -> T)
            if len(lt.member_types) == 1:
                lt = lt.member_types[0]

        return lt

    def observe(self, value: Any) -> None:
        lt = self._learn_variable_type(value)
        if self.result is None:
            self.result = lt
        else:
            self.result = self._union_learnt_types(self.result, lt)
        self.result = self._postprocess_learnt_type(self.result)
        print(self.result)
        print()


if __name__ == "__main__":
    tl = TypeLearner()

    # class Custom:
    #     pass

    # tl.observe(1)
    # tl.observe(Custom())
    # tl.observe(3.1415)
    # # tl.observe("hello")
    # for i in range(15):
    #     tl.observe(i)

    tl.observe((1, 2, 3))
    tl.observe((2, 3, 4))

    class SubInt(int):
        pass

    tl.observe((SubInt(3), SubInt(2), SubInt(5)))
