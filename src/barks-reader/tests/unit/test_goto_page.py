"""The page a title offers to open at (barks_reader.core.goto_page)."""

from __future__ import annotations

import pytest
from barks_reader.core.goto_page import (
    GotoPageButtonKind,
    GotoPageOffer,
    goto_page_after_reading,
    goto_page_button_kind,
)
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE

# Adventure Down Under under Australian Aboriginals: 7, 13 and 16 to 23.
_TAGGED_PAGES = ("7", "13", "16", "17", "18", "19", "20", "21", "22", "23")


class TestMake:
    def test_no_page_and_the_beginning_offer_nothing(self) -> None:
        assert GotoPageOffer.make() == GotoPageOffer()
        assert GotoPageOffer.make(COMIC_BEGIN_PAGE, active=True) == GotoPageOffer(active=True)

    def test_a_tag_offers_the_start_of_each_run(self) -> None:
        offer = GotoPageOffer.make("7", active=True, tagged_pages=_TAGGED_PAGES)
        assert offer.pages == ("7", "13", "16")
        assert offer.tagged_pages == _TAGGED_PAGES
        assert offer.position == " (1 of 3)"

    def test_the_page_offered_and_the_page_kept_join_the_tags_pages_in_order(self) -> None:
        offer = GotoPageOffer.make("9", active=True, tagged_pages=("13", "16"), kept_page="2")
        assert offer.pages == ("2", "9", "13", "16")
        offer = GotoPageOffer.make("13", active=True, tagged_pages=("13", "16"), kept_page="13")
        assert offer.pages == ("13", "16")

    def test_without_a_tag_there_is_nothing_to_step_through(self) -> None:
        offer = GotoPageOffer.make("9", active=True, kept_page="2")
        assert offer.pages == ()
        assert offer.can_step is False
        assert offer.position == ""


class TestStepping:
    def test_stepping_wraps_round_both_ways_and_ticks(self) -> None:
        offer = GotoPageOffer.make("7", tagged_pages=_TAGGED_PAGES)
        pages = []
        for _ in range(3):
            offer = offer.stepped(1)
            pages.append(offer.page)
        assert pages == ["13", "16", "7"]
        assert offer.active is True
        offer = offer.stepped(-1)
        assert (offer.page, offer.position) == ("16", " (3 of 3)")

    def test_one_run_has_nothing_to_step_through(self) -> None:
        offer = GotoPageOffer.make("4", active=True, tagged_pages=("4", "5", "6"))
        assert offer.stepped(1) is offer
        assert offer.position == ""


class TestText:
    def test_a_run_reads_as_its_pages_and_a_lone_page_as_one(self) -> None:
        offer = GotoPageOffer.make("7", tagged_pages=_TAGGED_PAGES)
        assert (offer.run_end, offer.text) == ("", "Goto page 7 (1 of 3):")
        offer = offer.stepped(-1)
        assert (offer.run_end, offer.text) == ("23", "Goto pages 16-23 (3 of 3):")

    def test_a_page_outside_the_tags_pages_has_no_position(self) -> None:
        offer = GotoPageOffer(page="9", active=True, tagged_pages=("13", "16"), pages=("13", "16"))
        assert offer.index is None
        assert offer.text == "Goto page 9:"
        assert offer.stepped(1).page == "16"  # steps on from the first


class TestAfterReading:
    def test_the_page_last_read_is_offered_with_the_tags_pages_a_step_away(self) -> None:
        offer = goto_page_after_reading("9", ("1", "14"))
        assert offer == GotoPageOffer.make("9", active=True, tagged_pages=("1", "14"))
        assert offer.pages == ("1", "9", "14")

    @pytest.mark.parametrize("last_read", ["", COMIC_BEGIN_PAGE])
    def test_with_nothing_read_the_tags_first_page_is_offered(self, last_read: str) -> None:
        offer = goto_page_after_reading(last_read, ("1", "14"))
        assert offer == GotoPageOffer.make("1", active=True, tagged_pages=("1", "14"))

    @pytest.mark.parametrize("last_read", ["", COMIC_BEGIN_PAGE])
    def test_with_nothing_read_and_no_tag_none_is_offered(self, last_read: str) -> None:
        assert goto_page_after_reading(last_read) == GotoPageOffer()


class TestGotoPageButtonKind:
    """How the comic reader's goto-page list marks a page."""

    @pytest.mark.parametrize("is_tagged", [True, False])
    @pytest.mark.parametrize("is_body", [True, False])
    def test_the_page_on_show_is_marked_as_that_whatever_else_it_is(
        self, *, is_tagged: bool, is_body: bool
    ) -> None:
        kind = goto_page_button_kind(is_current=True, is_tagged=is_tagged, is_body=is_body)
        assert kind is GotoPageButtonKind.CURRENT

    @pytest.mark.parametrize("is_body", [True, False])
    def test_a_tagged_page_is_marked_tagged_before_body_or_not(self, *, is_body: bool) -> None:
        kind = goto_page_button_kind(is_current=False, is_tagged=True, is_body=is_body)
        assert kind is GotoPageButtonKind.TAGGED

    @pytest.mark.parametrize(
        ("is_body", "kind"),
        [(True, GotoPageButtonKind.BODY), (False, GotoPageButtonKind.NON_BODY)],
    )
    def test_any_other_page_is_marked_by_whether_it_is_the_story_s(
        self, *, is_body: bool, kind: GotoPageButtonKind
    ) -> None:
        assert goto_page_button_kind(is_current=False, is_tagged=False, is_body=is_body) is kind
