"""Render progress as text or JSON."""

import dataclasses
import json
from collections.abc import Mapping

from questlog.models import Progress

BAR_WIDTH = 20
"""Width of the progress bar, in cells. Every row draws the same number of them."""


def _format_bar(count: int, next_threshold: int) -> str:
    """Draw ``count`` toward ``next_threshold`` as a fixed-width bar.

    The fill is proportional to ``count / next_threshold``: the bar shows how
    much of the way to the next tier the count has come, not the share of the
    current tier that is done (``Progress`` does not carry the previous
    threshold).
    """
    ratio = min(1.0, max(0.0, count / next_threshold))
    filled = round(BAR_WIDTH * ratio)
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


def _format_progress(item: Progress, labels: Mapping[str, str] | None = None) -> str:
    name = labels.get(item.name, item.name) if labels else item.name
    tier_label = f"Tier {item.tier}" if item.tier > 0 else "no tier yet"
    if item.next_threshold is None:
        bar = "[" + "#" * BAR_WIDTH + "]"
        return f"[x] {name} ({tier_label}): {bar} {item.count} (completed)"
    bar = _format_bar(item.count, item.next_threshold)
    return (
        f"[ ] {name} ({tier_label}): {bar} "
        f"{item.count}/{item.next_threshold} ({item.remaining} remaining)"
    )


def render_text(progress: list[Progress], labels: Mapping[str, str] | None = None) -> str:
    """Render a list of Progress objects into a readable text view."""
    if not progress:
        return "No progress to report.\n"
    return "\n".join(_format_progress(p, labels) for p in progress) + "\n"


def render_json(progress: list[Progress]) -> str:
    """Render a list of Progress objects as formatted JSON."""
    data = [dataclasses.asdict(p) for p in progress]
    return json.dumps(data, indent=2) + "\n"
