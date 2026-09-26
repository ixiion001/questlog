"""One module per achievement.

Each module defines ``NAME`` (its key in ``config/achievements.yaml``) and
``evaluate(activity: Activity, thresholds: list[int]) -> Progress``.
Rules are pure functions: no I/O.
"""
