"""Read a user's activity through the ``gh`` CLI. The only network code."""

from collections.abc import Callable

from questlog.models import Activity


def gh_json(args: list[str]) -> dict | list:
    """Run ``gh`` with ``args`` and return its parsed JSON output."""
    raise NotImplementedError


def fetch_activity(login: str, run: Callable[[list[str]], dict | list] = gh_json) -> Activity:
    """Collect the pull requests and issues of ``login``."""
    raise NotImplementedError
