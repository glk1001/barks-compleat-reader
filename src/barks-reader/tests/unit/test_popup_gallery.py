"""The popup gallery: every popup the app owns, opened on request or by Page Up/Down."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import log_markers
from barks_reader.core import popup_gallery as core_gallery
from barks_reader.core.keys import KEY_ENTER, KEY_PAGE_DOWN, KEY_PAGE_UP
from barks_reader.core.popup_frame import FrameButton
from barks_reader.core.popup_gallery import (
    LIVE_MODE,
    POPUP_GALLERY_ENV_VAR,
    POPUP_NAMES,
    error_popup_name,
    parse_request,
    request_text,
)
from barks_reader.core.user_error_messages import build_error_presentation
from barks_reader.core.user_error_types import ErrorTypes
from barks_reader.ui import main_screen as main_screen_module
from barks_reader.ui import popup_frame, popup_gallery, request_service
from barks_reader.ui.popup_frame import PopupFrame
from barks_reader.ui.popup_gallery import GALLERY, GalleryPopup
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.properties import ListProperty, NumericProperty  # ty: ignore[unresolved-import]
from kivy.uix.label import Label

if TYPE_CHECKING:
    from pathlib import Path


class TestNames:
    def test_a_user_errors_name_is_its_type_in_kebab_case(self) -> None:
        name = error_popup_name(ErrorTypes.MissingArchiveVolumes)
        assert name == "error-missing-archive-volumes"

    def test_every_name_is_once_in_the_gallery_in_its_order(self) -> None:
        assert len(set(POPUP_NAMES)) == len(POPUP_NAMES)
        assert tuple(popup.name for popup in GALLERY) == POPUP_NAMES

    def test_every_user_error_is_shown(self) -> None:
        for error_type in ErrorTypes:
            assert error_popup_name(error_type) in POPUP_NAMES

    def test_a_request_reads_back_as_written(self) -> None:
        assert parse_request(request_text("single-3", "quit")) == ("single-3", "quit")

    @pytest.mark.parametrize("text", ["", "quit", "1 quit extra"])
    def test_a_request_not_an_id_and_a_name_is_none(self, text: str) -> None:
        assert core_gallery.parse_request(text) is None


class TestSamples:
    @pytest.mark.parametrize("error_type", list(ErrorTypes))
    def test_each_user_errors_sample_makes_its_message(self, error_type: ErrorTypes) -> None:
        sample = popup_gallery._ERROR_SAMPLES[error_type]  # noqa: SLF001
        presentation = build_error_presentation(error_type, sample, MagicMock())
        assert presentation.text

    def test_the_offer_and_the_no_update_say_their_piece(self) -> None:
        offer = popup_gallery._sample_update_check(popup_gallery.UpdateStatus.UPDATE_AVAILABLE)  # noqa: SLF001
        assert "Install it now?" in offer.offer_message()
        none_new = popup_gallery._sample_update_check(popup_gallery.UpdateStatus.PACKS_MISSING)  # noqa: SLF001
        assert "barks-reader-data-2.barkspack" in none_new.no_update_message()


class TestOpeners:
    def test_quit_opens_the_main_screens_popup_over_its_art(self) -> None:
        app = MagicMock()
        with patch.object(popup_gallery, "open_quit_popup") as open_quit:
            popup_gallery._BY_NAME["quit"].open(app)  # noqa: SLF001
        art = str(app.reader_settings.sys_file_paths.get_app_identity_image_file.return_value)
        open_quit.assert_called_once_with(art, popup_gallery._ignore)  # noqa: SLF001

    def test_a_user_error_goes_through_the_apps_handler(self) -> None:
        app = MagicMock()
        name = error_popup_name(ErrorTypes.MissingArchiveVolumes)
        with patch.object(popup_gallery, "UserErrorHandler") as handler_cls:
            popup_gallery._BY_NAME[name].open(app)  # noqa: SLF001
        handler_cls.return_value.handle_error.assert_called_once()
        assert handler_cls.return_value.handle_error.call_args.args[0] is (
            ErrorTypes.MissingArchiveVolumes
        )


class TestShowPopup:
    def test_an_unknown_name_is_logged_and_opens_nothing(self, loguru_sink: list[str]) -> None:
        with patch.object(popup_gallery, "close_open_popups") as close:
            assert popup_gallery.show_popup(MagicMock(), "no-such", request="4") is False
        close.assert_not_called()
        assert log_markers.POPUP_GALLERY_UNKNOWN.format(request="4", name="no-such") in (
            loguru_sink
        )

    def test_the_last_popup_closes_and_the_named_one_opens_a_frame_later(
        self, loguru_sink: list[str]
    ) -> None:
        app = MagicMock()
        opener = MagicMock()
        with (
            patch.dict(popup_gallery._BY_NAME, {"quit": GalleryPopup("quit", opener)}),  # noqa: SLF001
            patch.object(popup_gallery, "close_open_popups") as close,
            patch.object(Clock, "schedule_once") as schedule,
        ):
            assert popup_gallery.show_popup(app, "quit", request="7") is True
            close.assert_called_once_with()
            opener.assert_not_called()
            schedule.call_args.args[0](0)
        opener.assert_called_once_with(app)
        assert log_markers.POPUP_GALLERY_SHOWN.format(request="7", name="quit") in loguru_sink


def test_the_about_box_in_the_gallery_is_opened_by_the_main_screens_own_function() -> None:
    """Built by lines of its own, it kept showing the old box when the screen's changed."""
    app = MagicMock()
    with (
        patch.object(main_screen_module, "show_about_box") as show,
        patch.object(main_screen_module.data_pack, "read_installed", return_value=None) as read,
    ):
        popup_gallery._open_about(app)  # noqa: SLF001

    read.assert_called_once_with(app.reader_settings.reader_files_dir)
    assert show.call_args.args[0] is app.font_manager
    assert show.call_args.kwargs == {
        "on_dismiss": None,
        "data_pack_text": "Data pack: not versioned",
    }


