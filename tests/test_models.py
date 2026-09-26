import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from questlog.models import Activity, Issue, Progress, PullRequest

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_models_are_frozen():
    progress = Progress(name="pull_shark", count=3, tier=1, next_threshold=16, remaining=13)
    with pytest.raises(dataclasses.FrozenInstanceError):
        progress.count = 4


def test_activity_holds_tuples():
    pr = PullRequest("o/r", 1, T0, T0, T0, reviewed=True)
    issue = Issue("o/r", 2, T0, None)
    activity = Activity("octocat", (pr,), (issue,))
    assert activity.pull_requests[0].merged_at == T0
    assert activity.issues[0].closed_at is None


def test_contract_fields():
    fields = {
        cls.__name__: [f.name for f in dataclasses.fields(cls)]
        for cls in (PullRequest, Issue, Activity, Progress)
    }
    assert fields == {
        "PullRequest": ["repo", "number", "created_at", "closed_at", "merged_at", "reviewed"],
        "Issue": ["repo", "number", "created_at", "closed_at"],
        "Activity": ["login", "pull_requests", "issues"],
        "Progress": ["name", "count", "tier", "next_threshold", "remaining"],
    }


@pytest.mark.parametrize(
    "stamp",
    [datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))],
    ids=["naive", "utc+2"],
)
def test_timestamps_must_be_utc(stamp):
    with pytest.raises(ValueError, match="PullRequest.merged_at must be a UTC datetime"):
        PullRequest("o/r", 1, T0, T0, stamp, reviewed=False)
    with pytest.raises(ValueError, match="Issue.created_at must be a UTC datetime"):
        Issue("o/r", 2, stamp, None)
