import logging
from enum import Enum
from typing import Any, Optional, Type

from .learnt_types import LLiteral, LType, LTuple, LearntType, LUnion
from .subtyping import is_subtype

logger = logging.getLogger(__name__)


class TypeLearner:
    def __init__(self, max_literal_type_size: int = 10) -> None:
        self.result: Optional[LearntType] = None
        self.max_literal_type_size = max_literal_type_size

    def learn_variable_type(self, var: Any, prevent_literals: bool = False) -> LearntType:
        if not prevent_literals and isinstance(var, (int, str, bytes, bool, Enum)) or var is None:
            return LLiteral(value=var)
        if isinstance(var, tuple):
            return LTuple(item_types=[self.learn_variable_type(item, prevent_literals=True) for item in var])
        return LType(type_=type(var))

    def union_learnt_types(self, lt1: LearntType, lt2: LearntType) -> LearntType:
        if lt1 == lt2:
            return lt1
        if is_subtype(lt1, lt2):
            return lt2
        if is_subtype(lt2, lt1):
            return lt1
        return LUnion([lt1, lt2])

    def postprocess_learnt_type(self, lt: LearntType) -> LearntType:
        # generalizing too large literal types
        if isinstance(lt, LUnion):
            literal_members: list[LLiteral] = []
            other_members: list[LearntType] = []
            for member in lt.union_members:
                if isinstance(member, LLiteral):
                    literal_members.append(member)
                else:
                    other_members.append(member)
            if len(literal_members) > self.max_literal_type_size:
                simple_type_members = [LType(type(lm.value)) for lm in literal_members]
                lt = LUnion(simple_type_members + other_members)
        # simplifying trivial unions (Union[str] -> str)
        if isinstance(lt, LUnion) and len(lt.union_members) == 1:
            lt = lt.union_members[0]
        return lt

    def observe(self, value: Any) -> None:
        lt = self.learn_variable_type(value)
        if self.result is None:
            self.result = lt
        else:
            self.result = self.union_learnt_types(self.result, lt)
        self.result = self.postprocess_learnt_type(self.result)
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
