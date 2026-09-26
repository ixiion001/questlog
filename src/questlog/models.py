"""Data passed between the GitHub reader, the rules and the report.

All datetimes are timezone-aware UTC.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


def _require_utc(obj: object, *names: str) -> None:
    for name in names:
        value = getattr(obj, name)
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError(f"{type(obj).__name__}.{name} must be a UTC datetime, got {value!r}")


@dataclass(frozen=True)
class PullRequest:
    repo: str
    number: int
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None
    reviewed: bool

    def __post_init__(self) -> None:
        _require_utc(self, "created_at", "closed_at", "merged_at")


@dataclass(frozen=True)
class Issue:
    repo: str
    number: int
    created_at: datetime
    closed_at: datetime | None

    def __post_init__(self) -> None:
        _require_utc(self, "created_at", "closed_at")


@dataclass(frozen=True)
class DiscussionAnswer:
    """An answer you wrote in a discussion that GitHub marks as the answer."""

    repo: str
    number: int
    created_at: datetime

    def __post_init__(self) -> None:
        _require_utc(self, "created_at")


@dataclass(frozen=True)
class Activity:
    login: str
    pull_requests: tuple[PullRequest, ...]
    issues: tuple[Issue, ...]
    discussion_answers: tuple[DiscussionAnswer, ...] = ()


@dataclass(frozen=True)
class Progress:
    """Where a user stands on one achievement.

    ``tier`` is the number of thresholds reached (0 = none yet).
    ``next_threshold`` and ``remaining`` are ``None`` once every tier is reached.
    """

    name: str
    count: int
    tier: int
    next_threshold: int | None
    remaining: int | None
