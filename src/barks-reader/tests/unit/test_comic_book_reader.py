# ruff: noqa: SLF001

from __future__ import annotations

import gc
import io
import sys
import types
import weakref
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, PropertyMock, patch

import barks_reader.ui.comic_book_reader
import barks_reader.ui.reader_close_mixin
import pytest
from barks_fantagraphics.barks_covers import get_cover_display_title, get_located_covers
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core import log_markers
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.page_image import PageImage
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
from barks_reader.ui.action_bar_helpers import ACTION_BAR_SIZE_Y
from barks_reader.ui.comic_book_reader import (
    FIRST_PAGE_REVEAL_TIMEOUT_SECS,
    ComicBookReader,
    ComicBookReaderScreen,
)
from kivy.uix.floatlayout import FloatLayout
from PIL import Image as PilImage

if TYPE_CHECKING:
    from kivy.core.image import Texture

_reader_module = barks_reader.ui.comic_book_reader


def _strongly_reaches(start: object, target: object) -> bool:
    """Whether `target` is reachable from `start` by strong references, modules left out."""
    module_dicts = {id(vars(m)) for m in list(sys.modules.values()) if m is not None}
    seen: set[int] = set()
    to_visit = [start]
    while to_visit:
        obj = to_visit.pop()
        if obj is target:
            return True
        if id(obj) in seen or isinstance(obj, (type, types.ModuleType)) or id(obj) in module_dicts:
            continue
        seen.add(id(obj))
        to_visit.extend(gc.get_referents(obj))
    return False


