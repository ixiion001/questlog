"""Command line entry point: ``questlog status`` and ``questlog explain NAME``."""

import argparse
import importlib
import sys
from collections.abc import Callable

from questlog import __version__
from questlog.config import Achievement, load_achievements
from questlog.github import fetch_activity, gh_json
from questlog.models import Activity, Progress
from questlog.report import render_json, render_text


def _format_error(exc: Exception) -> str:
    """Format an exception with its type and message, avoiding empty strings."""
    msg = str(exc)
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def evaluate_achievements(
    activity: Activity,
    achievements: dict[str, Achievement],
) -> list[Progress]:
    """Import and evaluate rule modules for each configured achievement."""
    progress_list: list[Progress] = []
    for key, achievement in achievements.items():
        module_name = f"questlog.rules.{key}"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # If the rule module for this achievement is not implemented yet, skip with a note
            if exc.name == module_name:
                sys.stderr.write(f"Note: rule module '{module_name}' not available; skipping.\n")
                continue
            raise
        evaluate_fn = getattr(module, "evaluate", None)
        if not callable(evaluate_fn):
            raise AttributeError(f"Rule module '{module_name}' has no callable 'evaluate' function")
        progress = evaluate_fn(activity, list(achievement.thresholds))
        progress_list.append(progress)
    return progress_list


def select_achievements(
    achievements: dict[str, Achievement],
    only: str | None,
) -> tuple[dict[str, Achievement], list[str]]:
    """Pick the achievements named in ``only`` (in config order) and list unknown keys.

    ``only`` is a comma-separated list of keys, matched case-insensitively with
    surrounding whitespace ignored. ``None`` selects every achievement.
    """
    if only is None:
        return achievements, []
    requested = {key.strip().lower() for key in only.split(",") if key.strip()}
    unknown = sorted(requested - achievements.keys())
    return {key: ach for key, ach in achievements.items() if key in requested}, unknown


def handle_status(
    args: argparse.Namespace,
    run: Callable[[list[str]], dict | list],
) -> int:
    """Handle ``questlog status``."""
    try:
        achievements = load_achievements()
    except Exception as exc:
        sys.stderr.write(f"Error loading achievements configuration: {_format_error(exc)}\n")
        return 1

    if args.only is not None:
        selected, unknown = select_achievements(achievements, args.only)
        if unknown:
            names = ", ".join(repr(key) for key in unknown)
            available = ", ".join(achievements)
            sys.stderr.write(f"Unknown achievement key(s): {names}. Available: {available}\n")
            return 1
        if not selected:
            available = ", ".join(achievements)
            sys.stderr.write(f"No achievements selected. Available: {available}\n")
            return 1
        achievements = selected

    try:
        login = resolve_login(args.user, run)
    except Exception as exc:
        sys.stderr.write(
            f"Error determining GitHub user: {_format_error(exc)}\n"
            "Please specify --user or log in via 'gh auth login'.\n"
        )
        return 1
    if login is None:
        sys.stderr.write(
            "Error: Could not determine GitHub user from 'gh api user'. "
            "Please specify --user or log in via 'gh auth login'.\n"
        )
        return 1

    try:
        activity = fetch_activity(login, run=run)
    except Exception as exc:
        sys.stderr.write(f"Error fetching activity for '{login}': {_format_error(exc)}\n")
        return 1

    try:
        progress_list = evaluate_achievements(activity, achievements)
    except Exception as exc:
        sys.stderr.write(f"Error evaluating rules: {_format_error(exc)}\n")
        return 1

    labels = {ach.key: ach.label for ach in achievements.values()}

    if args.json:
        sys.stdout.write(render_json(progress_list))
    else:
        sys.stdout.write(render_text(progress_list, labels=labels))

    return 0


def resolve_login(
    user: str | None,
    run: Callable[[list[str]], dict | list],
) -> str | None:
    """Return an explicit user or the authenticated ``gh`` login, if available."""
    if user:
        return user
    user_data = run(["api", "user"])
    if isinstance(user_data, dict) and "login" in user_data:
        return str(user_data["login"])
    return None


def handle_explain(
    args: argparse.Namespace,
    run: Callable[[list[str]], dict | list],
) -> int:
    """Handle ``questlog explain NAME``."""
    try:
        achievements = load_achievements()
    except Exception as exc:
        sys.stderr.write(f"Error loading achievements configuration: {_format_error(exc)}\n")
        return 1

    key = args.name.lower()
    ach = achievements.get(key)
    if not ach:
        # Also try matching label
        for a in achievements.values():
            if a.label.lower() == key:
                ach = a
                break

    if not ach:
        available = ", ".join(achievements.keys())
        sys.stderr.write(f"Unknown achievement: '{args.name}'. Available: {available}\n")
        return 1

    lines = [
        f"{ach.label} ({ach.key})",
        ach.summary,
        "",
    ]

    if args.user is not None:
        try:
            activity = fetch_activity(args.user, run=run)
            progress = evaluate_achievements(activity, {ach.key: ach})
        except Exception as exc:
            sys.stderr.write(
                f"Note: could not read progress for '{args.user}': {_format_error(exc)}\n"
            )
        else:
            if progress:
                lines.append("Your progress:")
                labels = {ach.key: ach.label}
                lines.extend(render_text(progress, labels=labels).rstrip("\n").splitlines())
                lines.append("")

    lines.append("Tiers:")
    for i, threshold in enumerate(ach.thresholds, 1):
        lines.append(f"  Tier {i}: {threshold}")

    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="questlog",
        description="A read-only quest log of your GitHub achievement progress.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"questlog {__version__}",
        help="Show the questlog version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser("status", help="Show progress on tracked achievements")
    status_parser.add_argument("--json", action="store_true", help="Output progress as JSON")
    status_parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="GitHub username (defaults to authenticated user via gh)",
    )
    status_parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated achievement keys to show (default: all)",
    )

    explain_parser = subparsers.add_parser("explain", help="Explain an achievement and its tiers")
    explain_parser.add_argument("name", type=str, help="Achievement name or key to explain")
    explain_parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="GitHub username for progress (omit to show tiers without fetching activity)",
    )

    return parser


def main(
    argv: list[str] | None = None,
    run: Callable[[list[str]], dict | list] | None = None,
) -> int:
    """Command-line entry point."""
    if argv is None:
        argv = sys.argv[1:]
    if run is None:
        run = gh_json

    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if args.command == "status":
        return handle_status(args, run=run)
    elif args.command == "explain":
        return handle_explain(args, run=run)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
