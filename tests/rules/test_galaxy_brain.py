"""Tests for the Galaxy Brain rule: discussion answers marked as accepted."""

from datetime import UTC, datetime

from questlog.models import Activity, DiscussionAnswer, Progress
from questlog.rules.galaxy_brain import evaluate

T0 = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLDS = [2, 8, 16, 32]


def activity_with(count: int = 0) -> Activity:
    answers = tuple(DiscussionAnswer("o/r", i + 1, T0) for i in range(count))
    return Activity("octocat", (), (), answers)


def test_empty_activity_is_tier_zero():
    assert evaluate(Activity("octocat", (), ()), THRESHOLDS) == Progress(
        name="galaxy_brain", count=0, tier=0, next_threshold=2, remaining=2
    )


def test_threshold_reached_exactly():
    assert evaluate(activity_with(2), THRESHOLDS) == Progress(
        name="galaxy_brain", count=2, tier=1, next_threshold=8, remaining=6
    )


def test_counts_between_thresholds():
    progress = evaluate(activity_with(9), THRESHOLDS)
    assert (progress.count, progress.tier, progress.next_threshold, progress.remaining) == (
        9,
        2,
        16,
        7,
    )


def test_all_tiers_reached():
    assert evaluate(activity_with(40), THRESHOLDS) == Progress(
        name="galaxy_brain", count=40, tier=4, next_threshold=None, remaining=None
    )


def test_thresholds_come_from_the_caller():
    assert evaluate(activity_with(5), [1, 3]) == Progress(
        name="galaxy_brain", count=5, tier=2, next_threshold=None, remaining=None
    )


def test_every_answer_counts_within_one_discussion():
    """Two accepted answers in one discussion are two, not one."""
    activity = Activity(
        "octocat",
        (),
        (),
        (
            DiscussionAnswer("o/r", 7, T0),
            DiscussionAnswer("o/r", 7, T0),
            DiscussionAnswer("o/other", 7, T0),
        ),
    )
    assert evaluate(activity, THRESHOLDS).count == 3
