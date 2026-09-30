"""What the search screen holds between keystrokes: the words picked to search together.

Kivy-free (docs/plans/advanced-search.md, phase 9; the tag and era choices of later
phases join it). The word search's basket is the words picked from the word list,
combined ALL (every one in the same story) or ANY. It runs as a typed query whose
words are quoted, so each is found exactly as picked and a term of several words is
a phrase: the same tree `query_from_words` builds, through the same evaluator as
anything typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from barks_fantagraphics.search_query import Combine


@dataclass
class WordBasket:
    """The words picked to search together, in the order picked, and how they combine."""

    words: list[str] = field(default_factory=list)
    combine: Combine = Combine.ALL

    def __contains__(self, word: object) -> bool:
        """Return whether `word` is picked."""
        return word in self.words

    def __len__(self) -> int:
        """Return how many words are picked."""
        return len(self.words)

    def toggle(self, word: str) -> bool:
        """Pick `word`, or put it back if it is picked already.

        Args:
            word: A word from the word list.

        Returns:
            Whether the word is picked now.

        """
        if word in self.words:
            self.words.remove(word)
            return False
        self.words.append(word)
        return True

    def remove(self, word: str) -> None:
        """Put `word` back, if it is picked."""
        if word in self.words:
            self.words.remove(word)

    def flip(self) -> Combine:
        """Switch between ALL and ANY, and return the new choice."""
        self.combine = Combine.ANY if self.combine is Combine.ALL else Combine.ALL
        return self.combine

    def clear(self) -> None:
        """Put every word back; the next word picked starts an ALL basket."""
        self.words.clear()
        self.combine = Combine.ALL

    def query_text(self) -> str:
        """Return the basket as a query: each word quoted, joined by a space (ALL) or ``|``.

        Returns:
            The query, or "" for an empty basket.

        """
        separator = " " if self.combine is Combine.ALL else " | "
        return separator.join(f'"{word}"' for word in self.words)
