"""Tests for when the story picture says "Read this story"."""

import pytest
from barks_reader.core.read_cue import (
    READ_CUE_ALWAYS,
    READ_CUE_FIRST_FEW,
    READ_CUE_NEVER,
    READ_CUE_OPENS,
    READ_CUE_OPTIONS,
    count_comic_opened,
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


class _Store:
    """A count kept in memory, with every save noted."""

    def __init__(self, opens_left: int = 0) -> None:
        self.opens_left = opens_left
        self.saved: list[int] = []

    def get_read_cue_opens_left(self) -> int:
        return self.opens_left

    def save_read_cue_opens_left(self, opens_left: int) -> None:
        self.opens_left = opens_left
        self.saved.append(opens_left)


class TestCountComicOpened:
    def test_the_first_comic_ever_opened_starts_the_count(self) -> None:
        store = _Store(opens_left=1)  # whatever was there: the count starts afresh

        count_comic_opened(store, first_use=True)

        assert store.saved == [READ_CUE_OPENS]

    def test_each_comic_after_that_takes_one_off_until_none_is_left(self) -> None:
        store = _Store()
        count_comic_opened(store, first_use=True)

        for _ in range(READ_CUE_OPENS + 2):
            count_comic_opened(store, first_use=False)

        assert store.saved == [READ_CUE_OPENS, *reversed(range(READ_CUE_OPENS))]
        assert store.opens_left == 0
        assert not is_read_cue_shown(READ_CUE_FIRST_FEW, store.opens_left)

    def test_with_none_left_nothing_is_saved(self) -> None:
        """An install past its first use before the caption existed has no count."""
        store = _Store(opens_left=0)

        count_comic_opened(store, first_use=False)

        assert store.saved == []
