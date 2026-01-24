# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock, PropertyMock, patch

import barks_reader.ui.comic_book_reader
import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE

# noinspection PyProtectedMember
from barks_reader.ui.comic_book_reader import (
    ComicBookReader,
    ComicBookReaderScreen,
    _ComicPageManager,
)
from kivy.uix.floatlayout import FloatLayout


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

        # noinspection PyProtectedMember
        assert pm._first_page_index == 0
        # noinspection PyProtectedMember
        assert pm._last_page_index == 2
        # noinspection PyProtectedMember
        assert (
            pm._current_page_index == -1
        )  # It doesn't set current page index, just first_page_to_read_index
        # noinspection PyProtectedMember
        assert pm._first_page_to_read_index == 0

        pm.set_to_first_page_to_read()
        # noinspection PyProtectedMember
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
        # noinspection PyProtectedMember
        assert pm._current_page_index == 1

        pm.prev_page()
        # noinspection PyProtectedMember
        assert pm._current_page_index == 0

        pm.prev_page()  # Should stay at 0
        # noinspection PyProtectedMember
        assert pm._current_page_index == 0

        pm.goto_last_page()
        # noinspection PyProtectedMember
        assert pm._current_page_index == 4

        pm.next_page()  # Should stay at 4
        # noinspection PyProtectedMember
        assert pm._current_page_index == 4

        pm.goto_start_page()
        # noinspection PyProtectedMember
        assert pm._current_page_index == 0

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
                # noinspection PyProtectedMember
                reader._on_toggle_action_bar_visibility = on_toggle

            return reader

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

        with (
            patch.object(
                barks_reader.ui.comic_book_reader, "get_action_bar_title"
            ) as _mock_get_title,
            patch.object(barks_reader.ui.comic_book_reader.Clock, "schedule_once"),
        ):
            assert reader
            reader.read_comic(
                fanta_info,
                use_fantagraphics_overrides=False,
                comic_book_image_builder=builder,
                page_to_first_goto=COMIC_BEGIN_PAGE,
                page_map=page_map,
            )

            # noinspection PyProtectedMember
            assert reader._current_title_str == "Title"
            # noinspection PyProtectedMember
            reader._comic_book_loader.set_comic.assert_called()
            # noinspection PyProtectedMember,PyUnresolvedReferences
            reader._on_comic_is_ready_to_read.assert_called()

    def test_on_touch_down_navigation(self, reader: ComicBookReader) -> None:
        # Setup navigation mock
        # noinspection PyProtectedMember
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
        # noinspection PyProtectedMember
        reader._page_manager = MagicMock()

        # Case 1: Right margin -> Next page
        # noinspection PyProtectedMember
        mock_nav.is_in_right_margin.return_value = True
        reader.on_touch_down(touch)
        # noinspection PyProtectedMember
        reader._page_manager.next_page.assert_called()

        # Case 2: Left margin -> Prev page
        # noinspection PyProtectedMember
        mock_nav.is_in_right_margin.return_value = False
        # noinspection PyProtectedMember
        mock_nav.is_in_left_margin.return_value = True
        reader.on_touch_down(touch)
        # noinspection PyProtectedMember
        reader._page_manager.prev_page.assert_called()


class TestComicBookReaderScreen:
    @pytest.fixture
    def screen(self) -> ComicBookReaderScreen:
        settings = MagicMock()
        font_manager = MagicMock()
        on_ready = MagicMock()
        on_close = MagicMock()

        # Mock Builder to avoid loading KV
        with (
            patch.object(barks_reader.ui.comic_book_reader.Builder, "load_file"),
            patch.object(barks_reader.ui.comic_book_reader, "ComicBookReader"),
            patch.object(barks_reader.ui.comic_book_reader, "WindowManager"),
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

            screen = ComicBookReaderScreen(settings, "icon.png", font_manager, on_ready, on_close)
            # Mock ids on the instance as well, just in case
            screen.ids = mock_ids
            return screen

    def test_is_active(self, screen: ComicBookReaderScreen) -> None:
        screen.is_active(active=True)
        # noinspection PyProtectedMember
        assert screen._active

        screen.is_active(active=False)
        # noinspection PyProtectedMember
        assert not screen._active

    def test_toggle_screen_mode(self, screen: ComicBookReaderScreen) -> None:
        with (
            patch.object(
                barks_reader.ui.comic_book_reader.WindowManager,
                "is_fullscreen_now",
                return_value=True,
            ),
            patch.object(barks_reader.ui.comic_book_reader.Clock, "schedule_once") as mock_schedule,
        ):
            screen.toggle_screen_mode()
            # Should schedule goto_windowed_mode
            # We can't easily check the lambda, but we can check schedule_once was called
            mock_schedule.assert_called()

    def test_on_touch_down_top_margin(self, screen: ComicBookReaderScreen) -> None:
        touch = MagicMock()

        # Mock comic_book_reader
        screen.comic_book_reader = MagicMock()
        screen.comic_book_reader.is_click_in_top_margin.return_value = True

        # Mock super().on_touch_down to return False (not handled by children)
        # We can't easily mock super(), but since we patched FloatLayout.add_widget,
        # the screen has no children (except what we added manually if any).
        # But wait, we mocked ComicBookReader class, so screen.comic_book_reader is a mock.
        # However, screen itself is a ReaderScreen (Screen).
        # Screen.on_touch_down delegates to children.

        # To avoid super().on_touch_down issues, we can mock it if possible,
        # or ensure children don't handle it.
        # Since we patched add_widget, the screen might be empty or have mocks.

        # Let's assume super().on_touch_down returns False.

        with patch.object(  # noqa: SIM117
            barks_reader.ui.comic_book_reader.WindowManager,
            "is_fullscreen_now",
            return_value=True,
        ):
            # We need to spy on _toggle_action_bar_visibility
            with patch.object(screen, "_toggle_action_bar_visibility") as mock_toggle:
                handled = screen.on_touch_down(touch)
                assert handled is True
                mock_toggle.assert_called_once()

        # Case: Not fullscreen
        with patch.object(  # noqa: SIM117
            barks_reader.ui.comic_book_reader.WindowManager,
            "is_fullscreen_now",
            return_value=False,
        ):
            with patch.object(screen, "_toggle_action_bar_visibility") as mock_toggle:
                handled = screen.on_touch_down(touch)
                # Should return False because top margin click is only handled in fullscreen
                # UNLESS super() handles it.
                # If super() returns False, then False.
                assert handled is False
                mock_toggle.assert_not_called()
