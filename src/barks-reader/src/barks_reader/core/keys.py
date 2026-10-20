"""The key codes the app navigates by, and the user's alternate Escape key.

Kivy-free: the codes are SDL2's, which Kivy passes through unchanged, so any
module may test a key against them without importing Kivy. The six keys a remote
has (Escape, Return, Up, Down, Left, Right) drive the whole app; the rest are
desktop extras.
"""

from __future__ import annotations

# Kivy SDL2 key codes for navigation keys.
KEY_TAB = 9
KEY_ENTER = 13
KEY_ESCAPE = 27
KEY_SPACE = 32
KEY_F = ord("f")
KEY_UP = 273
KEY_DOWN = 274
KEY_RIGHT = 275
KEY_LEFT = 276
KEY_NUMPAD_ENTER = 271
KEY_PAGE_UP = 280
KEY_PAGE_DOWN = 281
KEY_DELETE = 127

_alt_escape_key: int = 0


def set_alt_escape_key(key: int) -> None:
    """Set the user-configured alternate Escape keycode (0 = unset)."""
    global _alt_escape_key  # noqa: PLW0603
    _alt_escape_key = int(key) if key else 0


def get_alt_escape_key() -> int:
    """Return the current alternate Escape keycode (0 = unset)."""
    return _alt_escape_key


def is_escape_key(key: int) -> bool:
    """Return True if key is real Escape or the user-configured alternate Escape."""
    return key == KEY_ESCAPE or (_alt_escape_key != 0 and key == _alt_escape_key)


def is_escape_key_for_text_input(key: int, codepoint: str | None) -> bool:
    """Return True if `key` should act as Escape while a text field holds the keyboard.

    Real Escape always does. The alternate Escape is a bare keycode captured from a
    remote, and the very same keycode is an ordinary letter on a keyboard - the default
    114 is "r". A press carrying a printable character is therefore text the field
    should receive, not a request to leave it: without this, anyone whose alternate
    Escape is a letter cannot type a word containing it into any search box. The letter
    is swallowed and the box is exited instead.

    Only the text-input case is narrowed. Everywhere else the alternate Escape keeps
    working exactly as before, so a remote loses nothing outside a focused field.

    Args:
        key: The keycode.
        codepoint: The character the press produced, if any.

    """
    if key == KEY_ESCAPE:
        return True
    return is_escape_key(key) and not codepoint
