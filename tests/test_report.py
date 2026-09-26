import json
import re

from questlog.models import Progress
from questlog.report import BAR_WIDTH, render_json, render_text

BAR_PATTERN = re.compile(r"\[[#-]+\]")


def test_render_text_empty():
    assert render_text([]) == "No progress to report.\n"


def test_render_text_in_progress():
    progress = [
        Progress(name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1),
        Progress(name="pull_shark", count=3, tier=1, next_threshold=16, remaining=13),
    ]
    output = render_text(progress)
    expected = (
        "[ ] quickdraw (no tier yet): [--------------------] 0/1 (1 remaining)\n"
        "[ ] pull_shark (Tier 1): [###-----------------] 3/16 (13 remaining)\n"
    )
    assert output == expected


def test_render_text_with_labels():
    progress = [
        Progress(name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1),
        Progress(name="pull_shark", count=3, tier=1, next_threshold=16, remaining=13),
    ]
    labels = {"quickdraw": "Quickdraw", "pull_shark": "Pull Shark"}
    output = render_text(progress, labels=labels)
    expected = (
        "[ ] Quickdraw (no tier yet): [--------------------] 0/1 (1 remaining)\n"
        "[ ] Pull Shark (Tier 1): [###-----------------] 3/16 (13 remaining)\n"
    )
    assert output == expected


def test_render_text_completed():
    progress = [
        Progress(name="yolo", count=1, tier=1, next_threshold=None, remaining=None),
        Progress(name="pull_shark", count=1024, tier=4, next_threshold=None, remaining=None),
    ]
    output = render_text(progress)
    expected = (
        "[x] yolo (Tier 1): [####################] 1 (completed)\n"
        "[x] pull_shark (Tier 4): [####################] 1024 (completed)\n"
    )
    assert output == expected


def test_bars_are_fixed_width_and_use_bar_characters():
    progress = [
        Progress(name="quickdraw", count=0, tier=0, next_threshold=1, remaining=1),
        Progress(name="pull_shark", count=3, tier=1, next_threshold=16, remaining=13),
        Progress(name="pull_shark", count=127, tier=3, next_threshold=128, remaining=1),
        Progress(name="yolo", count=1, tier=1, next_threshold=None, remaining=None),
    ]
    bars = [line.split(": ")[1].split(" ")[0] for line in render_text(progress).splitlines()]
    assert all(BAR_PATTERN.fullmatch(bar) for bar in bars)
    assert {len(bar) for bar in bars} == {BAR_WIDTH + 2}


def test_bar_fill_grows_with_count():
    def fill(count: int) -> int:
        row = Progress(name="pull_shark", count=count, tier=1, next_threshold=16, remaining=1)
        return render_text([row]).count("#")

    assert fill(0) == 0
    assert fill(4) <= fill(8) < fill(15) <= BAR_WIDTH


def test_bar_fill_is_clamped():
    over = Progress(name="pull_shark", count=32, tier=2, next_threshold=16, remaining=0)
    assert render_text([over]).count("#") == BAR_WIDTH


def test_bar_never_fills_completely_before_tier_is_reached():
    # 127/128 (99.2%) must draw 19 cells, not 20: only a reached threshold is full
    one_away = Progress(name="pull_shark", count=127, tier=3, next_threshold=128, remaining=1)
    assert render_text([one_away]).count("#") == BAR_WIDTH - 1


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
