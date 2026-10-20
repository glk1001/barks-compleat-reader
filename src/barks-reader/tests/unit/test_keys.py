from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_reader.core.keys import (
    KEY_ESCAPE,
    get_alt_escape_key,
    is_escape_key,
    is_escape_key_for_text_input,
    set_alt_escape_key,
)

if TYPE_CHECKING:
    from collections.abc import Generator

_BACKSPACE = 8
_KEY_R = ord("r")


@pytest.fixture(autouse=True)
def _reset_alt_key() -> Generator[None]:
    set_alt_escape_key(0)
    yield
    set_alt_escape_key(0)


def test_real_escape_always_matches() -> None:
    assert is_escape_key(KEY_ESCAPE) is True


def test_alt_escape_defaults_to_unset() -> None:
    assert get_alt_escape_key() == 0
    assert is_escape_key(_BACKSPACE) is False


def test_set_alt_escape_key_enables_match() -> None:
    set_alt_escape_key(_BACKSPACE)
    assert get_alt_escape_key() == _BACKSPACE
    assert is_escape_key(_BACKSPACE) is True
    assert is_escape_key(KEY_ESCAPE) is True
    assert is_escape_key(_BACKSPACE + 1) is False


def test_clearing_alt_escape_key() -> None:
    set_alt_escape_key(_BACKSPACE)
    set_alt_escape_key(0)
    assert get_alt_escape_key() == 0
    assert is_escape_key(_BACKSPACE) is False
    assert is_escape_key(KEY_ESCAPE) is True


def test_alt_escape_accepts_non_int_truthy() -> None:
    set_alt_escape_key(42)
    assert is_escape_key(42) is True


class TestEscapeForTextInput:
    """A text field keeps a letter that doubles as the alternate Escape."""

    def test_real_escape_leaves_the_field(self) -> None:
        assert is_escape_key_for_text_input(KEY_ESCAPE, None) is True
        assert is_escape_key_for_text_input(KEY_ESCAPE, "\x1b") is True

    def test_alt_escape_with_no_character_leaves_the_field(self) -> None:
        set_alt_escape_key(_KEY_R)
        assert is_escape_key_for_text_input(_KEY_R, None) is True
        assert is_escape_key_for_text_input(_KEY_R, "") is True

    def test_alt_escape_typed_as_a_letter_is_text(self) -> None:
        set_alt_escape_key(_KEY_R)
        assert is_escape_key_for_text_input(_KEY_R, "r") is False

    def test_other_keys_are_text(self) -> None:
        set_alt_escape_key(_KEY_R)
        assert is_escape_key_for_text_input(_BACKSPACE, None) is False
