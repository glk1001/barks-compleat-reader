"""A story's ini credits agree with Barks's role in Barrier's bibliography.

The ini's ``extra_pub_info`` credits the script and the art (``story_credits``); the
bibliography's ``BibEntry.effective_qualifier`` says which of them was Barks's: all of it
(``None``), the art only, the script only, or the art and a rewrite of another's script.
The two are kept apart, so they can disagree: a story Barrier marks art only whose ini
names no other scriptwriter, or a wholly-Barks story whose ini credits someone else. A
story with no bibliography entry has no role to disagree with (which stories those are is
``EXPECTED_WITHOUT_BIB_ENTRY``, in ``test_barks_bibliography``).

A disagreement awaiting review is held in ``KNOWN_DISAGREEMENTS`` until one side or the
other is corrected. A new disagreement fails, and so does an entry that no longer
disagrees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_bibliography import TITLE_TO_BIB_ENTRY, Qualifier
from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from story_credits import StoryCredits, read_credits

if TYPE_CHECKING:
    from barks_fantagraphics.comics_database import ComicsDatabase

# Disagreements awaiting review: either the ini lacks a credit, or the role is wrong.
KNOWN_DISAGREEMENTS: dict[Titles, str] = {}


def disagreement(title: Titles, story_credits: StoryCredits) -> str | None:
    """Return how a story's credits contradict its bibliography role, or None if they agree.

    Args:
        title: The story.
        story_credits: The credits read from its ini.

    Returns:
        The disagreement, or None.

    """
    entry = TITLE_TO_BIB_ENTRY.get(title)
    if entry is None:  # no role to disagree with
        return None
    return _role_disagreement(entry.effective_qualifier, story_credits)


def _role_disagreement(role: Qualifier | None, story_credits: StoryCredits) -> str | None:
    """Return how the credits contradict Barks's role, or None if they agree.

    Art and rewriting of script takes any other scriptwriter's credit, so "Script by Bob
    Gregory and Barks" agrees with art only too.
    """
    c = story_credits
    problem = None
    if role is None:
        if c.other_script or c.other_art:
            problem = "wholly Barks's, but the ini credits someone else"
    elif role is Qualifier.SCRIPT_ONLY:
        if not c.other_art:
            problem = "SCRIPT_ONLY, but the ini names no other artist"
        elif c.other_script and not c.barks_script:
            problem = "SCRIPT_ONLY, but the ini credits only someone else's script"
    elif not c.other_script:  # Barks drew it: art only, or art and a rewritten script
        problem = f"{role.name}, but the ini names no other scriptwriter"
    elif c.other_art and not c.barks_art:
        problem = f"{role.name}, but the ini credits only someone else's art"
    return problem


@pytest.fixture(scope="module")
def credits_by_title(db: ComicsDatabase) -> dict[Titles, StoryCredits]:
    """Each story's credits, by title."""
    by_title = {}
    for name in db.get_all_story_titles():
        title = STR_TITLE_TO_ENUM.get(name)
        # Titles is an IntEnum and its first member is 0: test "is not None", never truth.
        if title is not None:
            by_title[title] = read_credits(db.get_comic_book(name).extra_pub_info)
    return by_title


class TestTheCreditReader:
    @pytest.mark.parametrize(
        ("credit", "expected"),
        [
            ("Script not by Barks", StoryCredits(other_script=True)),
            ("Script by Vic Lockman", StoryCredits(other_script=True)),
            ("Script by Bob Gregory and Barks", StoryCredits(other_script=True)),
            (
                "Script: Bob Karp\nArt: Carl Barks (pages 1, 2, 5, 12-40)",
                StoryCredits(other_script=True, barks_art=True),
            ),
            (
                "Pages 1-3, script by Carl Barks\nPages 4-8 script and finished art by Don Rosa",
                StoryCredits(barks_script=True, other_script=True, other_art=True),
            ),
            (
                "Script and layout by Carl Barks\nPencils and inks by Daan Jippes",
                StoryCredits(barks_script=True, other_art=True),
            ),
            ("Pages 1-3, script by Carl Barks", StoryCredits(barks_script=True)),
        ],
    )
    def test_a_credit_is_read(self, credit: str, expected: StoryCredits) -> None:
        assert read_credits(credit) == expected

    @pytest.mark.parametrize(
        "note",
        [
            "New opening half-page written by David Gerstein",
            "and Unn Printz-Påhlson, art by Daan Jippes",
            "Layout and restoration by Kim Weston",
            "Original art and dialogue on pages 2, 4, 5, 6, 7, and 8 restored by GLK, Dec 2025",
            "Original dialogue on page 4 restored by GLK, Aug 2025",
        ],
    )
    def test_a_note_is_not_a_credit(self, note: str) -> None:
        assert read_credits(note) == StoryCredits()

    def test_an_unknown_wording_is_kept_as_unrecognised(self) -> None:
        assert read_credits("Inks partly by Al Hubbard").unrecognised == (
            "Inks partly by Al Hubbard",
        )


