"""Render progress as text or JSON."""

from questlog.models import Progress


def render_text(progress: list[Progress]) -> str:
    raise NotImplementedError


def render_json(progress: list[Progress]) -> str:
    raise NotImplementedError
