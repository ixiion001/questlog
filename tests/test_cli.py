import importlib
import json
import subprocess
import sys
import types

from questlog import __version__
from questlog.cli import main
from questlog.models import Activity, Progress


def test_main_empty_argv_shows_help(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "questlog" in captured.out
    assert "status" in captured.out
    assert "explain" in captured.out


def test_version_flag(capsys):
    ret = main(["--version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"questlog {__version__}"


def test_python_m_questlog_shows_help():
    result = subprocess.run(
        [sys.executable, "-m", "questlog"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage: questlog" in result.stdout


def test_python_m_questlog_exit_code_on_error():
    result = subprocess.run(
        [sys.executable, "-m", "questlog", "explain", "nonexistent"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Unknown achievement: 'nonexistent'" in result.stderr


def test_explain_valid(capsys):
    ret = main(["explain", "pull_shark"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Pull Shark (pull_shark)" in captured.out
    assert "Pull requests you opened that were merged." in captured.out
    assert "Tier 1: 2" in captured.out
    assert "Tier 4: 1024" in captured.out


def test_explain_case_insensitive(capsys):
    ret = main(["explain", "YOLO"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "YOLO (yolo)" in captured.out
    assert "Tier 1: 1" in captured.out


def test_explain_unknown(capsys):
    ret = main(["explain", "nonexistent"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Unknown achievement: 'nonexistent'" in captured.err


def test_explain_config_load_error(monkeypatch, capsys):
    def failing_load():
        raise ValueError("corrupt config")

    monkeypatch.setattr("questlog.cli.load_achievements", failing_load)
    ret = main(["explain", "pull_shark"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error loading achievements configuration: ValueError: corrupt config" in captured.err


def test_status_with_explicit_user(monkeypatch, capsys):
    recorded_calls = []

    def fake_run(args):
        recorded_calls.append(args)
        return {}

    def fake_fetch_activity(login, run=None):
        assert login == "testuser"
        return Activity(login, (), ())

    monkeypatch.setattr("questlog.cli.fetch_activity", fake_fetch_activity)

    dummy_rule = types.ModuleType("questlog.rules.pull_shark")
    dummy_rule.evaluate = lambda act, thresh: Progress("pull_shark", 3, 1, 16, 13)
    monkeypatch.setitem(sys.modules, "questlog.rules.pull_shark", dummy_rule)

    ret = main(["status", "--user", "testuser"], run=fake_run)
    assert ret == 0
    captured = capsys.readouterr()
    assert "[ ] Pull Shark (Tier 1): 3/16 (13 remaining)\n" in captured.out
    assert "[ ] YOLO (no tier yet): 0/1 (1 remaining)\n" in captured.out
    assert "questlog.rules.yolo' not available" not in captured.err


def test_status_skips_missing_rule_module_with_a_note(monkeypatch, capsys):
    def fake_run(args):
        return {}

    def fake_fetch_activity(login, run=None):
        return Activity(login, (), ())

    monkeypatch.setattr("questlog.cli.fetch_activity", fake_fetch_activity)

    dummy_rule = types.ModuleType("questlog.rules.pull_shark")
    dummy_rule.evaluate = lambda act, thresh: Progress("pull_shark", 3, 1, 16, 13)
    monkeypatch.setitem(sys.modules, "questlog.rules.pull_shark", dummy_rule)

    real_import = importlib.import_module

    def fake_import(name):
        if name == "questlog.rules.yolo":
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import(name)

    monkeypatch.setattr("questlog.cli.importlib", types.SimpleNamespace(import_module=fake_import))

    ret = main(["status", "--user", "testuser"], run=fake_run)
    assert ret == 0
    captured = capsys.readouterr()
    assert "[ ] Pull Shark (Tier 1): 3/16 (13 remaining)\n" in captured.out
    assert "Note: rule module 'questlog.rules.yolo' not available; skipping.\n" in captured.err


def test_status_json(monkeypatch, capsys):
    def fake_run(args):
        return {}

    def fake_fetch_activity(login, run=None):
        return Activity(login, (), ())

    monkeypatch.setattr("questlog.cli.fetch_activity", fake_fetch_activity)

    dummy_rule = types.ModuleType("questlog.rules.yolo")
    dummy_rule.evaluate = lambda act, thresh: Progress("yolo", 1, 1, None, None)
    monkeypatch.setitem(sys.modules, "questlog.rules.yolo", dummy_rule)

    ret = main(["status", "--user", "testuser", "--json"], run=fake_run)
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    item = next(x for x in data if x["name"] == "yolo")
    assert item["count"] == 1
    assert item["tier"] == 1
    assert item["next_threshold"] is None


def test_status_default_user_via_gh_api(monkeypatch, capsys):
    def fake_run(args):
        if args == ["api", "user"]:
            return {"login": "detected_user"}
        return {}

    fetched_login = None

    def fake_fetch_activity(login, run=None):
        nonlocal fetched_login
        fetched_login = login
        return Activity(login, (), ())

    monkeypatch.setattr("questlog.cli.fetch_activity", fake_fetch_activity)

    ret = main(["status"], run=fake_run)
    assert ret == 0
    assert fetched_login == "detected_user"


def test_status_config_load_error(monkeypatch, capsys):
    def failing_load():
        raise ValueError("config file missing")

    monkeypatch.setattr("questlog.cli.load_achievements", failing_load)
    ret = main(["status"])
    assert ret == 1
    captured = capsys.readouterr()
    assert (
        "Error loading achievements configuration: ValueError: config file missing" in captured.err
    )


def test_status_gh_user_error(capsys):
    def failing_run(args):
        raise RuntimeError("gh auth required")

    ret = main(["status"], run=failing_run)
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error determining GitHub user: RuntimeError: gh auth required" in captured.err


def test_status_bare_exception_formatting(capsys):
    def failing_run(args):
        raise RuntimeError()

    ret = main(["status"], run=failing_run)
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error determining GitHub user: RuntimeError\n" in captured.err


def test_status_fetch_activity_error(monkeypatch, capsys):
    def fake_run(args):
        return {}

    def failing_fetch(login, run=None):
        raise RuntimeError("API failure")

    monkeypatch.setattr("questlog.cli.fetch_activity", failing_fetch)

    ret = main(["status", "--user", "testuser"], run=fake_run)
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error fetching activity for 'testuser': RuntimeError: API failure" in captured.err


def test_status_rule_missing_evaluate_function(monkeypatch, capsys):
    def fake_run(args):
        return {}

    def fake_fetch(login, run=None):
        return Activity(login, (), ())

    monkeypatch.setattr("questlog.cli.fetch_activity", fake_fetch)

    # Module exists but has no evaluate function
    bad_rule = types.ModuleType("questlog.rules.pull_shark")
    monkeypatch.setitem(sys.modules, "questlog.rules.pull_shark", bad_rule)

    ret = main(["status", "--user", "testuser"], run=fake_run)
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error evaluating rules: AttributeError:" in captured.err
    assert "has no callable 'evaluate' function" in captured.err
