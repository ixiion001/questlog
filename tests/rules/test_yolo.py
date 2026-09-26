"""Tests for the YOLO rule: pull requests merged without a review."""

from datetime import UTC, datetime

from questlog.models import Activity, Progress, PullRequest
from questlog.rules.yolo import evaluate

T0 = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLDS = [1]


def merged(reviewed: bool, number: int) -> PullRequest:
    return PullRequest("o/r", number, T0, T0, T0, reviewed=reviewed)


def not_merged(reviewed: bool, number: int) -> PullRequest:
    return PullRequest("o/r", number, T0, T0, None, reviewed=reviewed)


def test_empty_activity_is_tier_zero():
    assert evaluate(Activity("octocat", (), ()), THRESHOLDS) == Progress(
        name="yolo", count=0, tier=0, next_threshold=1, remaining=1
    )


def test_merges_without_review_count():
    activity = Activity("octocat", (merged(False, 1), merged(False, 2)), ())
    assert evaluate(activity, THRESHOLDS) == Progress(
        name="yolo", count=2, tier=1, next_threshold=None, remaining=None
    )


def test_merges_with_review_do_not_count():
    activity = Activity("octocat", (merged(True, 1), merged(True, 2)), ())
    assert evaluate(activity, THRESHOLDS) == Progress(
        name="yolo", count=0, tier=0, next_threshold=1, remaining=1
    )


def test_unmerged_pull_requests_do_not_count():
    open_pr = PullRequest("o/r", 3, T0, None, None, reviewed=False)
    activity = Activity("octocat", (not_merged(False, 1), open_pr), ())
    assert evaluate(activity, THRESHOLDS).count == 0


def test_only_unreviewed_merges_count():
    activity = Activity("octocat", (merged(False, 1), merged(True, 2), not_merged(False, 3)), ())
    assert evaluate(activity, THRESHOLDS).count == 1


def test_thresholds_come_from_the_caller():
    activity = Activity("octocat", (merged(False, 1), merged(False, 2), merged(False, 3)), ())
    assert evaluate(activity, [1, 5]) == Progress(
        name="yolo", count=3, tier=1, next_threshold=5, remaining=2
    )
