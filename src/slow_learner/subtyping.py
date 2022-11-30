import logging

from .learnt_types import LCollection, LearntType, LLiteral, LMapping, LTuple, LType, LTypedDict, LUnion

logger = logging.getLogger(__name__)


def is_subtype(maybe_sub: LearntType, maybe_super: LearntType) -> bool:
    if maybe_sub == maybe_super:
        return False
    try:
        if isinstance(maybe_sub, LType) and isinstance(maybe_super, LType):
            # special cases in mypy, see https://github.com/python/typing/issues/48
            num_type_tower = (bool, int, float, complex)
            try:
                return num_type_tower.index(maybe_sub.type_) < num_type_tower.index(maybe_super.type_)
            except Exception:
                return issubclass(maybe_sub.type_, maybe_super.type_)
        if isinstance(maybe_sub, LLiteral) and isinstance(maybe_super, LType):
            return isinstance(maybe_sub.value, maybe_super.type_) or is_subtype(
                LType(type(maybe_sub.value)), maybe_super
            )
        if isinstance(maybe_sub, LTuple) and isinstance(maybe_super, LTuple):
            return len(maybe_sub.item_types) == len(maybe_super.item_types) and all(
                is_subtype_or_equal(sub_item_type, super_item_type)
                for sub_item_type, super_item_type in zip(maybe_sub.item_types, maybe_super.item_types)
            )
        # collections and mappings are potentially invariant generics and can be subtyped only by top-level type
        # e.g. MyListSubclass[int] is a subtype of list[int], but list[int] is not a subtype of list[float]
        # see https://mypy.readthedocs.io/en/stable/generics.html#variance-of-generic-types
        if isinstance(maybe_sub, LCollection) and isinstance(maybe_super, LCollection):
            return maybe_sub.item_type == maybe_super.item_type and issubclass(
                maybe_sub.collection_type, maybe_super.collection_type
            )
        if isinstance(maybe_sub, LMapping) and isinstance(maybe_super, LMapping):
            return (
                maybe_sub.key_type == maybe_super.value_type
                and maybe_sub.key_type == maybe_super.value_type
                and issubclass(maybe_sub.mapping_type, maybe_super.mapping_type)
            )
        if isinstance(maybe_sub, LTypedDict) and isinstance(maybe_super, LTypedDict):
            for super_key, super_value_type in maybe_super.fields.items():
                if not (
                    super_key in maybe_sub.fields and is_subtype_or_equal(maybe_sub.fields[super_key], super_value_type)
                ):
                    return False
            else:
                return True
        if isinstance(maybe_sub, LUnion):
            return all(is_subtype(member, maybe_super) for member in maybe_sub.member_types)
        if isinstance(maybe_super, LUnion):
            return any(is_subtype_or_equal(maybe_sub, member) for member in maybe_super.member_types)
    except Exception:
        logger.exception("Error checking subtype")
    return False


def is_subtype_or_equal(maybe_sub: LearntType, maybe_super: LearntType) -> bool:
    return is_subtype(maybe_sub, maybe_super) or maybe_sub == maybe_super
