"""Tests for the Quickdraw rule: closed within 5 minutes of opening."""

from datetime import UTC, datetime, timedelta

from questlog.models import Activity, Issue, Progress, PullRequest
from questlog.rules.quickdraw import evaluate

T0 = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLDS = [1]
FIVE_MINUTES = timedelta(minutes=5)


def issue(offset: timedelta | None, number: int = 1) -> Issue:
    closed = None if offset is None else T0 + offset
    return Issue("o/r", number, T0, closed)


def pull_request(offset: timedelta | None, number: int = 2) -> PullRequest:
    closed = None if offset is None else T0 + offset
    return PullRequest("o/r", number, T0, closed, None, reviewed=False)


def test_empty_activity_is_tier_zero():
    assert evaluate(Activity("octocat", (), ()), THRESHOLDS) == Progress(
        name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1
    )


def test_issue_closed_within_the_window_counts():
    activity = Activity("octocat", (), (issue(timedelta(minutes=1)),))
    assert evaluate(activity, THRESHOLDS) == Progress(
        name="quickdraw", count=1, tier=1, next_threshold=None, remaining=None
    )


def test_boundary_exactly_five_minutes_counts():
    activity = Activity("octocat", (), (issue(FIVE_MINUTES),))
    assert evaluate(activity, THRESHOLDS).count == 1


def test_just_over_the_boundary_does_not_count():
    activity = Activity("octocat", (), (issue(FIVE_MINUTES + timedelta(seconds=1)),))
    assert evaluate(activity, THRESHOLDS).count == 0


def test_still_open_items_do_not_count():
    activity = Activity("octocat", (pull_request(None),), (issue(None),))
    assert evaluate(activity, THRESHOLDS).count == 0


def test_closed_before_opened_does_not_count():
    activity = Activity("octocat", (), (issue(timedelta(minutes=-1)),))
    assert evaluate(activity, THRESHOLDS).count == 0


def test_issues_and_pull_requests_both_count():
    activity = Activity(
        "octocat", (pull_request(timedelta(minutes=2)),), (issue(timedelta(minutes=1)),)
    )
    assert evaluate(activity, THRESHOLDS) == Progress(
        name="quickdraw", count=2, tier=1, next_threshold=None, remaining=None
    )


def test_thresholds_come_from_the_caller():
    activity = Activity(
        "octocat",
        (
            pull_request(timedelta(minutes=2), number=2),
            pull_request(timedelta(minutes=3), number=3),
        ),
        (issue(timedelta(minutes=1)),),
    )
    assert evaluate(activity, [1, 3]) == Progress(
        name="quickdraw", count=3, tier=2, next_threshold=None, remaining=None
    )
