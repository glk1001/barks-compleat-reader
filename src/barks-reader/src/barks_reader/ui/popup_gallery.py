"""The popup gallery: every popup the app owns, opened on request, to look them over.

The popups were written one at a time and do not look alike (the plan that sets them
right is ``docs/plans/popup-consistency.md``). The gallery opens each with sample
content through the very function its screen calls, so what it shows is what the app
shows. It runs only when ``POPUP_GALLERY_ENV_VAR`` is set, which no normal run does:

- ``live``: Page Down and Page Up step through the popups in the running app, a
  corner label naming each. The popup's own keys are left to it; every button it
  has is a no-op here, so nothing a press does reaches the profile. The app imports
  this module only when the variable is set, so no normal run depends on it.
- a file path: the app answers requests written to that file, as the GUI probe's
  frame requests are answered (``ui.frame_capture``). A request ``<id> <name>``
  closes any open popup, opens the one named and logs ``POPUP_GALLERY_SHOWN``;
  ``scripts/popup_gallery.py`` then captures the window and asks for the next.

The popups that run in their own window before the app does (the first-run
installer, the error popup, the data pack success) are not here: the script runs
each by its own preview.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.search_results import PageInfo, SpeechInfo, TitleInfo
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.data_pack import DataPackInfo, UpdateCheck, UpdateStatus
from barks_reader.core.keys import KEY_PAGE_DOWN, KEY_PAGE_UP
from barks_reader.core.popup_gallery import (
    LIVE_MODE,
    POPUP_GALLERY_ENV_VAR,
    POPUP_NAMES,
    error_popup_name,
    parse_request,
)
from barks_reader.core.reader_palette import DEFAULT_THEME_NAME, THEME_NAMES
from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

from .alt_escape_capture_popup import AltEscapeCapturePopup
from .history_screen import open_clear_history_popup, open_delete_from_history_popup
from .index_screen import create_speech_bubble_popup, show_speech_bubbles_popup
from .main_screen import (
    open_about_popup,
    open_data_pack_offer_popup,
    open_no_data_pack_update_popup,
    open_quit_popup,
    open_small_screen_popup,
)
from .request_service import install_request_service
from .settings_fix import SettingNumberPopup, SettingOptionsPopup, open_folder_chooser_popup
from .user_error_handler import UserErrorHandler

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager

# The live gallery or a popup's key handler, held here because Kivy holds them only weakly.
_SERVICE: list[object] = []


class GalleryApp(Protocol):
    """What the gallery's openers need from the running app."""

    @property
    def reader_settings(self) -> ReaderSettings:
        """The app's settings."""

    @property
    def font_manager(self) -> FontManager:
        """The app's font manager."""


@dataclass(frozen=True, slots=True)
class GalleryPopup:
    """One popup: its name in the gallery and how to open it with sample content."""

    name: str
    open: Callable[[GalleryApp], None]


def _ignore(*_args: object) -> None:
    """Stand in for every button's action: nothing a gallery press does sticks."""


class _SettingStandIn:
    """The setting a folder chooser hands its choice to, here a no-op."""

    def update_setting_value(self, _new_path: str) -> None:
        """Take the chosen folder and drop it."""


def _sample_pack(version: int, built_at: datetime) -> DataPackInfo:
    return DataPackInfo(version, f"data-v{version}", built_at, "gallery", {})


def _sample_update_check(status: UpdateStatus) -> UpdateCheck:
    from datetime import UTC, datetime  # noqa: PLC0415

    installed = _sample_pack(6, datetime(2026, 10, 29, tzinfo=UTC))
    offered = _sample_pack(7, datetime(2026, 11, 14, tzinfo=UTC))
    return UpdateCheck(
        status,
        Path.home() / "Downloads",
        installed,
        packs=(offered, offered),
        missing=("barks-reader-data-2.barkspack",),
    )


def _sample_title_speech() -> TitleInfo:
    def page(comic_page: str, *lines: str) -> PageInfo:
        speech = [
            SpeechInfo(str(group), group, text, text, speaker="donald")
            for group, text in enumerate(lines, start=1)
        ]
        return PageInfo(comic_page, speech)

    return TitleInfo(
        fanta_vol=7,
        fanta_pages={
            "3": page("3", "Square eggs! Who ever heard of square eggs?"),
            "7": page(
                "7",
                "These square eggs will make us rich, boys!",
                "If we can get them home without breaking.",
            ),
            "21": page("21", "Square chickens lay square eggs, of course!"),
        },
    )


