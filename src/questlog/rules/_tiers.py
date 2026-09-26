"""Shared tier arithmetic for rule modules."""

from collections.abc import Sequence

from questlog.models import Progress


def progress(name: str, count: int, thresholds: Sequence[int]) -> Progress:
    """Turn a raw count into a Progress.

    ``tier`` is the number of thresholds reached. ``next_threshold`` is the
    first threshold above ``count`` in config order and ``None`` once every
    tier is reached; ``remaining`` is what is still missing for it.
    """
    tier = 0
    next_threshold = None
    for threshold in thresholds:
        if count >= threshold:
            tier += 1
        elif next_threshold is None:
            next_threshold = threshold
    remaining = None if next_threshold is None else next_threshold - count
    return Progress(
        name=name, count=count, tier=tier, next_threshold=next_threshold, remaining=remaining
    )