class TestTheAgreementRules:
    """The rules by role, not through a story: a corrected role must not fail a rule."""

    @pytest.mark.parametrize(
        ("role", "story_credits", "agrees"),
        [
            # Art only: another's script is what the role says.
            (Qualifier.ART_ONLY, StoryCredits(other_script=True), True),
            (Qualifier.ART_ONLY, StoryCredits(), False),
            # Art only, Barks's art beside another's (Pirate Gold, with Jack Hannah).
            (
                Qualifier.ART_ONLY,
                StoryCredits(other_script=True, barks_art=True, other_art=True),
                True,
            ),
            (Qualifier.ART_ONLY, StoryCredits(other_script=True, other_art=True), False),
            # Art and a rewrite of another's script takes the same credits as art only.
            (Qualifier.ART_AND_REWRITING_OF_SCRIPT, StoryCredits(other_script=True), True),
            (Qualifier.ART_AND_REWRITING_OF_SCRIPT, StoryCredits(), False),
            # Wholly Barks's.
            (None, StoryCredits(), True),
            (None, StoryCredits(other_art=True), False),
            (None, StoryCredits(other_script=True), False),
            # Script only.
            (Qualifier.SCRIPT_ONLY, StoryCredits(barks_script=True, other_art=True), True),
            (Qualifier.SCRIPT_ONLY, StoryCredits(barks_script=True), False),
            (Qualifier.SCRIPT_ONLY, StoryCredits(other_script=True, other_art=True), False),
        ],
    )
    def test_a_role_and_its_credits(
        self, role: Qualifier | None, story_credits: StoryCredits, *, agrees: bool
    ) -> None:
        assert (_role_disagreement(role, story_credits) is None) == agrees

    def test_a_story_with_no_bibliography_entry_has_no_role_to_disagree_with(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(globals(), "TITLE_TO_BIB_ENTRY", {})
        assert disagreement(Titles.VACATION_TIME, StoryCredits(other_script=True)) is None

    def test_a_story_takes_the_role_its_bibliography_entry_gives(self) -> None:
        # One real story, to show the entry's role is the one the rules are asked about.
        assert TITLE_TO_BIB_ENTRY[Titles.PHANTOM_JOKER_THE].effective_qualifier is (
            Qualifier.SCRIPT_ONLY
        )
        assert disagreement(Titles.PHANTOM_JOKER_THE, StoryCredits(barks_script=True)) == (
            "SCRIPT_ONLY, but the ini names no other artist"
        )


class TestEveryStoryCredits:
    def test_the_stories_are_found(self, credits_by_title: dict[Titles, StoryCredits]) -> None:
        # Guards the checks below: with no stories they would pass vacuously.
        assert sum(c.any for c in credits_by_title.values()) > 40  # noqa: PLR2004

    def test_every_credit_is_a_known_form(
        self, credits_by_title: dict[Titles, StoryCredits]
    ) -> None:
        unknown = {t.name: c.unrecognised for t, c in credits_by_title.items() if c.unrecognised}
        assert not unknown, (
            "These ini credits name a role in a wording story_credits.py does not read;"
            f" teach it the wording, or reword the ini: {unknown}"
        )

    def test_the_credits_agree_with_the_bibliography(
        self, credits_by_title: dict[Titles, StoryCredits]
    ) -> None:
        found = {
            title: problem
            for title, story_credits in credits_by_title.items()
            if (problem := disagreement(title, story_credits)) is not None
        }
        new = {t.name: p for t, p in found.items() if t not in KNOWN_DISAGREEMENTS}
        resolved = sorted(t.name for t in KNOWN_DISAGREEMENTS if t not in found)
        assert not new, (
            "These stories' ini credits disagree with Barks's role in the bibliography."
            " Fix the ini, correct the role (ROLE_CORRECTIONS in"
            " experiments/bibliography/overrides.py), or add the story to"
            f" KNOWN_DISAGREEMENTS with a reason: {new}"
        )
        assert not resolved, (
            f"These stories no longer disagree; remove them from KNOWN_DISAGREEMENTS: {resolved}"
        )
