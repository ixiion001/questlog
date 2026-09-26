"""Pull Shark: pull requests you opened that were merged."""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "pull_shark"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count merged pull requests in ``activity`` against ``thresholds``."""
    count = sum(1 for pr in activity.pull_requests if pr.merged_at is not None)
    return progress(NAME, count, thresholds)
