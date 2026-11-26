"""Which page of a document shows and the moves between them (barks_reader.core.document_pager)."""

from __future__ import annotations

from pathlib import Path

import pytest
from barks_reader.core.document_pager import DocumentPager, DocumentView

DOC = Path("history/chapter-1")
OTHER_DOC = Path("history/chapter-2")


def _pages(count: int, doc_dir: Path = DOC) -> list[Path]:
    return [doc_dir / f"page-{number:03d}.png" for number in range(1, count + 1)]


def _opened(count: int, *, resume: bool = False) -> DocumentPager:
    pager = DocumentPager()
    pager.open(DOC, _pages(count), resume=resume)
    return pager


def _shown(pager: DocumentPager, *, two_up: bool) -> tuple[int, int | None]:
    view = pager.view(two_up=two_up)
    assert view is not None
    return view.left_index, view.right_index


class TestAnEmptyDocument:
    def test_a_new_pager_has_no_document(self) -> None:
        pager = DocumentPager()
        assert pager.is_open is False
        assert pager.page_count == 0
        assert pager.current_page_index == 0
        assert pager.view(two_up=False) is None

    @pytest.mark.parametrize("two_up", [False, True])
    def test_no_pages_give_no_view_and_neither_step_moves(self, two_up: bool) -> None:
        pager = _opened(0)
        assert pager.is_open is False
        assert pager.view(two_up=two_up) is None
        assert pager.next_page(two_up=two_up) is False
        assert pager.prev_page() is False
        assert pager.current_page_index == 0

    def test_no_pages_remember_no_page(self) -> None:
        pager = _opened(3)
        pager.next_page(two_up=False)
        pager.view(two_up=False)
        pager.open(DOC, [], resume=True)
        assert pager.view(two_up=False) is None
        pager.open(DOC, _pages(3), resume=True)
        assert _shown(pager, two_up=False) == (1, None)


class TestOnePageAtATime:
    def test_the_view_is_the_page_alone_with_its_path_and_the_count(self) -> None:
        pager = _opened(3)
        assert pager.is_open is True
        assert pager.page_count == 3  # noqa: PLR2004
        assert pager.view(two_up=False) == DocumentView(
            left=DOC / "page-001.png", right=None, left_index=0, right_index=None, page_count=3
        )

    def test_the_steps_move_a_page_and_stop_at_the_ends(self) -> None:
        pager = _opened(3)
        assert pager.prev_page() is False  # the first page
        assert pager.next_page(two_up=False) is True
        assert _shown(pager, two_up=False) == (1, None)
        assert pager.next_page(two_up=False) is True
        assert _shown(pager, two_up=False) == (2, None)
        assert pager.next_page(two_up=False) is False  # the last page
        assert _shown(pager, two_up=False) == (2, None)
        assert pager.prev_page() is True
        assert _shown(pager, two_up=False) == (1, None)
        assert pager.prev_page() is True  # the second page has one before it
        assert _shown(pager, two_up=False) == (0, None)
        assert pager.prev_page() is False

    def test_the_pager_keeps_its_own_list_of_pages(self) -> None:
        pages = _pages(2)
        pager = DocumentPager()
        pager.open(DOC, pages, resume=False)
        pages.clear()
        assert pager.page_count == 2  # noqa: PLR2004


class TestTwoUp:
    def test_the_view_is_the_pair_with_both_paths(self) -> None:
        pager = _opened(4)
        assert pager.view(two_up=True) == DocumentView(
            left=DOC / "page-001.png",
            right=DOC / "page-002.png",
            left_index=0,
            right_index=1,
            page_count=4,
        )

    def test_stepping_forward_from_a_pair_lands_on_the_next_pairs_left_page(self) -> None:
        pager = _opened(7)
        assert pager.next_page(two_up=True) is True
        assert pager.current_page_index == 2  # noqa: PLR2004
        assert _shown(pager, two_up=True) == (2, 3)

    def test_an_odd_page_count_leaves_the_last_page_alone(self) -> None:
        pager = _opened(5)
        pager.next_page(two_up=True)
        pager.next_page(two_up=True)
        assert _shown(pager, two_up=True) == (4, None)
        assert pager.next_page(two_up=True) is False

    def test_an_even_page_count_ends_on_a_pair(self) -> None:
        pager = _opened(4)
        assert pager.next_page(two_up=True) is True
        assert _shown(pager, two_up=True) == (2, 3)
        assert pager.next_page(two_up=True) is False  # its right page is the last
        assert _shown(pager, two_up=True) == (2, 3)

    def test_stepping_back_from_a_pairs_left_page_shows_the_pair_before_it(self) -> None:
        pager = _opened(7)
        pager.next_page(two_up=True)
        pager.next_page(two_up=True)
        assert _shown(pager, two_up=True) == (4, 5)
        assert pager.prev_page() is True
        assert _shown(pager, two_up=True) == (2, 3)
        assert pager.current_page_index == 2  # noqa: PLR2004

    def test_the_first_pair_has_no_page_before_it(self) -> None:
        pager = _opened(4)
        pager.view(two_up=True)
        assert pager.prev_page() is False
        assert _shown(pager, two_up=True) == (0, 1)


