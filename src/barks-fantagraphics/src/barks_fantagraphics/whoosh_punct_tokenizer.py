import unicodedata
from collections.abc import Generator
from typing import Any

from whoosh.analysis import Token, Tokenizer


class WordWithPunctTokenizer(Tokenizer):
    def __call__(  # noqa: PLR0915
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

        def is_word_char(c: str) -> bool:
            return unicodedata.category(c)[0] in ("L", "N")

        def has_future_word(start: int) -> bool:
            j = start
            while j < length:
                if is_word_char(value[j]):
                    return True
                if value[j].isspace():
                    return False
                j += 1
            return False

        while i < length:
            ch = value[i]

            if not is_word_char(ch) and ch != "'":
                i += 1
                char_pos += 1
                continue

            start_i = i
            start_char_pos = char_pos
            saw_word = False

            while i < length:
                ch = value[i]

                if is_word_char(ch):
                    saw_word = True
                    i += 1
                    char_pos += 1
                    continue

                if ch in ("-", ".", "'", ","):
                    # Apostrophes are always allowed
                    if ch == "'":
                        i += 1
                        char_pos += 1
                        continue

                    # Specific logic for commas in numbers (e.g., 1,000).
                    # We only allow a comma if it is sandwiched between two numbers.
                    if ch == ",":
                        if (
                            i > start_i
                            and i + 1 < length
                            and unicodedata.category(value[i - 1])[0] == "N"
                            and unicodedata.category(value[i + 1])[0] == "N"
                        ):
                            i += 1
                            char_pos += 1
                            continue
                        # If the comma isn't inside a number, we break (ending the token)
                        # so it doesn't get picked up by the looser `has_future_word` check below.
                        break

                    # Allow punctuation (dots/hyphens) if it connects to a future word.
                    if has_future_word(i + 1):
                        i += 1
                        char_pos += 1
                        continue

                    # Allow trailing dot in acronyms like G.I.
                    if (
                        ch == "."
                        and i > start_i
                        and is_word_char(value[i - 1])
                        and "." in value[start_i:i]
                    ):
                        i += 1
                        char_pos += 1
                        continue

                break

            if not saw_word:
                continue

            text = value[start_i:i]

            # Strip surrounding quote apostrophes only
            if text.startswith("'") and text.endswith("'") and len(text) > 2:  # noqa: PLR2004
                inner = text[1:-1]
                if any(is_word_char(c) for c in inner):
                    text = inner
                    start_char_pos += 1

            token.text = text  # ty:ignore[unresolved-attribute]

            if positions:
                token.pos = pos  # ty:ignore[unresolved-attribute]
                pos += 1

            if chars:
                token.startchar = start_char_pos  # ty:ignore[unresolved-attribute]
                token.endchar = start_char_pos + len(text)  # ty:ignore[unresolved-attribute]

            yield token
