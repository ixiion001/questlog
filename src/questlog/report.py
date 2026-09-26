"""Render progress as text or JSON."""

import dataclasses
import json

from questlog.models import Progress


def _format_progress(item: Progress) -> str:
    if item.next_threshold is None:
        return f"[x] {item.name} (Tier {item.tier}): {item.count} (completed)"
    return (
        f"[ ] {item.name} (Tier {item.tier}): "
        f"{item.count}/{item.next_threshold} ({item.remaining} remaining)"
    )


def render_text(progress: list[Progress]) -> str:
    """Render a list of Progress objects into a readable text view."""
    if not progress:
        return "No progress to report.\n"
    return "\n".join(_format_progress(p) for p in progress) + "\n"


def render_json(progress: list[Progress]) -> str:
    """Render a list of Progress objects as formatted JSON."""
    data = [dataclasses.asdict(p) for p in progress]
    return json.dumps(data, indent=2) + "\n"
