"""Galaxy Brain: discussion answers that GitHub marks as accepted."""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "galaxy_brain"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count accepted discussion answers in ``activity`` against ``thresholds``.

    Every ``DiscussionAnswer`` in the activity is an accepted one: the reader
    only collects answers GitHub flagged, so each one counts on its own even
    when several live in the same discussion.
    """
    return progress(NAME, len(activity.discussion_answers), thresholds)
