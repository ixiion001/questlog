"""Tests for the Starstruck rule: stars on the most-starred owned repository."""

from questlog.models import Activity, OwnedRepo, Progress
from questlog.rules.starstruck import evaluate

THRESHOLDS = [16, 128, 512, 4096]


def activity_with(*repos: OwnedRepo) -> Activity:
    return Activity("octocat", (), (), (), tuple(repos))


def test_empty_activity_is_tier_zero():
    assert evaluate(Activity("octocat", (), ()), THRESHOLDS) == Progress(
        name="starstruck", count=0, tier=0, next_threshold=16, remaining=16
    )


def test_count_below_the_first_threshold():
    assert evaluate(activity_with(OwnedRepo("o/r", 15)), THRESHOLDS) == Progress(
        name="starstruck", count=15, tier=0, next_threshold=16, remaining=1
    )


def test_threshold_reached_exactly():
    assert evaluate(activity_with(OwnedRepo("o/r", 16)), THRESHOLDS) == Progress(
        name="starstruck", count=16, tier=1, next_threshold=128, remaining=112
    )


def test_only_the_most_starred_repository_counts():
    # The maximum wins wherever it sits, not only in the first page position.
    activity = activity_with(
        OwnedRepo("o/small", 3), OwnedRepo("o/big", 500), OwnedRepo("o/mid", 20)
    )
    progress = evaluate(activity, THRESHOLDS)
    assert (progress.count, progress.tier, progress.next_threshold, progress.remaining) == (
        500,
        2,
        512,
        12,
    )


def test_all_tiers_reached():
    assert evaluate(activity_with(OwnedRepo("o/r", 4096)), THRESHOLDS) == Progress(
        name="starstruck", count=4096, tier=4, next_threshold=None, remaining=None
    )


def test_zero_star_repositories_score_zero():
    assert evaluate(activity_with(OwnedRepo("o/r", 0)), THRESHOLDS).count == 0


def test_thresholds_come_from_the_caller():
    assert evaluate(activity_with(OwnedRepo("o/r", 5)), [1, 3]) == Progress(
        name="starstruck", count=5, tier=2, next_threshold=None, remaining=None
    )
