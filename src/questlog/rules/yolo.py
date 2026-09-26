"""YOLO: a pull request you merged without a review.

Approximated from ``Activity``: it holds your own pull requests only (no
``merged_by``), so this counts merges with ``reviewed=False``.
"""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "yolo"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count pull requests merged without a review against ``thresholds``."""
    count = sum(1 for pr in activity.pull_requests if pr.merged_at is not None and not pr.reviewed)
    return progress(NAME, count, thresholds)
