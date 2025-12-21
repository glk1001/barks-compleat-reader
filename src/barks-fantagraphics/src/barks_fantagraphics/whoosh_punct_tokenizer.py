import unicodedata

from whoosh.analysis import Token, Tokenizer


class WordWithPunctTokenizer(Tokenizer):
    def __call__(
        self,
        value,
        positions=False,
        chars=False,
        keeporiginal=False,
        removestops=True,
        start_pos=0,
        start_char=0,
        mode="index",
        **kwargs,
    ):
        token = Token(positions=positions, chars=chars, removestops=removestops, mode=mode)

        length = len(value)
        i = 0
        pos = start_pos
        charpos = start_char

        def is_word_char(ch):
            return unicodedata.category(ch)[0] in ("L", "N")

        def has_future_word(start):
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
                charpos += 1
                continue

            start_i = i
            start_charpos = charpos
            saw_word = False

            while i < length:
                ch = value[i]

                if is_word_char(ch):
                    saw_word = True
                    i += 1
                    charpos += 1
                    continue

                if ch in ("-", ".", "'"):
                    # Apostrophes are always allowed
                    if ch == "'":
                        i += 1
                        charpos += 1
                        continue

                    # Allow punctuation if it connects to a future word
                    if has_future_word(i + 1):
                        i += 1
                        charpos += 1
                        continue

                    # Allow trailing dot in acronyms like G.I.
                    if (
                        ch == "."
                        and i > start_i
                        and is_word_char(value[i - 1])
                        and "." in value[start_i:i]
                    ):
                        i += 1
                        charpos += 1
                        continue

                break

            if not saw_word:
                continue

            text = value[start_i:i]

            # Strip surrounding quote apostrophes only
            if text.startswith("'") and text.endswith("'") and len(text) > 2:
                inner = text[1:-1]
                if any(is_word_char(c) for c in inner):
                    text = inner
                    start_charpos += 1

            token.text = text

            if positions:
                token.pos = pos
                pos += 1

            if chars:
                token.startchar = start_charpos
                token.endchar = start_charpos + len(text)

            yield token
