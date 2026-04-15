from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_reader.ui.reader_keyboard_nav import (
    KEY_ESCAPE,
    get_alt_escape_key,
    is_escape_key,
    set_alt_escape_key,
)

if TYPE_CHECKING:
    from collections.abc import Generator

_BACKSPACE = 8


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
