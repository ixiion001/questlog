"""Data passed between the GitHub reader, the rules and the report.

All datetimes are timezone-aware UTC.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PullRequest:
    repo: str
    number: int
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None
    reviewed: bool


@dataclass(frozen=True)
class Issue:
    repo: str
    number: int
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class Activity:
    login: str
    pull_requests: tuple[PullRequest, ...]
    issues: tuple[Issue, ...]


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
