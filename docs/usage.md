# Using questlog

`questlog` shows how far you are toward each GitHub achievement tier. It
reads your activity through the GitHub CLI and never writes anything to
GitHub.

## Before you start

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).
- The [GitHub CLI](https://cli.github.com/) (`gh`), logged in:

  ```sh
  gh auth login
  gh auth status
  ```

  `questlog` uses that session and doesn't handle tokens itself.

## Install

From a checkout:

```sh
uv tool install .      # puts `questlog` on your PATH
# or, without installing:
uv run questlog --help
```

## Commands

### `questlog status`

Shows your progress on every tracked achievement:

```console
$ questlog status
[ ] Pull Shark (Tier 1): 3/16 (13 remaining)
```

Each line shows:

- `[ ]` or `[x]`: `[x]` means every tier is reached.
- The achievement's name and the highest tier you have reached (`no tier yet`
  before the first one).
- Your count and the next tier's threshold, for example `3/16`. A completed
  achievement shows the count followed by `(completed)`.
- How many more you need for the next tier.

Options:

| Option | Effect |
| --- | --- |
| `--user LOGIN` | Check another account. Without it, `questlog` asks `gh` which account you are logged in as. |
| `--json` | Print the same data as JSON (see below). |

Achievements listed in the configuration whose rule isn't implemented yet are
skipped, with a note on stderr:

```text
Note: rule module 'questlog.rules.yolo' not available; skipping.
```

### `questlog explain NAME`

Prints what an achievement counts and its tier thresholds. `NAME` is the key
(`pull_shark`) or the label (`"Pull Shark"`), in any case:

```console
$ questlog explain pull_shark
Pull Shark (pull_shark)
Pull requests you opened that were merged.

Tiers:
  Tier 1: 2
  Tier 2: 16
  Tier 3: 128
  Tier 4: 1024
```

## JSON output

`questlog status --json` prints a list with one object per achievement:

```json
[
  {
    "name": "pull_shark",
    "count": 3,
    "tier": 1,
    "next_threshold": 16,
    "remaining": 13
  }
]
```

| Field | Meaning |
| --- | --- |
| `name` | Achievement key, as in `achievements.yaml`. |
| `count` | What the rule counted, for example merged pull requests. |
| `tier` | Number of tiers reached; `0` means none yet. |
| `next_threshold` | Count needed for the next tier; `null` once all are reached. |
| `remaining` | `next_threshold - count`; `null` once all are reached. |

## What gets counted

- `questlog` searches pull requests and closed issues **authored by** the
  account. It can only see what your `gh` login can see. For your own account
  that includes private repositories you have access to; for `--user` it is
  mostly public activity.
- GitHub search returns at most 1,000 results per query, so `questlog` splits
  the search into time windows below that limit. Large histories take a few
  more requests but are counted in full.
- If GitHub returns incomplete or inconsistent data, `questlog` stops with an
  error rather than reporting a partial count.
- GitHub may show an achievement on your profile some time after you reach a
  threshold, and it can change its rules without notice. The thresholds live
  in `src/questlog/achievements.yaml`.

## Exit codes and errors

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Something went wrong; the reason is on stderr. |
| `2` | The command line was invalid (unknown command or option). |

Common errors:

| Message | What to do |
| --- | --- |
| `GitHub CLI 'gh' is missing.` | Install `gh`. |
| `GitHub authentication failed.` | Run `gh auth login`. |
| `GitHub API rate limit reached.` | Wait for the limit to reset, then retry. |
| `Enter a GitHub login using letters, numbers and hyphens.` | Check the value passed to `--user`. |
| `Unknown achievement: 'NAME'. Available: ...` | Use one of the listed keys. |
