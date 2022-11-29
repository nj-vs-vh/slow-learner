from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Type


class LearntType(ABC):
    pass


@dataclass(frozen=True)
class LLiteral(LearntType):
    """Literal type with a single possible value; See https://peps.python.org/pep-0586/ for details"""

    value: Any


@dataclass(frozen=True)
class LType(LearntType):
    """Simple, opaque type, either built-in or custom"""

    type_: Type[Any]


@dataclass(frozen=True)
class LUnion(LearntType):
    """Union of several other types"""

    member_types: list[LearntType]

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, LUnion):
            return False
        for (one, another) in ((self, __o), (__o, self)):
            if not all(member in another.member_types for member in one.member_types):
                return False
        else:
            return True


@dataclass(frozen=True)
class LTuple(LearntType):
    """Inhomogenious, fixed size tuple, e.g. tuple[int, int, str]"""

    item_types: list[LearntType]
