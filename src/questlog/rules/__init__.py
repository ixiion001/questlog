"""One module per achievement.

Each module defines ``NAME`` (its key in ``questlog/achievements.yaml``) and
``evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress``.
Rules are pure functions: no I/O.
"""
