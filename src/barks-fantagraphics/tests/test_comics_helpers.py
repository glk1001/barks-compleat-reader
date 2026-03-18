# ruff: noqa: PLR2004, FBT003

from __future__ import annotations

from unittest.mock import MagicMock, patch

import barks_fantagraphics.comics_helpers as comics_helpers_module
import pytest
from barks_fantagraphics.comics_helpers import (
    draw_panel_bounds_on_image,
    get_display_title,
    get_issue_title,
    get_issue_titles,
    get_title_from_volume_page,
    get_titles,
    get_titles_and_info,
)
from barks_fantagraphics.panel_boxes import PagePanelBoxes, PanelBox
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> MagicMock:
    return MagicMock()


def _make_fanta_info(is_barks: bool = True) -> MagicMock:
    info = MagicMock()
    info.comic_book_info.is_barks_title = is_barks
    return info


def _make_panel_box(panel_num: int, x0: int, y0: int, x1: int, y1: int) -> PanelBox:
    return PanelBox(panel_num=panel_num, x0=x0, y0=y0, x1=x1, y1=y1, w=x1 - x0, h=y1 - y0)


# ---------------------------------------------------------------------------
# get_titles_and_info
# ---------------------------------------------------------------------------


class TestGetTitlesAndInfo:
    def test_single_title_returns_one_tuple(self) -> None:
        db = _make_db()
        fanta_info = _make_fanta_info()
        db.get_fanta_comic_book_info.return_value = fanta_info

        result = get_titles_and_info(db, [], "My Title")

        db.get_fanta_comic_book_info.assert_called_once_with("My Title")
        assert result == [("My Title", fanta_info)]

    def test_both_title_and_volumes_raises(self) -> None:
        db = _make_db()
        with pytest.raises(AssertionError):
            get_titles_and_info(db, [1], "My Title")

    def test_neither_title_nor_volumes_raises(self) -> None:
        db = _make_db()
        with pytest.raises(AssertionError):
            get_titles_and_info(db, [], "")

    def test_volumes_configured_only_true(self) -> None:
        db = _make_db()
        expected = [("T1", _make_fanta_info()), ("T2", _make_fanta_info())]
        db.get_configured_titles_in_fantagraphics_volumes.return_value = expected

        result = get_titles_and_info(db, [1, 2], "", configured_only=True)

        db.get_configured_titles_in_fantagraphics_volumes.assert_called_once_with([1, 2], False)
        assert result == expected

    def test_volumes_configured_only_false(self) -> None:
        db = _make_db()
        expected = [("T1", _make_fanta_info())]
        db.get_all_titles_in_fantagraphics_volumes.return_value = expected

        result = get_titles_and_info(db, [1], "", configured_only=False)

        db.get_all_titles_in_fantagraphics_volumes.assert_called_once_with([1])
        assert result == expected

    def test_exclude_non_comics_passed_through(self) -> None:
        db = _make_db()
        db.get_configured_titles_in_fantagraphics_volumes.return_value = []

        get_titles_and_info(db, [1], "", configured_only=True, exclude_non_comics=True)

        db.get_configured_titles_in_fantagraphics_volumes.assert_called_once_with([1], True)


# ---------------------------------------------------------------------------
# get_titles
# ---------------------------------------------------------------------------


class TestGetTitles:
    def test_submission_date_sorted_true_delegates_to_sorter(self) -> None:
        db = _make_db()
        fanta_info = _make_fanta_info()
        db.get_configured_titles_in_fantagraphics_volumes.return_value = [
            ("B Title", fanta_info),
            ("A Title", fanta_info),
        ]

        with patch.object(
            comics_helpers_module,
            "get_titles_sorted_by_submission_date",
            return_value=["A Title", "B Title"],
        ) as mock_sort:
            result = get_titles(db, [1], "", submission_date_sorted=True)

        mock_sort.assert_called_once()
        assert result == ["A Title", "B Title"]

    def test_submission_date_sorted_false_preserves_order(self) -> None:
        db = _make_db()
        fanta_info = _make_fanta_info()
        db.get_configured_titles_in_fantagraphics_volumes.return_value = [
            ("B Title", fanta_info),
            ("A Title", fanta_info),
        ]

        result = get_titles(db, [1], "", submission_date_sorted=False)

        assert result == ["B Title", "A Title"]

    def test_single_title_bypasses_volume_lookup(self) -> None:
        db = _make_db()
        fanta_info = _make_fanta_info()
        db.get_fanta_comic_book_info.return_value = fanta_info

        result = get_titles(db, [], "Exact Title", submission_date_sorted=False)

        assert result == ["Exact Title"]


