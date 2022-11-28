from abc import ABC
from dataclasses import dataclass
from typing import Any, Type


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


@dataclass(frozen=True)
class LearntTupleType(LearntType):
    """Inhomogenious, fixed size tuples, e.g. tuple[int, int, str]"""

    item_types: list[LearntType]
