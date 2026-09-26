import pytest

from questlog.config import Achievement, load_achievements


def test_shipped_file_loads():
    achievements = load_achievements()
    assert achievements["pull_shark"] == Achievement(
        "pull_shark",
        "Pull Shark",
        (2, 16, 128, 1024),
        "Pull requests you opened that were merged.",
    )
    assert {"yolo", "quickdraw"} <= achievements.keys()


def test_missing_field_is_an_error():
    with pytest.raises(ValueError, match="broken: needs label"):
        load_achievements("broken: {label: X, thresholds: [1]}")


@pytest.mark.parametrize("thresholds", ["[]", "[0, 1]", "[2, 2]", "[5, 3]"])
def test_bad_thresholds_are_an_error(thresholds):
    text = f"bad: {{label: X, summary: Y, thresholds: {thresholds}}}"
    with pytest.raises(ValueError, match="strictly increasing"):
        load_achievements(text)


def test_top_level_must_be_a_mapping():
    with pytest.raises(ValueError, match="must be a mapping"):
        load_achievements("- pull_shark")


@pytest.mark.parametrize("thresholds", ["[1.9, 3]", "[true, 2]", "[x]"])
def test_thresholds_must_be_whole_numbers(thresholds):
    text = f"bad: {{label: X, summary: Y, thresholds: {thresholds}}}"
    with pytest.raises(ValueError, match="bad: thresholds must be whole numbers"):
        load_achievements(text)
