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


@dataclass
class LUnion(LearntType):
    member_types: list[LearntType]


@dataclass(frozen=True)
class LTuple(LearntType):
    """Inhomogenious, fixed size tuples, e.g. tuple[int, int, str]"""

    item_types: list[LearntType]
