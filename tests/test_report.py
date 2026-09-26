import json

from questlog.models import Progress
from questlog.report import render_json, render_text


def test_render_text_empty():
    assert render_text([]) == "No progress to report.\n"


def test_render_text_in_progress():
    progress = [
        Progress(name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1),
        Progress(name="pull_shark", count=3, tier=1, next_threshold=16, remaining=13),
    ]
    output = render_text(progress)
    expected = (
        "[ ] quickdraw (Tier 0): 0/1 (1 remaining)\n[ ] pull_shark (Tier 1): 3/16 (13 remaining)\n"
    )
    assert output == expected


def test_render_text_completed():
    progress = [
        Progress(name="yolo", count=1, tier=1, next_threshold=None, remaining=None),
        Progress(name="pull_shark", count=1024, tier=4, next_threshold=None, remaining=None),
    ]
    output = render_text(progress)
    expected = "[x] yolo (Tier 1): 1 (completed)\n[x] pull_shark (Tier 4): 1024 (completed)\n"
    assert output == expected


def test_render_json_empty():
    output = render_json([])
    assert output == "[]\n"
    assert json.loads(output) == []


def test_render_json_data():
    progress = [
        Progress(name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1),
        Progress(name="yolo", count=1, tier=1, next_threshold=None, remaining=None),
    ]
    output = render_json(progress)
    parsed = json.loads(output)
    assert parsed == [
        {
            "name": "quickdraw",
            "count": 0,
            "tier": 0,
            "next_threshold": 1,
            "remaining": 1,
        },
        {
            "name": "yolo",
            "count": 1,
            "tier": 1,
            "next_threshold": None,
            "remaining": None,
        },
    ]
