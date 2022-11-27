from typing import Any, Optional, Type
from enum import Enum
from dataclasses import dataclass
from abc import ABC


class LearntType(ABC):
    pass


@dataclass(frozen=True)
class LearntLiteralType(LearntType):
    """Literal type with a single possible value; See https://peps.python.org/pep-0586/ for details"""

    value: Any


@dataclass(frozen=True)
class LearntSimpleType(LearntType):
    """Simple, opaque type, either built-in or custom"""

    type_: Type[Any]


@dataclass
class LearntUnionType(LearntType):
    union_members: list[LearntType]

    def __post_init__(self) -> None:
        flattened: list[LearntType] = []
        for member in self.union_members:
            if isinstance(member, LearntUnionType):
                flattened.extend(member.union_members)
            else:
                flattened.append(member)

        deduplicated: list[LearntType] = []
        for member in flattened:
            if member not in deduplicated:
                deduplicated.append(member)

        desubtyped: list[LearntType] = []
        for member in deduplicated:
            if any(is_subtype(member, other_member) for other_member in deduplicated):
                continue
            desubtyped.append(member)

        self.union_members = desubtyped


@dataclass(frozen=True)
class LearntTupleType(LearntType):
    """Inhomogenious tuples, e.g. tuple[int, int, str]"""

    item_types: list[LearntType]


def learn_variable_type(var: Any, prevent_literals: bool = False) -> LearntType:
    if not prevent_literals and isinstance(var, (int, str, bytes, bool, Enum)) or var is None:
        return LearntLiteralType(value=var)
    if isinstance(var, tuple):
        return LearntTupleType(item_types=[learn_variable_type(item, prevent_literals=True) for item in var])
    return LearntSimpleType(type_=type(var))


def union_learnt_types(lt1: LearntType, lt2: LearntType) -> LearntType:
    return LearntUnionType([lt1, lt2])


def is_subtype(maybe_sub: LearntType, maybe_super: LearntType) -> bool:
    try:
        if isinstance(maybe_sub, LearntSimpleType) and isinstance(maybe_super, LearntSimpleType):
            return maybe_sub.type_ != maybe_super.type_ and issubclass(maybe_sub.type_, maybe_super.type_)
        if isinstance(maybe_sub, LearntLiteralType) and isinstance(maybe_super, LearntSimpleType):
            return isinstance(maybe_sub.value, maybe_super.type_)
        if isinstance(maybe_sub, LearntTupleType) and isinstance(maybe_super, LearntTupleType):
            return len(maybe_sub.item_types) == len(maybe_super.item_types) and all(
                is_subtype(sub_item_type, super_item_type)
                for sub_item_type, super_item_type in zip(maybe_sub.item_types, maybe_super.item_types)
            )
        if isinstance(maybe_super, LearntUnionType):
            return any(is_subtype(maybe_sub, member) for member in maybe_super.union_members)
    except Exception:
        pass
    return False


@dataclass(frozen=True)
class TypeLearningConfig:
    max_literal_size: int


def postprocess_learnt_type(lt: LearntType, config: TypeLearningConfig) -> LearntType:
    # generalizing too large literal types
    if isinstance(lt, LearntUnionType):
        literal_members: list[LearntLiteralType] = []
        other_members: list[LearntType] = []
        for member in lt.union_members:
            if isinstance(member, LearntLiteralType):
                literal_members.append(member)
            else:
                other_members.append(member)
        if len(literal_members) > config.max_literal_size:
            simple_type_members = [LearntSimpleType(type(lm.value)) for lm in literal_members]
            lt = LearntUnionType(simple_type_members + other_members)
    # simplifying trivial unions (Union[str] -> str)
    if isinstance(lt, LearntUnionType) and len(lt.union_members) == 1:
        lt = lt.union_members[0]
    return lt


class TypeLearner:
    def __init__(self, max_literal_type_size: int = 10) -> None:
        self.result: Optional[LearntType] = None
        self.max_literal_type_size = max_literal_type_size
        self.learning_config = TypeLearningConfig(max_literal_size=max_literal_type_size)

    def observe(self, value: Any) -> None:
        lt = learn_variable_type(value)
        if self.result is None:
            self.result = lt
        else:
            self.result = union_learnt_types(self.result, lt)
        self.result = postprocess_learnt_type(self.result, self.learning_config)
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

