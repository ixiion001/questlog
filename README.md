# questlog

A read-only quest log for your GitHub achievements. `questlog` reads your
activity through the [GitHub CLI](https://cli.github.com/) and shows, for each
achievement, where you stand, the next tier and how far away it is.

> Status: early. The commands below are being built.

## Usage

```sh
questlog status            # progress on every tracked achievement
questlog status --json     # the same, as JSON
questlog explain pull_shark
```

`questlog` never writes to GitHub. It needs `gh` installed and logged in.

## Development

```sh
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

Tiers live in `src/questlog/achievements.yaml`, so a rule change on GitHub's side is
a config edit. Tests use recorded API responses in `tests/fixtures/` and never
touch the network.

## License

MIT