class TestService:
    def test_nothing_runs_without_the_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(POPUP_GALLERY_ENV_VAR, raising=False)
        assert popup_gallery.install_popup_gallery_service(MagicMock()) is False

    def test_a_request_written_to_the_file_opens_its_popup(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        request_file = tmp_path / "popup-request"
        monkeypatch.setenv(POPUP_GALLERY_ENV_VAR, str(request_file))
        app = MagicMock()
        with patch.object(Clock, "schedule_interval") as schedule:
            assert popup_gallery.install_popup_gallery_service(app) is True
        poll = schedule.call_args.args[0]
        assert schedule.call_args.args[1] == request_service.POLL_SECS

        request_file.write_text(request_text("2", "about"), encoding="utf-8")
        with patch.object(popup_gallery, "show_popup") as show:
            poll(0)
            poll(0)  # taken once: the file is gone
        show.assert_called_once_with(app, "about", request="2")

    def test_a_malformed_request_is_logged(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        request_file = tmp_path / "popup-request"
        monkeypatch.setenv(POPUP_GALLERY_ENV_VAR, str(request_file))
        with patch.object(Clock, "schedule_interval") as schedule:
            popup_gallery.install_popup_gallery_service(MagicMock())
        request_file.write_text("about", encoding="utf-8")
        with patch.object(popup_gallery, "show_popup") as show:
            schedule.call_args.args[0](0)
        show.assert_not_called()
        assert log_markers.POPUP_GALLERY_UNKNOWN.format(request="?", name="about") in loguru_sink

    def test_live_mode_starts_the_stepper(
        self, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        monkeypatch.setenv(POPUP_GALLERY_ENV_VAR, LIVE_MODE)
        with patch.object(Clock, "schedule_once") as schedule:
            assert popup_gallery.install_popup_gallery_service(MagicMock()) is True
        schedule.assert_called_once()
        assert log_markers.POPUP_GALLERY_LIVE.format(count=len(GALLERY)) in loguru_sink


class _KeyWindow(EventDispatcher):
    """A window that hands keys to its handlers as Kivy's does: the one bound last first."""

    __events__ = ("on_key_down",)
    size = ListProperty([1760, 1300])
    width = NumericProperty(1760)
    height = NumericProperty(1300)

    def on_key_down(self, *_args: object) -> None:
        """Take no key itself."""

    def add_widget(self, _widget: object) -> None:
        """Hold no widget."""

    def remove_widget(self, _widget: object) -> None:
        """Hold no widget."""


class TestLiveGallery:
    def test_page_down_gets_past_a_popup_that_keeps_every_key(self) -> None:
        window = _KeyWindow()
        with (
            patch.object(popup_gallery, "Window", window),
            patch.object(popup_frame, "Window", window),
            patch.object(popup_gallery, "show_popup") as show,
            patch.object(popup_frame, "update_focus_in_list"),
            patch.object(Clock, "schedule_once"),
        ):
            live = popup_gallery._LiveGallery(MagicMock())  # noqa: SLF001
            live.start()
            frame = PopupFrame(title="T", body=Label(), buttons=(FrameButton("OK", MagicMock()),))
            frame.dispatch("on_pre_open")  # the popup the gallery opened binds the keys
            live._come_to_front()  # noqa: SLF001  # as it does once the popup is up
            window.dispatch("on_key_down", KEY_PAGE_DOWN, 0, "", [])
            frame.dispatch("on_dismiss")
        show.assert_called_once()

    def _press(self, live: popup_gallery._LiveGallery, key: int) -> bool:
        return live._on_key_down(None, key, 0, "", [])  # noqa: SLF001

    def test_page_down_and_up_step_through_wrapping_round(self) -> None:
        app = MagicMock()
        live = popup_gallery._LiveGallery(app)  # noqa: SLF001
        with (
            patch.object(popup_gallery, "show_popup") as show,
            patch.object(Clock, "schedule_once"),
        ):
            assert self._press(live, KEY_PAGE_DOWN) is True
            assert self._press(live, KEY_PAGE_UP) is True
            assert self._press(live, KEY_PAGE_UP) is True
        names = [call.args[1] for call in show.call_args_list]
        assert names == [GALLERY[0].name, GALLERY[-1].name, GALLERY[-2].name]

    def test_every_other_key_is_left_to_the_popup(self) -> None:
        live = popup_gallery._LiveGallery(MagicMock())  # noqa: SLF001
        with patch.object(popup_gallery, "show_popup") as show:
            assert self._press(live, KEY_ENTER) is False
        show.assert_not_called()
