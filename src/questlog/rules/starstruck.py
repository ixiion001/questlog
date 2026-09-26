"""Starstruck: stars on the most-starred repository you own."""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "starstruck"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count the stars of the most-starred owned repository against ``thresholds``.

    ``owned_repos`` holds the repositories the user owns on one star-sorted
    page, so the maximum over the whole tuple is the count regardless of
    order. An account with no owned repositories scores zero.
    """
    stars = max((repo.stars for repo in activity.owned_repos), default=0)
    return progress(NAME, stars, thresholds)
