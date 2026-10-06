# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

import io
import zipfile
from collections import OrderedDict
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import barks_reader.ui.comic_book_reader
import pytest
from barks_fantagraphics.barks_covers import get_cover_display_title, get_located_covers
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core import log_markers
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui.comic_book_reader import (
    FIRST_PAGE_REVEAL_TIMEOUT_SECS,
    ComicBookReader,
    ComicBookReaderScreen,
    _ComicPageManager,
)
from kivy.uix.floatlayout import FloatLayout
from PIL import Image as PilImage

_reader_module = barks_reader.ui.comic_book_reader


class TestComicPageManager:
    @pytest.fixture
    def page_manager(self) -> tuple[_ComicPageManager, MagicMock]:
        callback = MagicMock()
        pm = _ComicPageManager(callback)
        return pm, callback

    def test_set_page_map(self, page_manager: tuple[_ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager

        # Create a dummy page map
        page_map = OrderedDict()
        page_map["1"] = PageInfo(
            page_index=0,
            page_type=PageType.BODY,
            display_page_num="1",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        page_map["2"] = PageInfo(
            page_index=1,
            page_type=PageType.BODY,
            display_page_num="2",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )
        page_map["3"] = PageInfo(
            page_index=2,
            page_type=PageType.BODY,
            display_page_num="3",
            srce_page=MagicMock(),
            dest_page=MagicMock(),
        )

        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)

        assert pm._first_page_index == 0
        assert pm._last_page_index == 2
        assert (
            pm._current_page_index == -1
        )  # It doesn't set current page index, just first_page_to_read_index
        assert pm._first_page_to_read_index == 0

        pm.set_to_first_page_to_read()
        assert pm._current_page_index == 0

    def test_navigation(self, page_manager: tuple[_ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )

        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        pm.set_to_first_page_to_read()  # index 0

        pm.next_page()
        assert pm._current_page_index == 1

        pm.prev_page()
        assert pm._current_page_index == 0

        pm.prev_page()  # Should stay at 0
        assert pm._current_page_index == 0

        pm.goto_last_page()
        assert pm._current_page_index == 4

        pm.next_page()  # Should stay at 4
        assert pm._current_page_index == 4

        pm.goto_start_page()
        assert pm._current_page_index == 0

    def test_the_page_edges_log_the_same_markers_in_double_page_mode(
        self, page_manager: tuple[_ComicPageManager, MagicMock], loguru_sink: list[str]
    ) -> None:
        """A GUI test waits on the edge lines whichever mode the reader booted in."""
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):  # units (0, 1), (2, 3), (4)
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        pm.double_page_mode = True
        pm.set_to_first_page_to_read()

        pm.prev_page()
        assert pm._current_page_index == 0
        assert "Already on the first page: current index = 0." in loguru_sink

        pm.goto_last_page()
        assert pm._current_page_index == 4
        pm.next_page()
        assert pm._current_page_index == 4
        assert "Already on the last page: current index = 4." in loguru_sink

    def test_get_image_load_order(self, page_manager: tuple[_ComicPageManager, MagicMock]) -> None:
        pm, _ = page_manager
        page_map = OrderedDict()
        for i in range(5):
            page_map[str(i)] = PageInfo(
                page_index=i,
                page_type=PageType.BODY,
                display_page_num=str(i),
                srce_page=MagicMock(),
                dest_page=MagicMock(),
            )

        # Case 1: Start at beginning
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        order = pm.get_image_load_order()
        assert order == ["0", "1", "2", "3", "4"]

        # Case 2: Start in middle (index 2)
        pm.set_page_map(page_map, "2")
        order = pm.get_image_load_order()
        # Expected: Current(2), Prev(1), Next...(3,4), Prev...(0)
        # 2, 1, 3, 4, 0
        assert order == ["2", "1", "3", "4", "0"]

    def test_no_display_unit_before_the_page_map_or_off_it(
        self, page_manager: tuple[_ComicPageManager, MagicMock]
    ) -> None:
        """Before a comic has pages, and on a page no unit holds, there is no unit."""
        pm, _ = page_manager
        assert pm.get_current_display_unit() is None

        page_map = OrderedDict(
            (
                str(i),
                PageInfo(
                    page_index=i,
                    page_type=PageType.BODY,
                    display_page_num=str(i),
                    srce_page=MagicMock(),
                    dest_page=MagicMock(),
                ),
            )
            for i in range(4)
        )
        pm.set_page_map(page_map, COMIC_BEGIN_PAGE)
        assert pm.get_current_page_index() == -1  # no page chosen yet
        assert pm.get_current_display_unit() is None

        pm.set_to_first_page_to_read()
        unit = pm.get_current_display_unit()
        assert unit is not None
        assert unit.left_page_index == 0


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
            patch.object(barks_reader.ui.comic_book_reader, "ArchivePageImageSource"),
        ):
            # action_bar_title is a StringProperty, so the formatter must yield a str.
            _mock_get_title.return_value = "Title"
            assert reader
            reader.read_comic(
                fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=builder,
                page_to_first_goto=COMIC_BEGIN_PAGE,
                page_map=page_map,
            )

            assert reader._current_title_str == "Title"
            reader._comic_book_loader.set_comic.assert_called()
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

    def test_show_page_renders_immediately_when_loaded(self, reader: ComicBookReader) -> None:
        self._stub_current_page(reader, 3)
        reader._all_loaded = True  # ready fast-path

        with patch.object(reader, "_render_page") as mock_render:
            reader._show_page(None, None)

        mock_render.assert_called_once_with(3, None)
        reader._comic_book_loader.cursor.set_busy.assert_not_called()

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
            reader._show_page(None, None)

        # The current page stays on screen (no blank loading-page flash); the busy
        # cursor + poll signal the wait instead.
        mock_loading.assert_not_called()
        reader._comic_book_loader.cursor.set_busy.assert_called_once()
        reader._comic_book_loader.prioritize_page.assert_called_once_with(3)
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

    def test_double_page_toggle_logs_the_new_mode(
        self, reader: ComicBookReader, loguru_sink: list[str]
    ) -> None:
        reader = self._bare_reader(reader)
        with patch.object(reader, "_show_page"):
            reader.toggle_double_page_mode()
        assert "Double page mode toggled: True." in loguru_sink

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
            reader._show_page(None, None)
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
        module = barks_reader.ui.comic_book_reader
        with (
            patch.object(module, "Clock") as clock,
            patch.object(module, "Window", width=900, height=1300),
            patch.object(
                screen, "_finish_closing_comic", wraps=screen._finish_closing_comic
            ) as fin,
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

    def test_a_reader_not_yet_resized_waits_until_it_fills_the_window(
        self, screen: ComicBookReaderScreen
    ) -> None:
        """Closed from a window into full screen: the old size must not fall out."""
        screen.size = (782, 1225)
        module = barks_reader.ui.comic_book_reader
        with (
            patch.object(module, "Clock") as clock,
            patch.object(module, "Window", width=900, height=1300),
            patch.object(screen, "_finish_closing_comic") as fin,
        ):
            screen._finish_closing_once_laid_out()
            self._run_frames(clock, 3)
            fin.assert_not_called()

            screen.size = (901, 1300)  # laid out, a pixel apart as a resize can land
            self._run_frames(clock, 2)

        fin.assert_called_once_with()

    def test_a_reader_that_never_fills_the_window_still_closes(
        self, screen: ComicBookReaderScreen
    ) -> None:
        screen.size = (100, 100)
        module = barks_reader.ui.comic_book_reader
        with (
            patch.object(module, "Clock") as clock,
            patch.object(module, "Window", width=900, height=1300),
            patch.object(screen, "_finish_closing_comic") as fin,
        ):
            screen._finish_closing_once_laid_out()
            self._run_frames(clock, ComicBookReaderScreen._CLOSE_LAYOUT_MAX_FRAMES)

        fin.assert_called_once_with()

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
        screen.comic_book_reader.open_goto_page_for_keyboard.return_value = None
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
            patch.object(_reader_module, "is_action_bar_visible", return_value=False),
            patch.object(_reader_module, "set_action_bar_visibility") as set_visibility,
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


def test_an_image_in_a_zip_is_read_from_its_bytes(tmp_path: Path) -> None:
    """A panel in the panels zip is a zipfile.Path: its bytes decode to the texture."""
    png = io.BytesIO()
    PilImage.new("RGB", (6, 4), (200, 100, 50)).save(png, format="PNG")
    archive = tmp_path / "panels.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Insets/Story.png", png.getvalue())

    texture = _reader_module.get_image_stream(zipfile.Path(archive, "Insets/Story.png"))

    assert tuple(texture.size) == (6, 4)
