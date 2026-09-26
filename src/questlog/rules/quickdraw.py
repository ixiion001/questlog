"""Quickdraw: an issue or pull request you closed within 5 minutes of opening it."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "quickdraw"
WINDOW = timedelta(minutes=5)


def _closed_quickly(created_at: datetime, closed_at: datetime | None) -> bool:
    if closed_at is None:
        return False
    age = closed_at - created_at
    return timedelta(0) <= age <= WINDOW


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count issues and pull requests closed within the window of opening."""
    count = sum(
        1 for issue in activity.issues if _closed_quickly(issue.created_at, issue.closed_at)
    )
    count += sum(1 for pr in activity.pull_requests if _closed_quickly(pr.created_at, pr.closed_at))
    return progress(NAME, count, thresholds)
