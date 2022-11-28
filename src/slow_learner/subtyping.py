import logging

from .learnt_types import LLiteral, LType, LTuple, LearntType, LUnion

logger = logging.getLogger(__name__)


def is_subtype(maybe_sub: LearntType, maybe_super: LearntType) -> bool:
    try:
        if maybe_sub == maybe_super:
            return True
        if isinstance(maybe_sub, LType) and isinstance(maybe_super, LType):
            return maybe_sub.type_ != maybe_super.type_ and issubclass(maybe_sub.type_, maybe_super.type_)
        if isinstance(maybe_sub, LLiteral) and isinstance(maybe_super, LType):
            return isinstance(maybe_sub.value, maybe_super.type_)
        if isinstance(maybe_sub, LTuple) and isinstance(maybe_super, LTuple):
            return len(maybe_sub.item_types) == len(maybe_super.item_types) and all(
                is_subtype(sub_item_type, super_item_type)
                for sub_item_type, super_item_type in zip(maybe_sub.item_types, maybe_super.item_types)
            )
        if isinstance(maybe_sub, LUnion):
            return all(is_subtype(member, maybe_super) for member in maybe_sub.union_members)
        if isinstance(maybe_super, LUnion):
            return any(is_subtype(maybe_sub, member) for member in maybe_super.union_members)
    except Exception:
        logger.exception("Error checking subtype")
    return False
