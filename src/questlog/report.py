"""Render progress as text or JSON."""

import dataclasses
import json
from collections.abc import Mapping

from questlog.models import Progress


def _format_progress(item: Progress, labels: Mapping[str, str] | None = None) -> str:
    name = labels.get(item.name, item.name) if labels else item.name
    tier_label = f"Tier {item.tier}" if item.tier > 0 else "no tier yet"
    if item.next_threshold is None:
        return f"[x] {name} ({tier_label}): {item.count} (completed)"
    return (
        f"[ ] {name} ({tier_label}): "
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