class TestComicBookReader:
    @pytest.fixture
    def reader(self) -> ComicBookReader:
        settings = MagicMock()
        font_manager = MagicMock()
        on_ready = MagicMock()
        on_toggle = MagicMock()

        # Mocking Kivy widgets and properties that might be instantiated
        with (
            patch.object(barks_reader.ui.comic_book_reader, "Image"),
            patch.object(barks_reader.ui.comic_book_reader, "ComicBookLoader"),
            # Use patch.object to be sure we are patching the right module attribute
            patch.object(barks_reader.ui.comic_book_reader, "ReaderNavigation") as mock_nav_cls,
            patch.object(barks_reader.ui.comic_book_reader, "get_image_stream"),
            patch.object(barks_reader.ui.comic_book_reader, "get_monitors") as mock_monitors,
            # Patch FloatLayout.add_widget to avoid Kivy widget tree logic
            patch.object(FloatLayout, "add_widget"),
        ):
            mock_monitors.return_value = [MagicMock(width=1920, height=1080)]

            # Setup ReaderNavigation mock instance
            mock_nav_instance = MagicMock()
            mock_nav_cls.return_value = mock_nav_instance

            reader = ComicBookReader(settings, font_manager, on_ready, on_toggle)

            # Ensure the attribute exists (it should, but just in case of weird Kivy behavior)
            if not hasattr(reader, "_on_toggle_action_bar_visibility"):
                reader._on_toggle_action_bar_visibility = on_toggle

            return reader

    def test_the_reader_names_an_article_as_its_tree_node_is(self) -> None:
        """An article is a non-Barks title: named by its issue, it would read "Extras ... #1"."""
        article = ALL_FANTA_COMIC_BOOK_INFO[Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION]
        assert not article.comic_book_info.is_barks_title
        title = ComicBookReader.get_reader_comic_title(article)
        assert title == "Don Ault: Fantagraphics Introduction"
        assert title != article.comic_book_info.get_title_from_issue_name()

    def test_the_reader_names_a_comic_by_its_title(self) -> None:
        comic = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
        assert ComicBookReader.get_reader_comic_title(comic) == "Lost in the Andes!"

    @staticmethod
    def _place_page(reader: ComicBookReader, texture: object) -> None:
        """Give the (mock) page image a spread fitted at the centre of a 2560x1440 window."""
        image = reader._comic_image
        image.texture = texture
        image.norm_image_size = (1280, 1440)
        image.center_x, image.center_y = 1280, 720
        image.to_window = lambda x, y: (x, y)

    def test_a_page_placement_is_logged_once_where_the_fitted_page_lands(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        """PAGE_PLACED: what the GUI harness holds centred in the window."""
        self._place_page(reader, MagicMock())
        with patch.object(_reader_module, "Window", MagicMock(width=2560, height=1440)):
            reader._log_page_placement(0)
            reader._log_page_placement(0)  # the same placement: not logged again
        expected = log_markers.PAGE_PLACED.format(
            width=1280, height=1440, x=640, y=0, win_width=2560, win_height=1440
        )
        assert [line for line in loguru_sink if line.startswith("Page placed")] == [expected]

    def test_the_loading_placeholder_and_no_page_are_not_logged(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        """Before the reader has laid itself out, the placeholder is at no real place."""
        with patch.object(_reader_module, "Window", MagicMock(width=2560, height=1440)):
            self._place_page(reader, reader._loading_page_texture)
            reader._log_page_placement(0)
            self._place_page(reader, None)
            reader._log_page_placement(0)
        assert not [line for line in loguru_sink if line.startswith("Page placed")]

    def test_logging_afresh_forgets_the_last_placement(self, reader: ComicBookReader) -> None:
        """At rest after a transition the page is logged even where it was."""
        reader._last_page_placement = MagicMock()
        reader._log_page_placement_trigger = MagicMock()
        reader.log_page_placement_afresh()
        assert reader._last_page_placement is None
        reader._log_page_placement_trigger.assert_called_once_with()

    def test_a_layout_change_asks_for_a_placement_log(self, reader: ComicBookReader) -> None:
        reader._log_page_placement_trigger = MagicMock()
        reader._on_page_layout_changed(reader._comic_image, (1, 2))
        reader._log_page_placement_trigger.assert_called_once_with()

    def test_the_page_manager_does_not_keep_the_reader_alive(self, reader: ComicBookReader) -> None:
        """The Kivy bind it replaced held the reader weakly: no cycle, no wait for a full gc."""
        page_manager = reader._page_manager
        page_info = PageInfo(0, "1", PageType.BODY, srce_page=MagicMock(), dest_page=MagicMock())
        page_manager.set_layout(ComicLayout(OrderedDict([("1", page_info)]), "1"), COMIC_BEGIN_PAGE)
        with patch.object(reader, "_render_page") as render_page:
            page_manager.set_to_first_page_to_read()
        render_page.assert_called_once()  # a page change reaches the reader

        assert not _strongly_reaches(page_manager, reader)

    def test_a_page_change_calls_show_page_as_patched_on_the_reader(
        self, reader: ComicBookReader
    ) -> None:
        """The benchmark stubs `_show_page` on the instance; the page change must find it."""
        page_manager = reader._page_manager
        page_info = PageInfo(0, "1", PageType.BODY, srce_page=MagicMock(), dest_page=MagicMock())
        page_manager.set_layout(ComicLayout(OrderedDict([("1", page_info)]), "1"), COMIC_BEGIN_PAGE)
        with (
            patch.object(reader, "_show_page") as show_page,
            patch.object(reader, "_render_page") as render_page,
        ):
            page_manager.set_to_first_page_to_read()
        show_page.assert_called_once_with()
        render_page.assert_not_called()

    def test_a_page_change_after_the_reader_is_gone_shows_nothing(self) -> None:
        shown: list[int] = []

        class Owner:
            def show(self) -> None:
                shown.append(1)

        owner = Owner()
        weak_owner = weakref.ref(owner)
        barks_reader.ui.comic_book_reader._call_if_alive(weak_owner, "show")
        assert shown == [1]
        del owner
        barks_reader.ui.comic_book_reader._call_if_alive(weak_owner, "show")
        assert shown == [1]

    def test_read_comic(self, reader: ComicBookReader) -> None:
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"

        builder = MagicMock()
        page_map = OrderedDict(
            [
                (
                    "1",
                    PageInfo(
                        0,
                        "1",
                        PageType.BODY,
                        srce_page=MagicMock(),
                        dest_page=MagicMock(),
                    ),
                )
            ]
        )

        # Configure the mocked loader to return a proper tuple from resolve_archive_for_comic
        reader._comic_book_loader.resolve_archive_for_comic.return_value = (
            Path("test.cbz"),
            None,
        )
        reader._comic_book_loader.empty_page_image = b"fake"
        reader._comic_book_loader.max_window_width = 800
        reader._comic_book_loader.max_window_height = 600

        with (
            patch.object(
                barks_reader.ui.comic_book_reader, "get_action_bar_title"
            ) as _mock_get_title,
            patch.object(barks_reader.ui.comic_book_reader.Clock, "schedule_once"),
            patch.object(barks_reader.ui.comic_book_reader, "ArchivePageImageSource") as source,
        ):
            # action_bar_title is a StringProperty, so the formatter must yield a str.
            _mock_get_title.return_value = "Title"
            assert reader
            reader.read_comic(
                fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=builder,
                page_to_first_goto=COMIC_BEGIN_PAGE,
                layout=ComicLayout(page_map, last_body_page="1"),
            )

            assert reader._current_title_str == "Title"
            # The page source takes the reader's decode-whole setting as it is.
            assert (
                source.call_args.kwargs["decode_whole"]
                is reader._reader_settings.decode_pages_whole
            )
            reader._comic_book_loader.set_comic.assert_called()
            # One page is awaited: the reader opens on a single page here.
            assert reader._comic_book_loader.set_comic.call_args.kwargs["num_pages_awaited"] == 1
            # The reader screen is held back until page one draws, so opening a comic
            # arms the reveal rather than switching to a blank page.
            reader._on_comic_is_ready_to_read.assert_not_called()
            assert reader._reveal_ev is not None

    @staticmethod
    def _stub_current_page(reader: ComicBookReader, page_index: int) -> None:
        """Point the reader at a single (non-double) page for _show_page tests."""
        reader._page_manager = MagicMock()
        reader._page_manager.get_current_page_index.return_value = page_index
        reader._page_manager.get_current_page_str.return_value = str(page_index)
        reader._page_manager.get_page_str.return_value = str(page_index)
        reader._page_manager.get_current_display_unit.return_value = None
        reader._is_one_pager_collection = False
        reader._is_covers_collection = False

    def test_first_page_drawn_reveals_the_reader_screen(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 0)
        with patch.object(barks_reader.ui.comic_book_reader.Clock, "schedule_once"):
            reader._arm_reveal()

        reader._render_page(0, None)

        reader._on_comic_is_ready_to_read.assert_called_once()
        assert reader._reveal_ev is None

    def test_later_page_turns_do_not_switch_screen_again(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 5)
        assert reader._reveal_ev is None  # nothing armed: the comic is already showing

        reader._render_page(5, None)

        reader._on_comic_is_ready_to_read.assert_not_called()

    def test_reveal_times_out_onto_the_loading_page(self, reader: ComicBookReader) -> None:
        with patch.object(
            barks_reader.ui.comic_book_reader.Clock, "schedule_once"
        ) as mock_schedule:
            reader._arm_reveal()
            on_timeout, delay = mock_schedule.call_args[0]

        assert delay == FIRST_PAGE_REVEAL_TIMEOUT_SECS
        on_timeout(0.0)

        reader._on_comic_is_ready_to_read.assert_called_once()

    def test_closing_before_the_first_page_cancels_the_reveal(
        self, reader: ComicBookReader
    ) -> None:
        """A comic abandoned mid-load must not switch to an empty reader afterwards."""
        reader._closed = False
        with patch.object(barks_reader.ui.comic_book_reader.Clock, "schedule_once"):
            reader._arm_reveal()

        reader.close_comic_book_reader()

        assert reader._reveal_ev is None
        reader._on_comic_is_ready_to_read.assert_not_called()

    def test_a_solo_unit_drawn_in_double_page_mode_leaves_it_two_up(
        self, reader: ComicBookReader
    ) -> None:
        """The cover or an odd last page alone: the screen's bar stays the pair's width."""
        self._stub_current_page(reader, 2)
        reader.two_up = True
        reader._render_page(4, None)
        reader._show_loading_page()
        assert reader.two_up is True

    def test_the_first_page_drawn_says_the_comic_opened_once(self, reader: ComicBookReader) -> None:
        """The opener hears of page one only, not of every page turn after it."""
        self._stub_current_page(reader, 0)
        on_comic_opened = MagicMock()
        reader._on_comic_opened = on_comic_opened

        reader._render_page(0, None)
        reader._render_page(1, None)

        on_comic_opened.assert_called_once_with()
        assert reader._on_comic_opened is None

    def test_a_timed_out_reveal_does_not_say_the_comic_opened(
        self, reader: ComicBookReader
    ) -> None:
        """The reader shown on its loading page has opened nothing yet."""
        on_comic_opened = MagicMock()
        reader._on_comic_opened = on_comic_opened
        with patch.object(
            barks_reader.ui.comic_book_reader.Clock, "schedule_once"
        ) as mock_schedule:
            reader._arm_reveal()
            on_timeout, _delay = mock_schedule.call_args[0]

        on_timeout(0.0)

        on_comic_opened.assert_not_called()
        assert reader._on_comic_opened is on_comic_opened  # page one may still draw

    def test_closing_before_the_first_page_drew_says_nothing_opened(
        self, reader: ComicBookReader
    ) -> None:
        """A load error closes the reader before page one: the comic never opened."""
        reader._closed = False
        on_comic_opened = MagicMock()
        reader._on_comic_opened = on_comic_opened

        reader.close_comic_book_reader()

        assert reader._on_comic_opened is None
        on_comic_opened.assert_not_called()

    def test_show_page_renders_immediately_when_loaded(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 3)
        reader._all_loaded = True  # ready fast-path

        with patch.object(reader, "_render_page") as mock_render:
            reader._show_page()

        mock_render.assert_called_once_with(3, None)
        reader._comic_book_loader.cursor.set_busy.assert_not_called()

    def test_show_page_logs_the_page_its_type_and_its_image(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        """The GUI harness reads it to tell a blank page from a render that failed."""
        self._stub_current_page(reader, 3)
        reader._all_loaded = True
        reader._page_manager.page_map = {"3": MagicMock(page_type=PageType.BLANK_PAGE)}
        image = f'"{log_markers.EMPTY_PAGE_IMAGE}" (from override)'
        reader._comic_book_loader.get_image_info_str.return_value = image

        with patch.object(reader, "_render_page"):
            reader._show_page()

        expected = log_markers.PAGE_IMAGE_SHOWN.format(index=3, page_type="BLANK_PAGE", image=image)
        assert any(expected in line for line in loguru_sink)

    def test_show_page_keeps_current_page_and_polls_when_not_loaded(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        self._stub_current_page(reader, 3)
        reader._all_loaded = False
        reader._comic_book_loader.wait_load_event.return_value = False  # page not ready

        handle = MagicMock()
        with (
            patch.object(reader, "_show_loading_page") as mock_loading,
            patch.object(
                barks_reader.ui.comic_book_reader.Clock, "schedule_interval", return_value=handle
            ) as mock_sched,
        ):
            reader._show_page()

        # The current page stays on screen (no blank loading-page flash); the busy
        # cursor + poll signal the wait instead.
        mock_loading.assert_not_called()
        reader._comic_book_loader.cursor.set_busy.assert_called_once()
        # The loader is asked by the page's name, which only the page manager knows.
        reader._comic_book_loader.prioritize_page.assert_called_once_with("3")
        mock_sched.assert_called_once()
        assert reader._pending_poll_ev is handle
        assert log_markers.PAGE_AWAITING_LOAD.format(index=3) in loguru_sink

    def test_start_pending_poll_does_not_double_schedule(self, reader: ComicBookReader) -> None:
        reader._pending_poll_ev = MagicMock()  # a poll is already running
        with patch.object(
            barks_reader.ui.comic_book_reader.Clock, "schedule_interval"
        ) as mock_sched:
            reader._start_pending_poll()
        mock_sched.assert_not_called()

    def test_poll_renders_and_finishes_when_page_ready(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 3)
        reader._all_loaded = False
        reader._pending_poll_ev = MagicMock()
        reader._comic_book_loader.wait_load_event.return_value = True  # ready now

        with patch.object(reader, "_render_page") as mock_render:
            keep_going = reader._poll_pending_page(0.05)

        assert keep_going is False
        mock_render.assert_called_once_with(3, None)

    def test_poll_keeps_waiting_when_page_not_ready(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 3)
        reader._all_loaded = False
        reader._pending_poll_ev = MagicMock()
        reader._comic_book_loader.wait_load_event.return_value = False  # still loading

        assert reader._poll_pending_page(0.05) is True

    def test_poll_stops_when_comic_closed(self, reader: ComicBookReader) -> None:
        reader._page_manager = MagicMock()
        reader._page_manager.get_current_page_index.return_value = -1  # closed/reset
        reader._pending_poll_ev = MagicMock()

        assert reader._poll_pending_page(0.05) is False
        assert reader._pending_poll_ev is None
        reader._comic_book_loader.cursor.set_normal.assert_called_once()

    def test_stop_pending_poll_cancels_and_restores_cursor(self, reader: ComicBookReader) -> None:
        handle = MagicMock()
        reader._pending_poll_ev = handle

        reader._stop_pending_poll()

        handle.cancel.assert_called_once()
        assert reader._pending_poll_ev is None
        reader._comic_book_loader.cursor.set_normal.assert_called_once()

    def test_on_touch_down_navigation(self, reader: ComicBookReader) -> None:
        # Setup navigation mock
        mock_nav = reader._navigation
        mock_nav.is_in_top_margin.return_value = False
        mock_nav.is_in_left_margin.return_value = False
        mock_nav.is_in_right_margin.return_value = False

        touch = MagicMock()
        touch.x = 100
        touch.y = 100
        reader.x = 0
        reader.y = 0
        reader.width = 200
        reader.height = 200

        # Mock page manager
        reader._page_manager = MagicMock()

        # Case 1: Right margin -> Next page
        mock_nav.is_in_right_margin.return_value = True
        reader.on_touch_down(touch)
        reader._page_manager.next_page.assert_called()

        # Case 2: Left margin -> Prev page
        mock_nav.is_in_right_margin.return_value = False
        mock_nav.is_in_left_margin.return_value = True
        reader.on_touch_down(touch)
        reader._page_manager.prev_page.assert_called()

    def test_margin_presses_log_their_markers(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        mock_nav = reader._navigation
        mock_nav.is_in_top_margin.return_value = False
        touch = MagicMock(x=100, y=60)
        reader.x, reader.y = 0, 0
        reader._page_manager = MagicMock()

        mock_nav.is_in_left_margin.return_value = True
        mock_nav.is_in_right_margin.return_value = False
        reader.on_touch_down(touch)
        mock_nav.is_in_left_margin.return_value = False
        mock_nav.is_in_right_margin.return_value = True
        reader.on_touch_down(touch)

        assert log_markers.LEFT_MARGIN_PRESSED.format(x=100, y=60) in loguru_sink
        assert log_markers.RIGHT_MARGIN_PRESSED.format(x=100, y=60) in loguru_sink

    def test_no_page_turns_once_the_comic_is_closed(self, reader: ComicBookReader) -> None:
        """Leaving fullscreen after Close takes a moment: a turn then must not reach the loader."""
        reader._page_manager = MagicMock()
        reader._closed = False
        with (
            patch.object(reader, "_cancel_reveal"),
            patch.object(reader, "_stop_pending_poll"),
        ):
            reader.close_comic_book_reader()
        reader.next_page()
        reader.prev_page()
        reader._page_manager.next_page.assert_not_called()
        reader._page_manager.prev_page.assert_not_called()

    def test_no_margin_turns_once_the_comic_is_closed(self, reader: ComicBookReader) -> None:
        reader._page_manager = MagicMock()
        reader._navigation.is_in_left_margin.return_value = True
        reader._closed = True
        assert not reader.on_touch_down(MagicMock(x=10, y=10))
        reader._page_manager.prev_page.assert_not_called()

    def test_tap_target_regions_are_the_margins_in_window_pixels(
        self, reader: ComicBookReader
    ) -> None:
        reader._navigation.tap_regions.return_value = {"left margin": (0, 10, 50, 20)}
        reader.x, reader.y = 5, 7
        reader.width, reader.height = 200, 100
        # With no parent, a widget's own position space is the window's.
        assert reader.tap_target_regions() == {"left margin": (5, 17, 50, 20)}
        reader._navigation.tap_regions.assert_called_once_with(200, 100)

    # --- log markers: double page and goto page, for the GUI path tests to wait on ---

    @staticmethod
    def _bare_reader(reader: ComicBookReader) -> ComicBookReader:
        reader._page_manager = MagicMock(double_page_mode=False)
        reader._is_one_pager_collection = False
        reader._is_covers_collection = False
        return reader

    @pytest.mark.parametrize(
        ("opens_two_up", "collection", "two_up"),
        [(False, False, False), (True, False, True), (True, True, False)],
    )
    def test_a_comic_opens_two_up_on_the_spread_unless_a_collection(
        self, reader: ComicBookReader, *, opens_two_up: bool, collection: bool, two_up: bool
    ) -> None:
        """The layout decides (`opens_two_up`); the one-pager and cover collections never pair."""
        reader = self._bare_reader(reader)
        reader.opens_two_up = opens_two_up
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Title"
        fanta_info.comic_book_info.title = (
            Titles.ALL_ONE_PAGERS if collection else Titles.LOST_IN_THE_ANDES
        )
        layout = MagicMock()
        layout.page_map = {COMIC_BEGIN_PAGE: MagicMock()}
        with (
            patch.object(reader, "_stop_pending_poll"),
            patch.object(
                reader._comic_book_loader, "resolve_archive_for_comic", side_effect=RuntimeError
            ),
            pytest.raises(RuntimeError),
        ):
            reader.read_comic(fanta_info, False, MagicMock(), COMIC_BEGIN_PAGE, layout)  # noqa: FBT003
        assert reader._page_manager.double_page_mode is two_up
        assert reader.two_up is two_up

    def test_double_page_toggle_logs_the_new_mode(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        reader = self._bare_reader(reader)
        with patch.object(reader, "_show_page"):
            reader.toggle_double_page_mode()
        assert "Double page mode toggled: True." in loguru_sink
        assert reader.two_up is True

    def test_double_page_toggle_is_ignored_for_single_page_collections(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        reader = self._bare_reader(reader)
        reader._is_one_pager_collection = True
        with patch.object(reader, "_show_page") as show:
            reader.toggle_double_page_mode()
        show.assert_not_called()
        assert "Double page toggle ignored: single-page collection." in loguru_sink

    def test_selecting_a_page_logs_it(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        reader = self._bare_reader(reader)
        with patch.object(reader, "_hide_action_bar_if_fullscreen"):
            reader.on_page_selected(MagicMock(), "12")
        assert 'Goto page selected: "12".' in loguru_sink

    def test_goto_page_off_screen_opens_nothing(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        """Mid-fade the Goto Page button has no window: no dropdown, no 'opened' line."""
        dropdown = MagicMock()
        dropdown.open_if_shown.return_value = False
        reader._goto_page_dropdown = dropdown
        reader._goto_page_buttons = []
        reader._goto_page_widget = MagicMock()
        on_dismiss = MagicMock()

        assert reader.open_goto_page_for_keyboard(on_dismiss) is None
        dropdown.bind.assert_not_called()
        assert log_markers.GOTO_PAGE_DROPDOWN_OPENED not in loguru_sink

    def test_with_the_goto_page_list_gone_a_scroll_or_unbind_does_nothing(
        self, reader: ComicBookReader
    ) -> None:
        """A comic closed with the list open resets it before its dismissal unbinds."""
        reader.reset_comic_book_reader()
        assert reader._goto_page_dropdown is None

        reader.scroll_goto_page_to(MagicMock())
        reader.unbind_goto_page_dismiss(MagicMock())

    def test_the_goto_page_list_opened_by_keyboard_tells_its_dismissal(
        self, reader: ComicBookReader
    ) -> None:
        dropdown = MagicMock()
        reader._goto_page_dropdown = dropdown
        on_dismiss = MagicMock()
        with patch.object(reader, "goto_page", return_value=True):
            assert reader.open_goto_page_for_keyboard(on_dismiss) == 0
        dropdown.bind.assert_called_once_with(on_dismiss=on_dismiss)

    # --- a load error ---

    def test_a_load_warning_closes_the_reader(self, reader: ComicBookReader) -> None:
        reader._all_loaded = True
        with patch.object(reader, "close_comic_book_reader") as close:
            reader._load_error(load_warning_only=True)
        close.assert_called_once()
        assert reader._all_loaded is False

    def test_a_load_error_raises_rather_than_show_a_broken_comic(
        self, reader: ComicBookReader
    ) -> None:
        with (
            patch.object(reader, "close_comic_book_reader") as close,
            pytest.raises(RuntimeError, match="comic book load error"),
        ):
            reader._load_error(load_warning_only=False)
        close.assert_not_called()

    # --- the collections' titles: the cover or one-pager on show names the bar ---

    def test_the_covers_collection_names_the_cover_on_show(self, reader: ComicBookReader) -> None:
        reader = self._bare_reader(reader)
        covers = get_located_covers()[:3]
        reader._is_covers_collection = True
        reader._collection_covers = covers
        reader._page_manager.get_current_page_index.return_value = 1
        reader._page_manager.get_current_page_str.return_value = "2"
        with (
            patch.object(_reader_module, "get_action_bar_title", side_effect=lambda _f, t: t),
            patch.object(reader, "_get_current_display_indices", return_value=(1, None)),
            patch.object(reader, "_pages_ready", return_value=True),
            patch.object(reader, "_render_page"),
        ):
            reader._show_page()
        assert reader.action_bar_title == get_cover_display_title(covers[1])

    @pytest.mark.parametrize("page_str", ["4", "0x"])
    @pytest.mark.parametrize(
        "setter", ["_set_cover_action_bar_title", "_set_one_pager_action_bar_title"]
    )
    def test_a_page_with_no_collection_item_leaves_the_title(
        self, reader: ComicBookReader, setter: str, page_str: str
    ) -> None:
        reader._collection_covers = get_located_covers()[:3]
        reader._collection_one_pagers = [MagicMock()] * 3
        reader.action_bar_title = "as before"
        getattr(reader, setter)(page_str)
        assert reader.action_bar_title == "as before"

    # --- edges ---

    def test_a_touch_a_child_widget_takes_turns_no_page(self, reader: ComicBookReader) -> None:
        """A press on a widget over the page (the goto-page dropdown, say) is that widget's."""
        reader._page_manager = MagicMock()
        reader._navigation.is_in_right_margin.return_value = True
        with patch.object(FloatLayout, "on_touch_down", return_value=True):
            assert reader.on_touch_down(MagicMock(x=100, y=100)) is True
        reader._page_manager.next_page.assert_not_called()

    def test_closing_twice_closes_once(self, reader: ComicBookReader) -> None:
        reader._closed = True
        with patch.object(reader, "_cancel_reveal") as cancel:
            reader.close_comic_book_reader()
        cancel.assert_not_called()

    def test_it_says_whether_the_comic_is_the_one_pager_collection(
        self, reader: ComicBookReader
    ) -> None:
        reader._is_one_pager_collection = True
        assert reader.is_one_pager_collection is True
        reader._is_one_pager_collection = False
        assert reader.is_one_pager_collection is False

    def test_goto_page_focuses_the_first_button_when_none_is_the_page_on_show(
        self, reader: ComicBookReader
    ) -> None:
        """The page on show is not in the list (a cover, say): the focus starts at the top."""
        reader._goto_page_dropdown = MagicMock()
        reader._goto_page_buttons = [MagicMock(text="1"), MagicMock(text="2")]
        reader._page_manager = MagicMock()
        reader._page_manager.page_map = {
            "1": MagicMock(page_index=3),
            "2": MagicMock(page_index=4),
        }
        reader._page_manager.get_current_page_index.return_value = 0
        on_dismiss = MagicMock()
        with patch.object(reader, "goto_page", return_value=True):
            assert reader.open_goto_page_for_keyboard(on_dismiss) == 0
        reader._goto_page_dropdown.bind.assert_called_once_with(on_dismiss=on_dismiss)

    def test_goto_page_colours_the_pages_the_tag_marks(self, reader: ComicBookReader) -> None:
        """Opened through a tag: its pages stand out, though the page on show stays yellow."""
        cbr = barks_reader.ui.comic_book_reader
        reader._goto_page_dropdown = MagicMock()
        reader._goto_page_widget = MagicMock()
        reader._goto_page_buttons = [MagicMock(text=str(page)) for page in range(1, 5)]
        reader._page_manager = MagicMock()
        reader._page_manager.page_map = {
            str(page): MagicMock(page_index=page - 1, page_type=PageType.BODY)
            for page in range(1, 5)
        }
        reader._page_manager.get_current_page_index.return_value = 0  # page "1"
        reader._tagged_pages = frozenset({"1", "3"})
        with patch.object(cbr, "open_dropdown", return_value=True):
            assert reader.goto_page()
        colours = [button.background_color for button in reader._goto_page_buttons]
        assert colours == [
            cbr.GOTO_PAGE_BUTTON_CURRENT_PAGE_COLOR,
            cbr.GOTO_PAGE_BUTTON_BODY_COLOR,
            cbr.GOTO_PAGE_BUTTON_TAGGED_COLOR,
            cbr.GOTO_PAGE_BUTTON_BODY_COLOR,
        ]

    def test_the_goto_page_dropdown_is_dismissed_only_once_made(
        self, reader: ComicBookReader
    ) -> None:
        reader._goto_page_dropdown = None
        reader.dismiss_goto_page_dropdown()  # nothing made yet: nothing to dismiss

        dropdown = MagicMock()
        reader._goto_page_dropdown = dropdown
        reader.dismiss_goto_page_dropdown()
        dropdown.dismiss.assert_called_once_with()


class TestComicBookReaderScreen:
    @pytest.fixture
    def screen(self) -> ComicBookReaderScreen:
        settings = MagicMock()
        font_manager = MagicMock()
        window_manager = MagicMock()
        on_ready = MagicMock()
        on_close = MagicMock()

        # Mock Builder to avoid loading KV
        with (
            patch.object(barks_reader.ui.comic_book_reader.Builder, "load_file"),
            patch.object(barks_reader.ui.comic_book_reader, "ComicBookReader"),
            # Mock ids property on ComicBookReaderScreen
            patch.object(ComicBookReaderScreen, "ids", new_callable=PropertyMock) as mock_ids_prop,
            # Patch FloatLayout.add_widget to avoid Kivy widget tree logic
            patch.object(FloatLayout, "add_widget"),
        ):
            # Set up the mock ids object (MagicMock supports dot access)
            mock_ids = MagicMock()
            mock_ids.action_bar = MagicMock()
            mock_ids.fullscreen_button = MagicMock()
            mock_ids.goto_page_button = MagicMock()
            mock_ids.image_layout = MagicMock()

            mock_ids_prop.return_value = mock_ids

            screen = ComicBookReaderScreen(
                settings, "icon.png", font_manager, window_manager, on_ready, on_close
            )
            # Mock ids on the instance as well, just in case
            screen.ids = mock_ids
            return screen

    def test_entering_logs_the_page_placement_afresh(
        self, screen: ComicBookReaderScreen, loguru_sink: list[str]
    ) -> None:
        """Once the screen is at rest, after the line the GUI harness reads it entered by."""
        screen.comic_book_reader = MagicMock()
        screen.on_enter()
        assert log_markers.SCREEN_ENTERED.format(name=screen.name) in loguru_sink
        screen.comic_book_reader.log_page_placement_afresh.assert_called_once_with()

    def test_is_active(self, screen: ComicBookReaderScreen) -> None:
        screen.is_active(active=True)
        assert screen._active

        screen.is_active(active=False)
        assert not screen._active

    @pytest.mark.parametrize(
        ("finish", "reason"),
        [
            ("_on_finished_goto_windowed_mode", "ComicBookReaderScreen windowed"),
            ("_on_finished_goto_fullscreen_mode", "ComicBookReaderScreen fullscreen"),
        ],
    )
    def test_a_settled_mode_change_logs_the_window_geometry(
        self, screen: ComicBookReaderScreen, finish: str, reason: str
    ) -> None:
        with (
            patch.object(screen, "_update_widget_states"),
            patch.object(screen, "_update_fullscreen_button"),
            patch.object(barks_reader.ui.comic_book_reader, "WindowManager"),
            patch.object(barks_reader.ui.comic_book_reader, "log_window_geometry") as log_geometry,
        ):
            getattr(screen, finish)()

        log_geometry.assert_called_once_with(reason)

    @staticmethod
    def _run_frames(clock: MagicMock, frames: int) -> None:
        """Run what the reader scheduled, a frame at a time, as the clock would."""
        for _ in range(frames):
            if not clock.schedule_once.call_args_list:
                return
            callback = clock.schedule_once.call_args_list.pop(0).args[0]
            callback(0)

    def test_a_reader_already_filling_the_window_closes_a_frame_later(
        self, screen: ComicBookReaderScreen, loguru_sink: list[str]
    ) -> None:
        """The frame lets the page inside the reader follow its size."""
        screen.size = (900, 1300)
        mixin = barks_reader.ui.reader_close_mixin
        with (
            patch.object(mixin, "Clock") as clock,
            patch.object(mixin, "Window", width=900, height=1300),
            patch.object(barks_reader.ui.comic_book_reader, "Window", width=900, height=1300),
            patch.object(screen, "_finish_closing", wraps=screen._finish_closing) as fin,
        ):
            screen._finish_closing_once_laid_out()
            fin.assert_not_called()
            self._run_frames(clock, 1)

        fin.assert_called_once_with()
        screen._on_close_reader.assert_called_once_with()
        assert (
            log_markers.READER_CLOSING.format(
                width=900, height=1300, win_width=900, win_height=1300
            )
            in loguru_sink
        )

    @pytest.mark.parametrize(
        "finish", ["_on_finished_goto_windowed_mode", "_on_finished_goto_fullscreen_mode"]
    )
    def test_a_close_waits_for_the_layout_whichever_mode_it_returns_to(
        self, screen: ComicBookReaderScreen, finish: str
    ) -> None:
        screen._is_closing = True
        with (
            patch.object(screen, "_update_widget_states"),
            patch.object(screen, "_update_fullscreen_button"),
            patch.object(barks_reader.ui.comic_book_reader, "WindowManager"),
            patch.object(screen, "_finish_closing_once_laid_out") as wait,
        ):
            getattr(screen, finish)()

        wait.assert_called_once_with()

    def test_goto_page_off_screen_stays_in_menu_mode(self, screen: ComicBookReaderScreen) -> None:
        """Enter on Goto Page mid-fade opens nothing; the menu keeps its focus."""
        cast("MagicMock", screen.comic_book_reader).open_goto_page_for_keyboard.return_value = None
        with (
            patch.object(screen, "_enter_dropdown_nav") as enter_dropdown_nav,
            patch.object(screen, "_update_menu_focus") as update_menu_focus,
        ):
            screen._open_goto_page_for_keyboard()
        enter_dropdown_nav.assert_not_called()
        update_menu_focus.assert_called_once()

    def test_keys_are_swallowed_while_the_reader_closes(
        self, screen: ComicBookReaderScreen
    ) -> None:
        """Close in fullscreen closes the comic, then leaves fullscreen: no key acts meanwhile."""
        screen._is_closing = True
        with patch.object(screen, "_handle_reader_key") as handle:
            assert screen._on_key_down(MagicMock(), 276, 0, "", [])  # Left
        handle.assert_not_called()

    def test_a_key_is_handled_when_not_closing(self, screen: ComicBookReaderScreen) -> None:
        screen._is_closing = False
        with patch.object(screen, "_handle_reader_key", return_value=True) as handle:
            assert screen._on_key_down(MagicMock(), 276, 0, "", [])
        handle.assert_called_once_with(276)

    def test_taps_are_swallowed_while_the_reader_closes(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen._is_closing = True
        with patch.object(screen, "_clear_menu_on_touch") as clear_menu:
            assert screen.on_touch_down(MagicMock())
        clear_menu.assert_not_called()

    def test_toggle_screen_mode(self, screen: ComicBookReaderScreen) -> None:
        # The toggle scaffolding lives in WindowModeController now; the screen just
        # delegates to it. (The controller's own toggle logic is unit-tested in
        # test_window_manager.py.)
        screen._mode = MagicMock()

        screen.toggle_screen_mode()

        screen._mode.toggle.assert_called_once_with()

    def test_on_touch_down_top_margin(self, screen: ComicBookReaderScreen) -> None:
        touch = MagicMock()

        # Mock comic_book_reader
        screen.comic_book_reader = MagicMock()
        screen.comic_book_reader.is_click_in_top_margin.return_value = True

        # Case: action bar hidden -> top margin click should show it.
        with patch.object(screen, "_is_action_bar_hidden", return_value=True):  # noqa: SIM117
            with patch.object(screen, "_show_action_bar") as mock_show:
                handled = screen.on_touch_down(touch)
                assert handled is True
                mock_show.assert_called_once()

        # Case: action bar visible -> top margin click is NOT consumed (passes through to
        # the action bar buttons).
        with patch.object(screen, "_is_action_bar_hidden", return_value=False):  # noqa: SIM117
            with patch.object(screen, "_show_action_bar") as mock_show:
                handled = screen.on_touch_down(touch)
                assert handled is False
                mock_show.assert_not_called()

    def test_the_menu_over_a_visible_action_bar_leaves_it_as_it_is(
        self, screen: ComicBookReaderScreen
    ) -> None:
        """Windowed, the bar is always up: entering the menu has nothing to show."""
        with (
            patch.object(_reader_module, "is_action_bar_visible", return_value=True),
            patch.object(_reader_module, "set_action_bar_visibility") as set_visibility,
        ):
            screen._on_action_bar_shown_for_menu()
        set_visibility.assert_not_called()

    def test_the_menu_over_a_hidden_action_bar_shows_it(
        self, screen: ComicBookReaderScreen
    ) -> None:
        with (
            patch.object(
                barks_reader.ui.reader_close_mixin, "is_action_bar_visible", return_value=False
            ),
            patch.object(
                barks_reader.ui.reader_close_mixin, "set_action_bar_visibility"
            ) as set_visibility,
        ):
            screen._on_action_bar_shown_for_menu()
        set_visibility.assert_called_once()

    def test_dismissing_the_dropdown_dismisses_the_readers_goto_page_list(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen.comic_book_reader = MagicMock()
        screen._dismiss_dropdown()
        screen.comic_book_reader.dismiss_goto_page_dropdown.assert_called_once_with()

    def test_leaving_the_screen_in_menu_mode_leaves_menu_mode(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen._menu_mode = True
        with patch.object(screen, "_exit_menu_mode") as exit_menu_mode:
            screen.is_active(active=False)
        exit_menu_mode.assert_called_once_with()

    def test_a_fullscreen_switch_that_failed_says_so_and_keeps_the_real_mode(
        self, screen: ComicBookReaderScreen, loguru_sink: list[str]
    ) -> None:
        """The button and action bar follow the window as it is, not as it was asked to be."""
        with (
            patch.object(screen, "_update_widget_states"),
            patch.object(screen, "_update_fullscreen_button"),
            patch.object(_reader_module, "WindowManager") as window_manager,
            patch.object(_reader_module, "log_window_geometry"),
        ):
            window_manager.is_fullscreen_now.return_value = False
            window_manager.get_screen_mode_now.return_value = "windowed"
            screen._on_finished_goto_fullscreen_mode()

        assert screen.is_fullscreen is False
        assert any(
            "Finishing goto fullscreen on ComicBookReaderScreen but Window fullscreen" in line
            and "'windowed'" in line
            for line in loguru_sink
        )

    # --- the bar is as wide as the pages under it ---

    @pytest.mark.parametrize(
        ("window", "two_up", "expected_width"),
        [
            # The spread window on a 2560x1440 monitor: a page, then the pair.
            ((1775, 1365), False, round((1365 - ACTION_BAR_SIZE_Y) / COMIC_PAGE_ASPECT_RATIO)),
            ((1775, 1365), True, round((1365 - ACTION_BAR_SIZE_Y) / COMIC_PAGE_ASPECT_RATIO * 2)),
            # The single-page window: the pair is width-limited to the window.
            ((874, 1365), True, 874),
        ],
    )
    def test_the_bar_is_as_wide_as_the_pages_under_it(
        self,
        screen: ComicBookReaderScreen,
        window: tuple[int, int],
        two_up: bool,
        expected_width: int,
    ) -> None:
        """A page wide in single-page mode, the pair's width in double-page mode."""
        cast("MagicMock", screen.comic_book_reader).two_up = two_up
        with patch.object(_reader_module, "Window", width=window[0], height=window[1]):
            screen._reset_action_bar_width()
        assert screen.action_bar_width == expected_width

    def test_the_bar_refits_as_the_mode_changes(self, screen: ComicBookReaderScreen) -> None:
        """A comic's load and the Double Page toggle set the mode; the bar follows it."""
        binds = cast("MagicMock", screen.comic_book_reader).bind.call_args_list
        on_change = next(call.kwargs["two_up"] for call in binds if "two_up" in call.kwargs)
        with patch.object(screen, "_reset_action_bar_width") as reset:
            on_change(screen.comic_book_reader, False)  # noqa: FBT003
        reset.assert_called_once_with()

    # --- the goto-page dropdown opened from its bar button ---

    @staticmethod
    def _ids_with(screen: ComicBookReaderScreen) -> MagicMock:
        """Return the bar ids as the nav list knows them: the goto button is its last entry."""
        ids = MagicMock()
        ids.goto_page_button = screen._menu_buttons[-1]
        return ids

    def test_opened_from_the_bar_the_dropdown_is_in_keyboard_nav(
        self, screen: ComicBookReaderScreen
    ) -> None:
        """A press on the bar button is no keyboard path, yet the arrows must work in it."""
        screen._menu_mode = False
        cast("MagicMock", screen.comic_book_reader).open_goto_page_for_keyboard.return_value = 3
        with (
            patch.object(
                ComicBookReaderScreen,
                "ids",
                new_callable=PropertyMock,
                return_value=self._ids_with(screen),
            ),
            patch.object(screen, "_enter_menu_mode") as enter_menu,
            patch.object(screen, "_exit_menu_mode") as exit_menu,
            patch.object(screen, "_clear_menu_focus"),
            patch.object(
                screen,
                "_enter_dropdown_nav",
                side_effect=lambda **_kw: setattr(screen, "_dropdown_nav_mode", True),
            ) as enter_dropdown,
        ):
            screen.open_goto_page_from_bar()
        enter_menu.assert_called_once_with()
        enter_dropdown.assert_called_once_with(initial_idx=3)
        exit_menu.assert_not_called()
        assert screen._last_used_btn_idx == len(screen._menu_buttons) - 1

    def test_a_dropdown_that_does_not_open_from_the_bar_leaves_no_focus_on_it(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen._menu_mode = False
        cast("MagicMock", screen.comic_book_reader).open_goto_page_for_keyboard.return_value = None
        with (
            patch.object(
                ComicBookReaderScreen,
                "ids",
                new_callable=PropertyMock,
                return_value=self._ids_with(screen),
            ),
            patch.object(
                screen,
                "_enter_menu_mode",
                side_effect=lambda: setattr(screen, "_menu_mode", True),
            ) as enter_menu,
            patch.object(screen, "_exit_menu_mode") as exit_menu,
            patch.object(screen, "_clear_menu_focus"),
            patch.object(screen, "_update_menu_focus"),
        ):
            screen.open_goto_page_from_bar()
        enter_menu.assert_called_once_with()
        exit_menu.assert_called_once_with()

    def test_pressed_from_the_bar_in_menu_mode_the_menu_is_kept(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen._menu_mode = True
        cast("MagicMock", screen.comic_book_reader).open_goto_page_for_keyboard.return_value = None
        with (
            patch.object(
                ComicBookReaderScreen,
                "ids",
                new_callable=PropertyMock,
                return_value=self._ids_with(screen),
            ),
            patch.object(screen, "_enter_menu_mode") as enter_menu,
            patch.object(screen, "_exit_menu_mode") as exit_menu,
            patch.object(screen, "_clear_menu_focus"),
            patch.object(screen, "_update_menu_focus"),
        ):
            screen.open_goto_page_from_bar()
        enter_menu.assert_not_called()
        exit_menu.assert_not_called()


def test_an_image_in_a_zip_is_read_from_its_bytes(tmp_path: Path) -> None:
    """A panel in the panels zip is a zipfile.Path: its bytes decode to the texture."""
    png = io.BytesIO()
    PilImage.new("RGB", (6, 4), (200, 100, 50)).save(png, format="PNG")
    archive = tmp_path / "panels.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Insets/Story.png", png.getvalue())

    texture = _reader_module.get_image_stream(zipfile.Path(archive, "Insets/Story.png"))

    assert tuple(texture.size) == (6, 4)


def test_a_loaded_page_fills_a_texture_the_right_way_up() -> None:
    """The page's pixels go straight into a texture; PIL rows run top-down, so it is flipped."""
    page = PageImage.from_pil(PilImage.new("RGB", (6, 4), (200, 100, 50)))

    texture = _reader_module.page_texture(page)

    assert tuple(texture.size) == (6, 4)
    assert texture.colorfmt == "rgb"
    assert texture.uvsize[1] < 0


def _rendered(texture: Texture) -> bytes:
    """Draw *texture* into an offscreen buffer and return the pixels it put there."""
    from kivy.graphics import ClearBuffers, ClearColor, Fbo, Rectangle  # noqa: PLC0415

    fbo = Fbo(size=texture.size)
    with fbo:
        ClearColor(0, 0, 0, 1)
        ClearBuffers()
        Rectangle(texture=texture, pos=(0, 0), size=texture.size)
    fbo.draw()
    return bytes(fbo.pixels)


def test_a_page_texture_draws_what_the_kivy_loader_would() -> None:
    """Orientation and colors: the page's texture renders pixel for pixel as the PNG did.

    An asymmetric image, so a flipped or mirrored texture would show.
    """
    pil = PilImage.new("RGB", (4, 3), (0, 0, 255))
    for x in range(4):
        pil.putpixel((x, 0), (255, 0, 0))
    pil.putpixel((0, 2), (0, 255, 0))
    png = io.BytesIO()
    pil.save(png, format="PNG")
    png.seek(0)

    from_png = _rendered(_reader_module.CoreImage(png, ext="png").texture)
    from_page = _rendered(_reader_module.page_texture(PageImage.from_pil(pil)))

    assert from_page == from_png
