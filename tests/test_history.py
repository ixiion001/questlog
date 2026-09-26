"""Tests for the local progress history: append, load and diff."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from questlog.history import (
    ENV_VAR,
    Change,
    HistoryError,
    Snapshot,
    append,
    changes,
    default_path,
    load,
)
from questlog.models import Progress

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
PULL_SHARK = Progress("pull_shark", 2, 1, 16, 14)
GALAXY = Progress("galaxy_brain", 0, 0, 2, 2)
DONE = Progress("yolo", 194, 1, None, None)


def test_missing_file_is_an_empty_history(tmp_path):
    assert load(tmp_path / "nope.jsonl", "octocat") == []


def test_append_then_load_round_trips(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK, GALAXY], T0)
    append(path, "octocat", [PULL_SHARK, GALAXY], T1)
    snapshots = load(path, "octocat")
    assert [item.at for item in snapshots] == [T0, T1]
    assert snapshots[0].progress == (PULL_SHARK, GALAXY)
    assert snapshots[1].login == "octocat"


def test_append_creates_missing_parents(tmp_path):
    path = tmp_path / "deep" / "nested" / "history.jsonl"
    append(path, "octocat", [GALAXY], T0)
    assert path.exists()
    assert load(path, "octocat")[0].progress == (GALAXY,)


def test_snapshots_are_one_json_object_per_line(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    append(path, "octocat", [DONE], T1)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {
        "at": "2026-01-01T00:00:00+00:00",
        "login": "octocat",
        "progress": [
            {
                "name": "pull_shark",
                "count": 2,
                "tier": 1,
                "next_threshold": 16,
                "remaining": 14,
            }
        ],
    }


def test_load_filters_by_login_so_accounts_share_one_file(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    append(path, "hubot", [GALAXY], T0)
    assert [item.progress[0].name for item in load(path, "octocat")] == ["pull_shark"]
    assert [item.progress[0].name for item in load(path, "hubot")] == ["galaxy_brain"]


def test_load_returns_oldest_first_even_when_appended_out_of_order(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [DONE], T1)
    append(path, "octocat", [PULL_SHARK], T0)
    assert [item.at for item in load(path, "octocat")] == [T0, T1]


def test_timestamps_are_normalised_to_utc(tmp_path):
    path = tmp_path / "history.jsonl"
    append(
        path,
        "octocat",
        [PULL_SHARK],
        datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=2))),
    )
    # 09:00 at +02:00 is 07:00 UTC.
    assert load(path, "octocat")[0].at == datetime(2026, 1, 1, 7, tzinfo=UTC)


def test_a_flat_period_is_kept_rather_than_hidden(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    append(path, "octocat", [PULL_SHARK], T1)
    snapshots = load(path, "octocat")
    assert len(snapshots) == 2
    assert changes(snapshots) == [Change("pull_shark", 2, 2, T0, T1)]
    assert changes(snapshots)[0].delta == 0


def test_changes_report_first_latest_and_dates(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK, GALAXY], T0)
    append(path, "octocat", [Progress("pull_shark", 20, 2, 128, 108), GALAXY], T1)
    assert changes(load(path, "octocat")) == [
        Change("pull_shark", 2, 20, T0, T1),
        Change("galaxy_brain", 0, 0, T0, T1),
    ]


def test_an_achievement_that_appears_later_is_still_reported(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    append(path, "octocat", [PULL_SHARK, GALAXY], T1)
    # Tracked from the first snapshot that mentions it, so it is not dropped.
    assert changes(load(path, "octocat")) == [
        Change("pull_shark", 2, 2, T0, T1),
        Change("galaxy_brain", 0, 0, T1, T1),
    ]


def test_an_achievement_that_stops_appearing_keeps_its_last_known_value(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK, GALAXY], T0)
    append(path, "octocat", [PULL_SHARK], T1)
    assert changes(load(path, "octocat"))[1] == Change("galaxy_brain", 0, 0, T0, T0)


def test_no_snapshots_yet_produces_no_changes(tmp_path):
    assert changes(load(tmp_path / "history.jsonl", "octocat")) == []


def test_snapshot_at_must_be_utc():
    with pytest.raises(HistoryError, match="must be a UTC datetime"):
        Snapshot(datetime(2026, 1, 1), "octocat", ())
    # A fixed offset, not the machine's: ``astimezone()`` is UTC on a UTC host,
    # which would make this test pass on one machine and fail on another.
    with pytest.raises(HistoryError, match="must be a UTC datetime"):
        Snapshot(datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=2))), "octocat", ())


def test_a_corrupt_line_is_reported_rather_than_dropped(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    path.write_text(path.read_text() + "{not json\n")
    with pytest.raises(HistoryError, match="Line 2 .* is not valid JSON"):
        load(path, "octocat")


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "history.jsonl"
    append(path, "octocat", [PULL_SHARK], T0)
    path.write_text(path.read_text() + "\n\n")
    assert len(load(path, "octocat")) == 1


@pytest.mark.parametrize(
    "line",
    [
        json.dumps({"at": "2026-01-01T00:00:00+00:00", "login": "octocat"}),
        json.dumps({"at": "2026-01-01T00:00:00+00:00", "login": "octocat", "progress": {}}),
        json.dumps({"at": "2026-01-01T00:00:00+00:00", "login": "octocat", "progress": [7]}),
        json.dumps(
            {"at": "2026-01-01T00:00:00+00:00", "login": "octocat", "progress": [{"name": "x"}]}
        ),
    ],
)
def test_incomplete_snapshots_raise_instead_of_reporting_nothing(tmp_path, line):
    path = tmp_path / "history.jsonl"
    path.write_text(line + "\n")
    with pytest.raises(HistoryError):
        load(path, "octocat")


@pytest.mark.parametrize("at", ["not-a-date", "2026-01-01T00:00:00"])
def test_unusable_timestamps_raise(tmp_path, at):
    path = tmp_path / "history.jsonl"
    path.write_text(json.dumps({"at": at, "login": "octocat", "progress": []}) + "\n")
    with pytest.raises(HistoryError):
        load(path, "octocat")


def test_default_path_prefers_the_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "custom.jsonl"))
    assert default_path() == tmp_path / "custom.jsonl"


def test_default_path_uses_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert default_path() == tmp_path / "questlog" / "history.jsonl"


def test_default_path_falls_back_to_local_state(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert default_path() == Path.home() / ".local" / "state" / "questlog" / "history.jsonl"
