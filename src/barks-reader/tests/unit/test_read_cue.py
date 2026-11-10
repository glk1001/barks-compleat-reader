"""Tests for when the story picture says "Read this story"."""

import pytest
from barks_reader.core.read_cue import (
    READ_CUE_ALWAYS,
    READ_CUE_FIRST_FEW,
    READ_CUE_NEVER,
    READ_CUE_OPENS,
    READ_CUE_OPTIONS,
    is_read_cue_shown,
)


def test_the_first_few_is_the_first_option() -> None:
    """The settings panel lists them in this order."""
    assert READ_CUE_OPTIONS == (READ_CUE_FIRST_FEW, READ_CUE_ALWAYS, READ_CUE_NEVER)


@pytest.mark.parametrize(
    ("setting", "opens_left", "shown"),
    [
        (READ_CUE_FIRST_FEW, READ_CUE_OPENS, True),
        (READ_CUE_FIRST_FEW, 1, True),
        (READ_CUE_FIRST_FEW, 0, False),
        (READ_CUE_ALWAYS, 0, True),
        (READ_CUE_ALWAYS, 2, True),
        (READ_CUE_NEVER, 0, False),
        (READ_CUE_NEVER, 2, False),
        ("a value from an older ini", 1, True),
        ("a value from an older ini", 0, False),
    ],
)
def test_the_caption_follows_the_setting_and_the_count(
    setting: str, opens_left: int, shown: bool
) -> None:
    assert is_read_cue_shown(setting, opens_left) is shown