# What each user error's popup is shown with: the fields its message reads.
_ERROR_SAMPLES: dict[ErrorTypes, ErrorInfo | None] = {
    ErrorTypes.FantagraphicsVolumeRootNotSet: None,
    ErrorTypes.FantagraphicsVolumeRootNotFound: ErrorInfo(
        file="/media/greg/Barks/Fantagraphics Carl Barks Library"
    ),
    ErrorTypes.DuplicateVolumeArchiveFiles: ErrorInfo(
        file="/media/greg/Barks/Fantagraphics Carl Barks Library", duplicate_volumes=[7, 12]
    ),
    ErrorTypes.MissingArchiveVolumes: ErrorInfo(missing_volumes=[5, 9, 14]),
    ErrorTypes.MissingVolumeCannotShowTitle: ErrorInfo(
        missing_volumes=[7], title=Titles.LOST_IN_THE_ANDES
    ),
    ErrorTypes.ArchiveVolumeNotAvailable: ErrorInfo(file_volume=7, title=Titles.LOST_IN_THE_ANDES),
    ErrorTypes.ComicLoadFailed: ErrorInfo(title=Titles.LOST_IN_THE_ANDES),
}


def _identity_art(app: GalleryApp) -> str:
    return str(app.reader_settings.sys_file_paths.get_app_identity_image_file())


def _open_user_error(error_type: ErrorTypes) -> Callable[[GalleryApp], None]:
    def open_it(app: GalleryApp) -> None:
        handler = UserErrorHandler(app.reader_settings, _ignore)
        handler.handle_error(error_type, _ERROR_SAMPLES[error_type], on_popup_closed=_ignore)

    return open_it


def _open_about(app: GalleryApp) -> None:
    open_about_popup(app.font_manager, app.reader_settings)


def _open_speech_bubbles(app: GalleryApp) -> None:
    fm = app.font_manager
    popup, nav = create_speech_bubble_popup(fm.speech_bubble_popup_title_font_name)
    _SERVICE.append(nav)  # the screens hold theirs; the keys work while it is up
    show_speech_bubbles_popup(
        popup,
        "Lost in the Andes!",
        "square eggs",
        _sample_title_speech(),
        _ignore,
        text_font_size=fm.speech_bubble_text_font_size,
    )


def _open_alt_escape(_app: GalleryApp) -> None:
    AltEscapeCapturePopup(current_keycode=0, on_capture=_ignore, on_clear=_ignore).open()


# How each popup in `POPUP_NAMES` (``core.popup_gallery``) is opened.
_OPENERS: dict[str, Callable[[GalleryApp], None]] = {
    "quit": lambda app: open_quit_popup(_identity_art(app), _ignore),
    "delete-reading": lambda _app: open_delete_from_history_popup(None, _ignore),
    "delete-title-readings": lambda _app: open_delete_from_history_popup(
        "Lost in the Andes!", _ignore
    ),
    "clear-history": lambda _app: open_clear_history_popup(_ignore),
    "data-pack-offer": lambda app: open_data_pack_offer_popup(
        _sample_update_check(UpdateStatus.UPDATE_AVAILABLE), _ignore, _identity_art(app), None
    ),
    "data-pack-no-update": lambda _app: open_no_data_pack_update_popup(
        _sample_update_check(UpdateStatus.PACKS_MISSING), None
    ),
    "small-screen": lambda _app: open_small_screen_popup(1280, 720),
    **{error_popup_name(error_type): _open_user_error(error_type) for error_type in _ERROR_SAMPLES},
    "about": _open_about,
    "speech-bubbles": _open_speech_bubbles,
    "folder-chooser": lambda _app: open_folder_chooser_popup(
        "Fantagraphics Directory", str(Path.home()), _SettingStandIn()
    ),
    "alt-escape-key": _open_alt_escape,
    "setting-options": lambda _app: SettingOptionsPopup(
        "Color Theme", THEME_NAMES, DEFAULT_THEME_NAME, _ignore
    ).open(),
    "setting-number": lambda _app: SettingNumberPopup("Main Window Height", "0", _ignore).open(),
}

GALLERY: tuple[GalleryPopup, ...] = tuple(
    GalleryPopup(name, _OPENERS[name]) for name in POPUP_NAMES
)

_BY_NAME = {popup.name: popup for popup in GALLERY}


