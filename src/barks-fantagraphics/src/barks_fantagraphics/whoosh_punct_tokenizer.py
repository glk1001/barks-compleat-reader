import unicodedata
from collections.abc import Generator
from typing import Any

from whoosh.analysis import Token, Tokenizer


class WordWithPunctTokenizer(Tokenizer):
    @staticmethod
    def _is_word_char(c: str) -> bool:
        return unicodedata.category(c)[0] in ("L", "N")

    @classmethod
    def _has_future_word(cls, value: str, start: int, length: int) -> bool:
        j = start
        while j < length:
            if cls._is_word_char(value[j]):
                return True
            if value[j].isspace():
                return False
            j += 1
        return False

    @classmethod
    def _consume_punctuation(cls, value: str, i: int, start_i: int, length: int, ch: str) -> bool:
        """Return True if the punctuation at 'i' should be included in the current token."""
        if ch == "'":
            return True
        if ch == ",":
            # Only allow commas sandwiched between two digits (e.g. 1,000).
            return (
                i > start_i
                and i + 1 < length
                and unicodedata.category(value[i - 1])[0] == "N"
                and unicodedata.category(value[i + 1])[0] == "N"
            )
        # Hyphen or dot: allow if it connects to a future word character.
        if cls._has_future_word(value, i + 1, length):
            return True
        # Allow a trailing dot to complete an acronym like "G.I."
        return (
            ch == "."
            and i > start_i
            and cls._is_word_char(value[i - 1])
            and "." in value[start_i:i]
        )

    @classmethod
    def _scan_token(cls, value: str, start: int, length: int) -> tuple[int, bool]:
        """Scan one token starting at start; return (end_index, saw_word_char)."""
        i = start
        saw_word = False
        while i < length:
            ch = value[i]
            if cls._is_word_char(ch):
                saw_word = True
                i += 1
            elif ch in ("-", ".", "'", ","):
                if cls._consume_punctuation(value, i, start, length, ch):
                    i += 1
                else:
                    break
            else:
                break
        return i, saw_word

    @classmethod
    def _strip_surrounding_apostrophes(cls, text: str) -> tuple[str, int]:
        """Strip matching outer apostrophes when they enclose word characters.

        Returns (text, start_offset) where start_offset is 1 if stripped, else 0.
        """
        if text.startswith("'") and text.endswith("'") and len(text) > 2:  # noqa: PLR2004
            inner = text[1:-1]
            if any(cls._is_word_char(c) for c in inner):
                return inner, 1
        return text, 0

    def __call__(
        self,
        value: str,
        positions: bool = False,
        chars: bool = False,
        _keep_original: bool = False,
        remove_stops: bool = True,
        start_pos: int = 0,
        start_char: int = 0,
        mode: str = "index",
        **_kwargs: Any,  # noqa: ANN401
    ) -> Generator[Token, Any]:
        token = Token(positions=positions, chars=chars, removestops=remove_stops, mode=mode)
        length = len(value)
        i = 0
        pos = start_pos
        char_pos = start_char

        while i < length:
            ch = value[i]
            if not self._is_word_char(ch) and ch != "'":
                i += 1
                char_pos += 1
                continue

            start_i = i
            start_char_pos = char_pos
            i, saw_word = self._scan_token(value, start_i, length)
            char_pos += i - start_i

            if not saw_word:
                continue

            text, apostrophe_offset = self._strip_surrounding_apostrophes(value[start_i:i])
            start_char_pos += apostrophe_offset

            token.text = text  # ty:ignore[unresolved-attribute]
            if positions:
                token.pos = pos  # ty:ignore[unresolved-attribute]
                pos += 1
            if chars:
                token.startchar = start_char_pos  # ty:ignore[unresolved-attribute]
                token.endchar = start_char_pos + len(text)  # ty:ignore[unresolved-attribute]
            yield token
