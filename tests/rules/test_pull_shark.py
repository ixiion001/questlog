"""Tests for the Pull Shark rule: merged pull requests you authored."""

from datetime import UTC, datetime

from questlog.models import Activity, Progress, PullRequest
from questlog.rules.pull_shark import evaluate

T0 = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLDS = [2, 16, 128, 1024]


def activity_with(merged: int = 0, open_: int = 0, closed_unmerged: int = 0) -> Activity:
    merged_prs = tuple(PullRequest("o/r", i, T0, T0, T0, reviewed=True) for i in range(merged))
    open_prs = tuple(
        PullRequest("o/r", 100 + i, T0, None, None, reviewed=False) for i in range(open_)
    )
    closed_prs = tuple(
        PullRequest("o/r", 200 + i, T0, T0, None, reviewed=True) for i in range(closed_unmerged)
    )
    return Activity("octocat", merged_prs + open_prs + closed_prs, ())


def test_empty_activity_is_tier_zero():
    assert evaluate(Activity("octocat", (), ()), THRESHOLDS) == Progress(
        name="pull_shark", count=0, tier=0, next_threshold=2, remaining=2
    )


def test_only_merged_pull_requests_count():
    progress = evaluate(activity_with(merged=1, open_=2, closed_unmerged=1), THRESHOLDS)
    assert (progress.count, progress.tier, progress.remaining) == (1, 0, 1)


def test_threshold_reached_exactly():
    assert evaluate(activity_with(merged=2), THRESHOLDS) == Progress(
        name="pull_shark", count=2, tier=1, next_threshold=16, remaining=14
    )


def test_counts_between_thresholds():
    progress = evaluate(activity_with(merged=20), THRESHOLDS)
    assert (progress.count, progress.tier, progress.next_threshold, progress.remaining) == (
        20,
        2,
        128,
        108,
    )


def test_all_tiers_reached():
    assert evaluate(activity_with(merged=2000), THRESHOLDS) == Progress(
        name="pull_shark", count=2000, tier=4, next_threshold=None, remaining=None
    )


def test_thresholds_come_from_the_caller():
    assert evaluate(activity_with(merged=5), [1, 3]) == Progress(
        name="pull_shark", count=5, tier=2, next_threshold=None, remaining=None
    )
