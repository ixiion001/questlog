# Adding an achievement

An achievement in `questlog` has two parts:

- an entry in `src/questlog/achievements.yaml` with its label, tiers and a
  one-line summary, and
- a rule module in `src/questlog/rules/` that counts the matching activity.

`questlog status` loads every entry in the YAML file and runs the rule module
with the same key. `src/questlog/rules/pull_shark.py` and
`tests/rules/test_pull_shark.py` are a complete example.

## 1. Add the entry

```yaml
# src/questlog/achievements.yaml
my_key:
  label: My Achievement
  thresholds: [1, 10, 50]
  summary: One sentence on what counts.
```

- The key is lowercase with underscores. It is the rule module's file name
  and the `name` in JSON output.
- `thresholds` are whole numbers, positive and strictly increasing. A
  one-time achievement has a single threshold, `[1]`.
- The loader rejects a missing field or bad thresholds with an error that
  names the key. `tests/test_config.py` loads the shipped file, so a mistake
  fails the tests.

If GitHub later changes a tier, only this file changes.

## 2. Write the rule

```python
# src/questlog/rules/my_key.py
"""My Achievement: one sentence on what counts."""

from collections.abc import Sequence

from questlog.models import Activity, Progress
from questlog.rules._tiers import progress

NAME = "my_key"


def evaluate(activity: Activity, thresholds: Sequence[int]) -> Progress:
    """Count the matching items in ``activity`` against ``thresholds``."""
    count = sum(1 for pr in activity.pull_requests if ...)
    return progress(NAME, count, thresholds)
```

Rules follow three conventions:

- **Pure.** A rule reads only the `Activity` it is given: no network, files
  or clock. All GitHub access is in `src/questlog/github.py`.
- **Thresholds come from the caller.** Never hard-code tiers in the rule.
  `progress()` in `rules/_tiers.py` turns a count into `tier`,
  `next_threshold` and `remaining`.
- **Only the data in `models.py`.** `Activity` holds the user's authored pull
  requests (`created_at`, `closed_at`, `merged_at`, `reviewed`) and closed
  issues (`created_at`, `closed_at`). All timestamps are UTC. If a rule needs
  data the reader doesn't collect yet, extend `models.py` and `github.py`
  first, in their own change.

If a count can only approximate GitHub's rule with this data, say so in the
module docstring and the summary.

## 3. Test it

Put tests in `tests/rules/test_my_key.py` and build `Activity` values by
hand, as `tests/rules/test_pull_shark.py` does. Cover at least:

- no activity (tier 0),
- items that must *not* count,
- a count exactly on a threshold,
- all tiers reached (`next_threshold` and `remaining` are `None`),
- thresholds passed in by the test, not read from the YAML file.

Tests never call GitHub. If you change the reader, record real `gh api`
responses under `tests/fixtures/` as described in
`tests/fixtures/README.md`.

## 4. Check

```sh
uv run pytest
uv run ruff check && uv run ruff format --check
uv run questlog explain my_key
```

`questlog status` prints a note on stderr for any entry whose rule module is
missing, and fails if the module has no `evaluate` function.
