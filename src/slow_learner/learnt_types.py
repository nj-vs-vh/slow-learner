from abc import ABC
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any, Type


class LearntType(ABC):
    pass


@dataclass(frozen=True)
class LLiteral(LearntType):
    """Literal with a single possible value; see https://peps.python.org/pep-0586/ for details"""

    value: Any

    def __str__(self) -> str:
        return f"Literal[{self.value!r}]"


@dataclass(frozen=True)
class LNone(LearntType):
    """Literal None, separated from LLiteral for cleaner learning"""

    def __str__(self) -> str:
        return "None"


@dataclass(frozen=True)
class LType(LearntType):
    """Simple, opaque type, either built-in or custom"""

    type_: Type[Any]

    def __str__(self) -> str:
        return self.type_.__qualname__


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

    def __str__(self) -> str:
        return " | ".join(str(m) for m in self.member_types)


@dataclass(frozen=True)
class LTuple(LearntType):
    """Inhomogenious, fixed size tuple, e.g. tuple[int, int, str]"""

    item_types: list[LearntType]

    def __str__(self) -> str:
        return "tuple[" + ", ".join(str(item_type) for item_type in self.item_types) + "]"


@dataclass
class LCollection(LearntType):
    """Homogenious collection with single type parameter, like list[int], set[bool | str] or tuple[float, ...]"""

    collection_type: Type[Collection]
    item_type: LearntType

    def __str__(self) -> str:
        return f"{self.collection_type.__qualname__}[{self.item_type}]"


@dataclass
class LMapping(LearntType):
    """Simple mapping type with two type parameters, like dict[int, bool] or TTLCache[str, float]"""

    mapping_type: Type[Mapping]
    key_type: LearntType
    value_type: LearntType

    def __str__(self) -> str:
        return f"{self.mapping_type.__qualname__}[{self.key_type}, {self.value_type}]"


@dataclass
class LMissingTypedDictKey(LearntType):
    """Special type only allowed as a possible value for LTypedDict to mark not required key"""

    def __str__(self) -> str:
        return "<missing>"


@dataclass
class LTypedDict(LearntType):
    """TypedDict, i.e. dict with string keys and per-key typing, see https://peps.python.org/pep-0589/"""

    fields: dict[str, LearntType]

    def __str__(self) -> str:
        body_str = ", ".join('"' + key_name + '": ' + str(value_type) for key_name, value_type in self.fields.items())
        return f"TypedDict({{{body_str}}})"
