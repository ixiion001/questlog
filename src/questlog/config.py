"""Load the achievement definitions shipped with the package."""

from dataclasses import dataclass
from importlib.resources import files

import yaml


@dataclass(frozen=True)
class Achievement:
    key: str
    label: str
    thresholds: tuple[int, ...]
    summary: str


def load_achievements(text: str | None = None) -> dict[str, Achievement]:
    """Parse ``achievements.yaml`` (or ``text``) into achievements keyed by name.

    Raises ``ValueError`` when an entry is missing a field or its thresholds
    are not positive and strictly increasing.
    """
    if text is None:
        text = files("questlog").joinpath("achievements.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("achievements must be a mapping of name to entry")
    achievements = {}
    for key, entry in data.items():
        try:
            thresholds = tuple(entry["thresholds"])
            achievement = Achievement(key, entry["label"], thresholds, entry["summary"])
        except (KeyError, TypeError) as exc:
            raise ValueError(f"{key}: needs label, thresholds and summary") from exc
        if not all(type(t) is int for t in thresholds):
            raise ValueError(f"{key}: thresholds must be whole numbers")
        if not thresholds or thresholds[0] < 1 or list(thresholds) != sorted(set(thresholds)):
            raise ValueError(f"{key}: thresholds must be positive and strictly increasing")
        achievements[key] = achievement
    return achievements
