# cspell:ignore scroge scroged
"""The word search's typed query language: parsed into a small tree, never raising.

Phase 4 of the reader's search plan (docs/plans/advanced-search.md). A query such
as ``gold AND (mine OR "pirate gold") -duck year:1950-55`` parses into a tree of
`And`, `Or` and `Not` over words, phrases, NEAR pairs and qualifiers. The query
evaluator (a later phase) runs the tree; this module only reads the text. It is our
own grammar, not Whoosh's QueryParser: Whoosh's AND is per document (one bubble),
and the reader's AND means the same story.

Grammar (a space between terms means AND)::

    or_expr  := and_expr (OR and_expr)*
    and_expr := unary (AND? unary)*
    unary    := (NOT | -) unary | + unary | primary
    primary  := ( or_expr ) | "phrase" | WORD [NEAR[/n] WORD] | qualifier
    qualifier:= tag:WORD | tag:"words" | year:1950[-55] | vol:7[-9]

Operators: ``AND`` ``and`` ``&``; ``OR`` ``or`` ``|``; ``NOT`` ``not`` and a
leading ``-``. And, or and not are stop words, never searchable, so either case is
an operator; ``near`` is a word people search for, so only ``NEAR`` is one. A ``-``
is NOT only at the start of a token: ``indo-china`` and ``100-foot`` are words. No
term in the index holds ``& | + * ? : ( ) "``, so they are syntax wherever they are.

A word holding ``*`` or ``?`` is a wildcard (at least two letters besides them),
quoted or not: no index term holds either. Quotes make a single word exact and
several words a phrase. `parse_query` never
raises: bad syntax comes back as a `ParseError` with the position it was found at,
for a notice and a literal search instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum, auto

NEAR_DEFAULT_DISTANCE = 5
MIN_WILDCARD_LETTERS = 2
WILDCARD_CHARS = frozenset("*?")

# ----------------------------------------------------------------------- the tree --


@dataclass(frozen=True, slots=True)
class Word:
    """A word to find. ``exact``: quoted or picked from the list, so no other forms."""

    text: str
    exact: bool = False

    @property
    def is_wildcard(self) -> bool:
        """Whether the word holds ``*`` or ``?``."""
        return any(c in WILDCARD_CHARS for c in self.text)


@dataclass(frozen=True, slots=True)
class Phrase:
    """Words next to each other, in order, in one bubble."""

    words: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NearQuery:
    """Two words in one bubble, at most ``distance`` words apart, in either order."""

    left: Word
    right: Word
    distance: int = NEAR_DEFAULT_DISTANCE


@dataclass(frozen=True, slots=True)
class TagQualifier:
    """Only stories with this tag (``tag:scrooge``)."""

    name: str


@dataclass(frozen=True, slots=True)
class YearQualifier:
    """Only stories submitted in these years, both included (``year:1950-55``)."""

    first: int
    last: int


@dataclass(frozen=True, slots=True)
class VolumeQualifier:
    """Only stories in these Fantagraphics volumes, both included (``vol:5-8``)."""

    first: int
    last: int


@dataclass(frozen=True, slots=True)
class And:
    """Every part in the same story."""

    parts: tuple[QueryNode, ...]


@dataclass(frozen=True, slots=True)
class Or:
    """Any part."""

    parts: tuple[QueryNode, ...]


@dataclass(frozen=True, slots=True)
class Not:
    """Not in the same story."""

    part: QueryNode


type QueryNode = (
    And | Or | Not | Word | Phrase | NearQuery | TagQualifier | YearQualifier | VolumeQualifier
)


# ------------------------------------------------- the leaves the engine will run --


@dataclass(frozen=True, slots=True)
class AnyTerm:
    """A bubble holding any one of these index terms (a word, its forms, a wildcard's)."""

    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Near:
    """A bubble with a term from each side at most ``distance`` words apart."""

    left: AnyTerm
    right: AnyTerm
    distance: int = NEAR_DEFAULT_DISTANCE

    def is_near(self, lefts: list[int], rights: list[int]) -> bool:
        """Whether two different words, one from each side, are at most `distance` apart.

        Args:
            lefts: The positions in a bubble of the left side's terms.
            rights: The positions of the right side's terms.

        Returns:
            Whether the bubble holds the pair.

        """
        return any(i != j and abs(i - j) <= self.distance for i in lefts for j in rights)


type SearchLeaf = AnyTerm | Phrase | Near


# -------------------------------------------------------------------- the result --


@dataclass(frozen=True, slots=True)
class ParseError:
    """What was wrong with a query, and where: a character index into the text."""

    message: str
    position: int


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    """A query's tree, or why it has none. Both are None for an empty query."""

    text: str
    root: QueryNode | None = None
    error: ParseError | None = None

    @property
    def ok(self) -> bool:
        """Whether the query parsed into a tree."""
        return self.root is not None and self.error is None


class Combine(StrEnum):
    """How the words (or tags) picked into a list combine."""

    ALL = auto()
    ANY = auto()


def query_from_words(words: list[str], combine: Combine) -> QueryNode | None:
    """Return the query for words picked from the list: each exact, all or any of them.

    Args:
        words: The picked words.
        combine: ALL (every one in the same story) or ANY.

    Returns:
        The query, or None when no word was picked.

    """
    parts = tuple(Word(w, exact=True) for w in words)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return And(parts) if combine is Combine.ALL else Or(parts)


# -------------------------------------------------------------------- the tokens --


class _Kind(StrEnum):
    WORD = auto()
    PHRASE = auto()
    QUALIFIER = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    PLUS = auto()
    NEAR = auto()
    LPAREN = auto()
    RPAREN = auto()


@dataclass(frozen=True, slots=True)
class _Token:
    kind: _Kind
    text: str
    position: int
    key: str = ""  # a qualifier's key
    quoted: bool = False  # a qualifier value given in quotes


class _QueryError(Exception):
    """Raised inside the parser only; `parse_query` turns it into a `ParseError`."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(message)
        self.message = message
        self.position = position


_OPERATOR_WORDS = {"and": _Kind.AND, "or": _Kind.OR, "not": _Kind.NOT}
_QUALIFIER_KEYS = ("tag", "year", "vol")
_NEAR_RE = re.compile(r"NEAR(?:/(\d+))?")
# What ends a word: space, and the characters that are syntax wherever they are.
_WORD_END = frozenset('()"&|') | frozenset(" \t\n\r")


def _read_quoted(text: str, start: int) -> tuple[str, int]:
    """Return the text between the quote at `start` and the next, and the index after it."""
    end = text.find('"', start + 1)
    if end < 0:
        msg = "a quote is not closed"
        raise _QueryError(msg, start)
    return text[start + 1 : end], end + 1


def _tokenize(text: str) -> list[_Token]:  # noqa: C901, PLR0912
    tokens: list[_Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch in "()":
            tokens.append(_Token(_Kind.LPAREN if ch == "(" else _Kind.RPAREN, ch, i))
            i += 1
        elif ch == '"':
            inner, end = _read_quoted(text, i)
            tokens.append(_Token(_Kind.PHRASE, inner, i))
            i = end
        elif ch in "&|":
            tokens.append(_Token(_Kind.AND if ch == "&" else _Kind.OR, ch, i))
            i += 1
        elif ch in "+-":
            # Only at the start of a token: a word's own hyphen (indo-china, 100-foot)
            # is read with the word below, never here.
            tokens.append(_Token(_Kind.PLUS if ch == "+" else _Kind.NOT, ch, i))
            i += 1
        else:
            start = i
            while i < n and text[i] not in _WORD_END:
                i += 1
            word = text[start:i]
            key, colon, value = word.partition(":")
            if colon:
                if key.lower() not in _QUALIFIER_KEYS:
                    msg = f'"{key}:" is not a filter (tag:, year: or vol:)'
                    raise _QueryError(msg, start)
                if not value and i < n and text[i] == '"':
                    value, i = _read_quoted(text, i)
                    tokens.append(_Token(_Kind.QUALIFIER, value, start, key.lower(), quoted=True))
                else:
                    tokens.append(_Token(_Kind.QUALIFIER, value, start, key.lower()))
            elif word.lower() in _OPERATOR_WORDS:
                tokens.append(_Token(_OPERATOR_WORDS[word.lower()], word, start))
            elif _NEAR_RE.fullmatch(word):
                tokens.append(_Token(_Kind.NEAR, word, start))
            else:
                tokens.append(_Token(_Kind.WORD, word, start))
    return tokens


# -------------------------------------------------------------------- the parser --

_STARTS_A_TERM = frozenset(
    {_Kind.WORD, _Kind.PHRASE, _Kind.QUALIFIER, _Kind.NOT, _Kind.PLUS, _Kind.LPAREN}
)


def _range(value: str, position: int, what: str, *, years: bool) -> tuple[int, int]:
    """Return the inclusive range a ``year:``/``vol:`` value names: ``7``, ``5-8``, ``1950-55``."""
    first_text, dash, last_text = value.partition("-")
    if not first_text.isdigit() or (dash and not last_text.isdigit()):
        msg = f"{what} must be a number or a range, like {'1950-55' if years else '5-8'}"
        raise _QueryError(msg, position)
    first = int(first_text)
    last = first
    if dash:
        last = int(last_text)
        if years and len(last_text) < len(first_text):  # 1950-55: the last two digits
            scale = 10 ** len(last_text)
            last = first // scale * scale + last
    if last < first:
        msg = f"{what} range runs backwards"
        raise _QueryError(msg, position)
    return first, last


def read_range(value: str, *, years: bool) -> tuple[int, int]:
    """Return the inclusive range a ``year:`` or ``vol:`` value names: ``7``, ``5-8``, ``1950-55``.

    For other parsers of the same qualifiers (typed tags).

    Args:
        value: The text after the colon.
        years: Whether it is years, whose last may be shortened (``1948-9``).

    Returns:
        The first and last, both included.

    Raises:
        ValueError: If the value is no number or range, or runs backwards.

    """
    try:
        return _range(value, 0, "a year" if years else "a volume", years=years)
    except _QueryError as exc:
        raise ValueError(exc.message) from exc


class _Parser:
    def __init__(self, tokens: list[_Token], text: str) -> None:
        self._tokens = tokens
        self._text = text
        self._i = 0

    def _peek(self) -> _Token | None:
        return self._tokens[self._i] if self._i < len(self._tokens) else None

    def _take(self) -> _Token:
        token = self._tokens[self._i]
        self._i += 1
        return token

    def _end(self) -> int:
        return len(self._text)

    def parse(self) -> QueryNode:
        node = self._or()
        extra = self._peek()
        if extra is not None:
            msg = (
                "a closing bracket has no opening one"
                if extra.kind is _Kind.RPAREN
                else (f'"{extra.text}" is not expected here')
            )
            raise _QueryError(msg, extra.position)
        return node

    def _or(self) -> QueryNode:
        parts = [self._and()]
        while (token := self._peek()) is not None and token.kind is _Kind.OR:
            self._take()
            self._expect_term(token)
            parts.append(self._and())
        return parts[0] if len(parts) == 1 else Or(tuple(parts))

    def _and(self) -> QueryNode:
        parts = [self._unary()]
        while (token := self._peek()) is not None:
            if token.kind is _Kind.AND:
                self._take()
                self._expect_term(token)
            elif token.kind not in _STARTS_A_TERM:
                break
            parts.append(self._unary())
        return parts[0] if len(parts) == 1 else And(tuple(parts))

    def _expect_term(self, operator: _Token) -> None:
        token = self._peek()
        if token is None or token.kind not in _STARTS_A_TERM:
            msg = f'nothing to search after "{operator.text}"'
            raise _QueryError(msg, operator.position)

    def _unary(self) -> QueryNode:
        token = self._peek()
        if token is not None and token.kind in (_Kind.NOT, _Kind.PLUS):
            self._take()
            self._expect_term(token)
            part = self._unary()
            return Not(part) if token.kind is _Kind.NOT else part
        return self._primary()

    def _primary(self) -> QueryNode:
        token = self._peek()
        if token is None:
            msg = "the query ends too soon"
            raise _QueryError(msg, self._end())
        self._take()
        match token.kind:
            case _Kind.LPAREN:
                return self._group(token)
            case _Kind.PHRASE:
                return self._phrase(token)
            case _Kind.QUALIFIER:
                return self._qualifier(token)
            case _Kind.WORD:
                return self._word_or_near(token)
            case _:
                msg = (
                    "a closing bracket has no opening one"
                    if token.kind is _Kind.RPAREN
                    else f'"{token.text}" needs something to search before it'
                )
                raise _QueryError(msg, token.position)

    def _group(self, opening: _Token) -> QueryNode:
        token = self._peek()
        if token is not None and token.kind is _Kind.RPAREN:
            msg = "the brackets are empty"
            raise _QueryError(msg, opening.position)
        node = self._or()
        closing = self._peek()
        if closing is None or closing.kind is not _Kind.RPAREN:
            msg = "a bracket is not closed"
            raise _QueryError(msg, opening.position)
        self._take()
        return node

    def _phrase(self, token: _Token) -> QueryNode:
        words = tuple(token.text.split())
        if not words:
            msg = "the quotes are empty"
            raise _QueryError(msg, token.position)
        if len(words) == 1:
            return self._word(words[0], token.position, exact=True)
        return Phrase(words)

    @staticmethod
    def _qualifier(token: _Token) -> QueryNode:
        value = token.text.strip()
        if not value:
            msg = f'"{token.key}:" needs a value'
            raise _QueryError(msg, token.position)
        if token.key == "tag":
            return TagQualifier(value)
        if token.quoted:
            msg = f'"{token.key}:" takes a number, not quotes'
            raise _QueryError(msg, token.position)
        if token.key == "year":
            return YearQualifier(*_range(value, token.position, "a year", years=True))
        return VolumeQualifier(*_range(value, token.position, "a volume", years=False))

    def _word_or_near(self, token: _Token) -> QueryNode:
        left = self._word(token.text, token.position)
        near = self._peek()
        if near is None or near.kind is not _Kind.NEAR:
            return left
        self._take()
        near_match = _NEAR_RE.fullmatch(near.text)
        assert near_match is not None  # the tokenizer made it a NEAR by this match
        distance_text = near_match.group(1)
        distance = NEAR_DEFAULT_DISTANCE if distance_text is None else int(distance_text)
        if distance < 1:
            msg = "NEAR/n needs a distance of at least 1"
            raise _QueryError(msg, near.position)
        right_token = self._peek()
        if right_token is None or right_token.kind is not _Kind.WORD:
            msg = "NEAR needs a word after it"
            raise _QueryError(msg, near.position)
        self._take()
        return NearQuery(left, self._word(right_token.text, right_token.position), distance)

    @staticmethod
    def _word(text: str, position: int, *, exact: bool = False) -> Word:
        word = Word(text, exact=exact)
        if word.is_wildcard:
            letters = sum(1 for c in text if c not in WILDCARD_CHARS)
            if letters < MIN_WILDCARD_LETTERS:
                msg = f"a wildcard needs at least {MIN_WILDCARD_LETTERS} letters besides * and ?"
                raise _QueryError(msg, position)
        return word


# ---------------------------------------------------------------------- the API --


def parse_query(text: str) -> ParsedQuery:
    """Parse a typed query. Never raises: bad syntax comes back as the result's `error`.

    Args:
        text: What was typed.

    Returns:
        The query's tree; or, for bad syntax, why and where; or neither, for nothing
        typed.

    """
    try:
        tokens = _tokenize(text)
        if not tokens:
            return ParsedQuery(text)
        return ParsedQuery(text, root=_Parser(tokens, text).parse())
    except _QueryError as exc:
        return ParsedQuery(text, error=ParseError(exc.message, exc.position))
    except (RecursionError, ValueError) as exc:  # pathological input: still no raise
        return ParsedQuery(text, error=ParseError(f"the query cannot be read ({exc})", 0))


def replace_word(text: str, word: str, replacement: str) -> str:
    """Return `text` with every whole-word `word` in it, in any case, made `replacement`.

    For a spelling suggestion picked in place of a word typed: ``scroge -gold`` with
    Scrooge for scroge is ``Scrooge -gold``. Operators and brackets around the word
    stay; a longer word holding it (``scroged``) does not change.

    Args:
        text: A typed query.
        word: The word to replace, as typed.
        replacement: What to put in its place.

    Returns:
        The query with the word replaced.

    """
    found = re.compile(rf"(?<![\w'-]){re.escape(word)}(?![\w'-])", re.IGNORECASE)
    return found.sub(lambda _m: replacement, text)


def has_query_syntax(text: str) -> bool:
    """Return whether `text` uses the query language, not just plain words.

    Quotes, brackets, operators, NEAR, qualifiers and wildcards count; a text that
    tries one and gets it wrong (an unclosed quote) counts too. Plain words with
    spaces between them do not: the word list is tried for them first.

    Args:
        text: What was typed.

    Returns:
        Whether a query, not a word, was typed.

    """
    try:
        tokens = _tokenize(text)
    except _QueryError:
        return True
    return any(t.kind is not _Kind.WORD or Word(t.text).is_wildcard for t in tokens)