def close_open_popups() -> None:
    """Take every popup off the window at once, with no closing animation."""
    for widget in list(Window.children):
        if isinstance(widget, ModalView):
            widget.dismiss(animation=False)


def show_popup(app: GalleryApp, name: str, request: str = "") -> bool:
    """Close any open popup and open the one named, on the next frame.

    Args:
        app: The running app.
        name: A name in `GALLERY`.
        request: The request id to log it under ("" in live mode).

    Returns:
        Whether the name is in the gallery.

    """
    popup = _BY_NAME.get(name)
    if popup is None:
        logger.warning(log_markers.POPUP_GALLERY_UNKNOWN.format(request=request, name=name))
        return False
    close_open_popups()

    def open_it(_dt: float) -> None:
        popup.open(app)
        logger.debug(log_markers.POPUP_GALLERY_SHOWN.format(request=request, name=name))

    # A frame after the closing, so the last popup has left the window first.
    Clock.schedule_once(open_it, 0)
    return True


class _LiveGallery:
    """Page Down and Page Up through the popups, a corner label naming each."""

    def __init__(self, app: GalleryApp) -> None:
        self._app = app
        self._index = -1
        self._label = Label(
            text="Popup gallery: Page Down for the first popup",
            font_size=sp(16),
            size_hint=(None, None),
            halign="left",
            valign="middle",
            padding=(dp(10), dp(6)),
        )
        self._label.bind(texture_size=self._fit_label)
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with self._label.canvas.before:  # ty: ignore[missing-union-attribute]
            Color(0, 0, 0, 0.8)
            self._label_bg = Rectangle()
        self._label.bind(pos=self._fit_label_bg, size=self._fit_label_bg)

    def _fit_label(self, label: Label, texture_size: tuple[float, float]) -> None:
        label.size = texture_size
        label.pos = (dp(8), dp(8))

    def _fit_label_bg(self, label: Label, _value: object) -> None:
        self._label_bg.pos = label.pos
        self._label_bg.size = label.size

    def start(self) -> None:
        self._come_to_front()

    def _come_to_front(self, *_args: object) -> None:
        """Take the keys ahead of any popup, and put the label on top of the window.

        Kivy hands a key to the handler bound last first, and a popup on the frame binds
        at opening and keeps every key; so the gallery binds again after each popup is
        up, or Page Down would never get past the first.
        """
        Window.unbind(on_key_down=self._on_key_down)
        Window.bind(on_key_down=self._on_key_down)
        if self._label.parent is not None:
            Window.remove_widget(self._label)
        Window.add_widget(self._label)

    def _on_key_down(
        self, _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list[str]
    ) -> bool:
        if key not in (KEY_PAGE_DOWN, KEY_PAGE_UP):
            return False
        step = 1 if key == KEY_PAGE_DOWN else -1
        self._index = (self._index + step) % len(GALLERY)
        popup = GALLERY[self._index]
        show_popup(self._app, popup.name)
        self._label.text = (
            f"{self._index + 1}/{len(GALLERY)}  {popup.name}    (Page Up / Page Down)"
        )
        # After the popup is up: it opens a frame from now, some a frame after that.
        Clock.schedule_once(self._come_to_front, 0.3)
        return True


def install_popup_gallery_service(app: GalleryApp) -> bool:
    """Run the gallery when ``POPUP_GALLERY_ENV_VAR`` asks for it; else do nothing.

    The live gallery starts a frame after the app's build, when the window has its
    screens, so its label is over them and its keys are bound after theirs (Kivy hands
    a key to the handler bound last first); each popup it opens it gets ahead of again.

    Args:
        app: The running app.

    Returns:
        Whether the gallery is running.

    """
    mode = os.environ.get(POPUP_GALLERY_ENV_VAR, "")
    if not mode:
        return False
    if mode == LIVE_MODE:
        live = _LiveGallery(app)
        _SERVICE.append(live)
        Clock.schedule_once(lambda _dt: live.start(), 0)
        logger.info(log_markers.POPUP_GALLERY_LIVE.format(count=len(GALLERY)))
        return True

    def answer(text: str, _out_dir: Path) -> None:
        parsed = parse_request(text)
        if parsed is None:
            logger.warning(log_markers.POPUP_GALLERY_UNKNOWN.format(request="?", name=text))
            return
        show_popup(app, parsed[1], request=parsed[0])

    # Any other value of the variable is the file a script writes its requests to.
    return install_request_service(POPUP_GALLERY_ENV_VAR, "Popup gallery", answer)
