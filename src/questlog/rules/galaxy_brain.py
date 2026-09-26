"""Galaxy Brain: discussion answers that GitHub marks as accepted."""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "galaxy_brain"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count accepted discussion answers in ``activity`` against ``thresholds``.

    The reader supplies one entry per accepted answer, so the count is the
    length of the tuple. Keeping that tuple free of duplicates is the
    reader's job.
    """
    return progress(NAME, len(activity.discussion_answers), thresholds)
