"""Local, append-only snapshots of a user's progress.

One JSON object per line, so a run that is interrupted can never leave the
earlier records unreadable. Nothing here touches the network.
"""

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from questlog.models import Progress

ENV_VAR = "QUESTLOG_HISTORY"
_APP_DIR = "questlog"
_FILE_NAME = "history.jsonl"


class HistoryError(ValueError):
    """The local history file could not be read or written."""


@dataclass(frozen=True)
class Snapshot:
    """One recorded run: what a login stood on, and when."""

    at: datetime
    login: str
    progress: tuple[Progress, ...]

    def __post_init__(self) -> None:
        if self.at.utcoffset() != timedelta(0):
            raise HistoryError(f"Snapshot.at must be a UTC datetime, got {self.at!r}")


@dataclass(frozen=True)
class Change:
    """How one achievement moved between the first and latest snapshot.

    An achievement is tracked from the first snapshot that mentions it to the
    last one that mentions it, so a tier that appears or stops appearing later
    is still reported.
    """

    name: str
    first_count: int
    latest_count: int
    first_at: datetime
    latest_at: datetime

    @property
    def delta(self) -> int:
        """How much the count moved; zero means nothing changed."""
        return self.latest_count - self.first_count


def default_path() -> Path:
    """Where snapshots live unless ``QUESTLOG_HISTORY`` says otherwise."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override)
    state = os.environ.get("XDG_STATE_HOME")
    base = Path(state) if state else Path.home() / ".local" / "state"
    return base / _APP_DIR / _FILE_NAME


def append(path: Path, login: str, progress: list[Progress], at: datetime) -> None:
    """Add one snapshot to the end of the file, creating parents as needed."""
    record = {
        "at": at.astimezone(UTC).isoformat(),
        "login": login,
        "progress": [asdict(item) for item in progress],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError as exc:
        raise HistoryError(f"Could not write the history file: {exc}") from exc


def _progress(item: object) -> Progress:
    if not isinstance(item, dict):
        raise HistoryError("A snapshot entry is not an object.")
    try:
        return Progress(**item)
    except TypeError as exc:
        raise HistoryError(f"A snapshot entry has the wrong fields: {exc}") from exc


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise HistoryError("A snapshot has no usable timestamp.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HistoryError(f"A snapshot timestamp is not a date: {value!r}") from exc
    if parsed.utcoffset() is None:
        raise HistoryError(f"A snapshot timestamp has no timezone: {value!r}")
    return parsed.astimezone(UTC)


def load(path: Path, login: str) -> list[Snapshot]:
    """Return one login's snapshots, oldest first.

    A missing file is an empty history, not an error. A line that is present
    but unreadable raises, because quietly dropping it would let the report
    disagree with what is on disk.
    """
    if not path.exists():
        return []
    snapshots: list[Snapshot] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HistoryError(
                f"Line {number} of the history file is not valid JSON: {exc}"
            ) from exc
        if not isinstance(record, dict) or record.get("login") != login:
            continue
        items = record.get("progress")
        if not isinstance(items, list):
            raise HistoryError(f"Line {number} of the history file has no progress list.")
        snapshots.append(
            Snapshot(_timestamp(record.get("at")), login, tuple(_progress(i) for i in items))
        )
    return sorted(snapshots, key=lambda item: item.at)


def changes(snapshots: list[Snapshot]) -> list[Change]:
    """Compare the first and latest snapshot of each achievement."""
    first: dict[str, tuple[datetime, int]] = {}
    latest: dict[str, tuple[datetime, int]] = {}
    order: list[str] = []
    for snapshot in snapshots:
        for item in snapshot.progress:
            if item.name not in first:
                first[item.name] = (snapshot.at, item.count)
                order.append(item.name)
            latest[item.name] = (snapshot.at, item.count)
    return [
        Change(
            name=name,
            first_count=first[name][1],
            latest_count=latest[name][1],
            first_at=first[name][0],
            latest_at=latest[name][0],
        )
        for name in order
    ]
