import itertools
from collections.abc import Collection
from typing import Callable, Hashable, Iterable, Optional, TypeVar, Union

ItemT = TypeVar("ItemT")


def group_and_process(
    collection: Collection[ItemT],
    group_key: Callable[[ItemT], Optional[Hashable]],
    group_processor: Callable[[list[ItemT]], list[ItemT]],
) -> list[ItemT]:
    """Wrapper around itertools.groupby that

    - groups elements with non-None group_key value
    - applies group_processor func to each group
    - collects and returns processed groups and ungrouped elements
    """
    result: list[ItemT] = []

    def safe_key(item: ItemT) -> int:
        unsafe_key = group_key(item)
        return hash(unsafe_key) if unsafe_key is not None else -1

    for key, group in itertools.groupby(sorted(collection, key=safe_key), key=safe_key):
        if key == -1:
            result.extend(group)
        else:
            result.extend(group_processor(list(group)))
    return result


def to_json_path(path_parts: list[Union[str, int]]) -> str:
    return "".join(["." + p if isinstance(p, str) else f"[{p}]" for p in path_parts if isinstance(p, (int, str))])