# ---------------------------------------------------------------------------
# get_issue_titles
# ---------------------------------------------------------------------------


class TestGetIssueTitles:
    def test_returns_correct_four_tuple(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (True, "")
        fanta_info = MagicMock()
        fanta_info.get_short_issue_title.return_value = "WDC 001"

        result = get_issue_titles(db, [("My Title", fanta_info)])

        assert len(result) == 1
        ttl, issue_title, info, is_configured = result[0]
        assert ttl == "My Title"
        assert issue_title == "WDC 001"
        assert info is fanta_info
        assert is_configured is True

    def test_empty_list_returns_empty(self) -> None:
        db = _make_db()
        assert get_issue_titles(db, []) == []

    def test_not_configured_flag(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (False, "")
        fanta_info = MagicMock()
        fanta_info.get_short_issue_title.return_value = "FOO 002"

        result = get_issue_titles(db, [("Unconfigured", fanta_info)])

        _, _, _, is_configured = result[0]
        assert is_configured is False

    def test_multiple_items(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (True, "")
        info_a = MagicMock()
        info_a.get_short_issue_title.return_value = "WDC 001"
        info_b = MagicMock()
        info_b.get_short_issue_title.return_value = "WDC 002"

        result = get_issue_titles(db, [("Title A", info_a), ("Title B", info_b)])

        assert len(result) == 2
        assert result[0][0] == "Title A"
        assert result[1][0] == "Title B"


# ---------------------------------------------------------------------------
# get_display_title
# ---------------------------------------------------------------------------


class TestGetDisplayTitle:
    def test_not_configured_returns_title_as_is(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (False, "")

        result = get_display_title(db, "Some Title")

        assert result == "Some Title"

    def test_configured_barks_title_returns_title_as_is(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (True, "")
        fanta_info = MagicMock()
        fanta_info.comic_book_info.is_barks_title = True
        db.get_fanta_comic_book_info.return_value = fanta_info

        result = get_display_title(db, "Barks Story")

        assert result == "Barks Story"

    def test_configured_non_barks_title_returns_in_parens(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (True, "")
        fanta_info = MagicMock()
        fanta_info.comic_book_info.is_barks_title = False
        db.get_fanta_comic_book_info.return_value = fanta_info

        result = get_display_title(db, "Non-Barks Story")

        assert result == "(Non-Barks Story)"


# ---------------------------------------------------------------------------
# get_issue_title
# ---------------------------------------------------------------------------


class TestGetIssueTitle:
    def test_not_configured_returns_title_as_is(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (False, "")

        result = get_issue_title(db, "Unknown Title")

        assert result == "Unknown Title"

    def test_configured_returns_safe_issue_title(self) -> None:
        db = _make_db()
        db.is_story_title.return_value = (True, "")
        comic = MagicMock()
        comic.get_comic_issue_title.return_value = "WDC & S 001: Some Title"
        db.get_comic_book.return_value = comic

        with patch.object(
            comics_helpers_module, "get_safe_title", return_value="WDC and S 001 Some Title"
        ) as mock_safe:
            result = get_issue_title(db, "Configured Title")

        mock_safe.assert_called_once_with("WDC & S 001: Some Title")
        assert result == "WDC and S 001 Some Title"


# ---------------------------------------------------------------------------
# get_title_from_volume_page
# ---------------------------------------------------------------------------


def _make_srce_dest_pages(page_stems: list[str], dest_page_nums: list[int]) -> MagicMock:
    srce_pages = [MagicMock(page_filename=f"{stem}.jpg") for stem in page_stems]
    dest_pages = [MagicMock(page_num=num) for num in dest_page_nums]
    result = MagicMock()
    result.srce_pages = srce_pages
    result.dest_pages = dest_pages
    return result


class TestGetTitleFromVolumePage:
    def test_page_found_returns_title_and_page_num(self) -> None:
        db = _make_db()
        db.get_all_titles_in_fantagraphics_volumes.return_value = [("Found Title", MagicMock())]
        db.get_comic_book.return_value = MagicMock()
        srce_dest = _make_srce_dest_pages(["page-001", "page-002"], [10, 11])

        with patch.object(
            comics_helpers_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            title, page_num = get_title_from_volume_page(db, 1, "page-002")

        assert title == "Found Title"
        assert page_num == 11

    def test_page_not_found_returns_empty_and_minus_one(self) -> None:
        db = _make_db()
        db.get_all_titles_in_fantagraphics_volumes.return_value = [("Some Title", MagicMock())]
        db.get_comic_book.return_value = MagicMock()
        srce_dest = _make_srce_dest_pages(["page-001"], [5])

        with patch.object(
            comics_helpers_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            title, page_num = get_title_from_volume_page(db, 1, "page-999")

        assert title == ""
        assert page_num == -1

    def test_stops_at_first_matching_title(self) -> None:
        db = _make_db()
        titles = [("Title One", MagicMock()), ("Title Two", MagicMock())]
        db.get_all_titles_in_fantagraphics_volumes.return_value = titles
        db.get_comic_book.side_effect = [MagicMock(), MagicMock()]
        srce_dest1 = _make_srce_dest_pages(["page-001"], [3])
        srce_dest2 = _make_srce_dest_pages(["page-002"], [7])

        with patch.object(
            comics_helpers_module,
            "get_sorted_srce_and_dest_pages",
            side_effect=[srce_dest1, srce_dest2],
        ):
            title, page_num = get_title_from_volume_page(db, 1, "page-001")

        assert title == "Title One"
        assert page_num == 3
        assert db.get_comic_book.call_count == 1

    def test_no_titles_returns_empty(self) -> None:
        db = _make_db()
        db.get_all_titles_in_fantagraphics_volumes.return_value = []

        title, page_num = get_title_from_volume_page(db, 1, "page-001")

        assert title == ""
        assert page_num == -1


# ---------------------------------------------------------------------------
# draw_panel_bounds_on_image
# ---------------------------------------------------------------------------


class TestDrawPanelBoundsOnImage:
    def _make_page_panel_boxes(self, panels: list[PanelBox], overall: PanelBox) -> PagePanelBoxes:
        return PagePanelBoxes(
            page_num="001",
            page_width=100,
            page_height=200,
            overall_bounds=overall,
            panel_boxes=panels,
        )

    def test_returns_true(self) -> None:
        image = Image.new("RGB", (100, 200))
        overall = _make_panel_box(0, 0, 0, 100, 200)
        ppb = self._make_page_panel_boxes([], overall)

        assert draw_panel_bounds_on_image(image, ppb) is True

    def test_with_panels_and_overall_bound(self) -> None:
        image = Image.new("RGB", (100, 200))
        panel = _make_panel_box(1, 10, 20, 50, 80)
        overall = _make_panel_box(0, 0, 0, 100, 200)
        ppb = self._make_page_panel_boxes([panel], overall)

        assert draw_panel_bounds_on_image(image, ppb, include_overall_bound=True) is True

    def test_include_overall_bound_false(self) -> None:
        image = Image.new("RGB", (100, 200))
        panel = _make_panel_box(1, 10, 20, 50, 80)
        overall = _make_panel_box(0, 0, 0, 100, 200)
        ppb = self._make_page_panel_boxes([panel], overall)

        assert draw_panel_bounds_on_image(image, ppb, include_overall_bound=False) is True

    def test_multiple_panels(self) -> None:
        image = Image.new("RGB", (200, 400))
        panels = [
            _make_panel_box(1, 0, 0, 100, 200),
            _make_panel_box(2, 100, 200, 200, 400),
        ]
        overall = _make_panel_box(0, 0, 0, 200, 400)
        ppb = self._make_page_panel_boxes(panels, overall)

        assert draw_panel_bounds_on_image(image, ppb) is True
