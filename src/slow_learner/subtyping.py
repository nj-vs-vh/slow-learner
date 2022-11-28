import logging

from .learnt_types import LearntLiteralType, LearntSimpleType, LearntTupleType, LearntType, LearntUnionType

logger = logging.getLogger(__name__)


def is_subtype(maybe_sub: LearntType, maybe_super: LearntType) -> bool:
    try:
        if maybe_sub == maybe_super:
            return True
        if isinstance(maybe_sub, LearntSimpleType) and isinstance(maybe_super, LearntSimpleType):
            return maybe_sub.type_ != maybe_super.type_ and issubclass(maybe_sub.type_, maybe_super.type_)
        if isinstance(maybe_sub, LearntLiteralType) and isinstance(maybe_super, LearntSimpleType):
            return isinstance(maybe_sub.value, maybe_super.type_)
        if isinstance(maybe_sub, LearntTupleType) and isinstance(maybe_super, LearntTupleType):
            return len(maybe_sub.item_types) == len(maybe_super.item_types) and all(
                is_subtype(sub_item_type, super_item_type)
                for sub_item_type, super_item_type in zip(maybe_sub.item_types, maybe_super.item_types)
            )
        if isinstance(maybe_sub, LearntUnionType):
            return all(is_subtype(member, maybe_super) for member in maybe_sub.union_members)
        if isinstance(maybe_super, LearntUnionType):
            return any(is_subtype(maybe_sub, member) for member in maybe_super.union_members)
    except Exception:
        logger.exception("Error checking subtype")
    return False