class TestTheLayoutChangingBetweenSteps:
    def test_a_right_page_shows_with_its_pair_and_then_the_pairs_left_alone(self) -> None:
        pager = _opened(7)
        for _ in range(3):
            pager.next_page(two_up=False)
        assert _shown(pager, two_up=False) == (3, None)
        assert _shown(pager, two_up=True) == (2, 3)
        # The pair's left page became the current one.
        assert _shown(pager, two_up=False) == (2, None)

    def test_a_step_one_up_from_a_pair_goes_to_its_right_page(self) -> None:
        pager = _opened(7)
        assert _shown(pager, two_up=True) == (0, 1)
        assert pager.next_page(two_up=False) is True
        assert _shown(pager, two_up=False) == (1, None)
        assert pager.next_page(two_up=True) is True  # on from the pair (0, 1)
        assert _shown(pager, two_up=True) == (2, 3)

    def test_a_step_two_up_before_the_view_goes_on_from_the_whole_pair(self) -> None:
        pager = _opened(7)
        pager.next_page(two_up=False)  # page 2, the first pair's right page
        assert pager.next_page(two_up=True) is True
        assert _shown(pager, two_up=True) == (2, 3)


class TestResume:
    def test_a_resumed_document_opens_at_the_page_last_shown(self) -> None:
        pager = _opened(4)
        pager.next_page(two_up=False)
        pager.next_page(two_up=False)
        pager.view(two_up=False)
        pager.open(DOC, _pages(4), resume=True)
        assert _shown(pager, two_up=False) == (2, None)

    def test_a_document_not_resumed_opens_at_its_first_page(self) -> None:
        pager = _opened(4)
        pager.next_page(two_up=False)
        pager.view(two_up=False)
        pager.open(DOC, _pages(4), resume=False)
        assert _shown(pager, two_up=False) == (0, None)

    def test_a_page_stepped_to_but_never_shown_is_not_remembered(self) -> None:
        pager = _opened(4)
        pager.view(two_up=False)
        pager.next_page(two_up=False)
        pager.open(DOC, _pages(4), resume=True)
        assert _shown(pager, two_up=False) == (0, None)

    def test_a_folder_with_fewer_pages_than_before_resumes_at_its_last_one(self) -> None:
        pager = _opened(3)
        pager.next_page(two_up=False)
        pager.next_page(two_up=False)
        pager.view(two_up=False)
        pager.open(DOC, _pages(2), resume=True)
        assert _shown(pager, two_up=False) == (1, None)

    def test_two_folders_are_remembered_apart(self) -> None:
        pager = _opened(3, resume=True)
        pager.next_page(two_up=False)
        pager.view(two_up=False)
        pager.open(OTHER_DOC, _pages(3, OTHER_DOC), resume=True)
        view = pager.view(two_up=False)
        assert view is not None
        assert view.left == OTHER_DOC / "page-001.png"
        pager.open(DOC, _pages(3), resume=True)
        view = pager.view(two_up=False)
        assert view is not None
        assert view.left == DOC / "page-002.png"

    def test_a_folder_never_shown_resumes_at_its_first_page(self) -> None:
        assert _shown(_opened(3, resume=True), two_up=False) == (0, None)

    def test_a_resumed_document_comes_back_at_its_pair(self) -> None:
        pager = _opened(7)
        pager.next_page(two_up=True)
        pager.next_page(two_up=True)
        pager.view(two_up=True)
        pager.open(DOC, _pages(7), resume=True)
        assert _shown(pager, two_up=True) == (4, 5)


class TestClose:
    def test_a_closed_document_has_no_view_and_does_not_step(self) -> None:
        pager = _opened(4)
        pager.view(two_up=False)
        pager.close()
        assert pager.is_open is False
        assert pager.page_count == 0
        assert pager.view(two_up=True) is None
        assert pager.next_page(two_up=False) is False
        assert pager.prev_page() is False

    def test_a_view_asked_of_a_closed_document_leaves_its_resume_page(self) -> None:
        """A layout change under a closed reader once moved the page it resumed at."""
        pager = _opened(7)
        for _ in range(3):
            pager.next_page(two_up=False)
        pager.view(two_up=False)  # page 4, a pair's right page two-up
        pager.close()
        pager.view(two_up=True)
        pager.open(DOC, _pages(7), resume=True)
        assert _shown(pager, two_up=False) == (3, None)


class TestOpeningAtTheLastPage:
    """A turn back from a chapter's first page opens the chapter before at its end."""

    def test_it_opens_on_the_last_page_whatever_page_was_last_shown(self) -> None:
        pager = _opened(5)
        pager.view(two_up=False)  # page 1 remembered
        pager.open(DOC, _pages(5), resume=True, at_last_page=True)
        assert _shown(pager, two_up=False) == (4, None)
        assert pager.next_page(two_up=False) is False

    def test_two_up_it_shows_the_last_pair(self) -> None:
        pager = DocumentPager()
        pager.open(DOC, _pages(4), resume=False, at_last_page=True)
        assert _shown(pager, two_up=True) == (2, 3)

    def test_two_up_an_odd_last_page_shows_alone(self) -> None:
        pager = DocumentPager()
        pager.open(DOC, _pages(5), resume=False, at_last_page=True)
        assert _shown(pager, two_up=True) == (4, None)

    def test_a_document_with_no_pages_is_still_empty(self) -> None:
        pager = DocumentPager()
        pager.open(DOC, [], resume=False, at_last_page=True)
        assert pager.is_open is False
        assert pager.current_page_index == 0


def test_the_pager_names_the_folder_last_opened() -> None:
    pager = DocumentPager()
    assert pager.doc_dir is None
    pager.open(DOC, _pages(1), resume=False)
    pager.open(OTHER_DOC, _pages(1, OTHER_DOC), resume=False)
    assert pager.doc_dir == OTHER_DOC
