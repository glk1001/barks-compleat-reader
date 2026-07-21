from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any, ClassVar

from barks_fantagraphics.fanta_comics_info import NUM_VOLUMES
from comic_utils.timing import Timing
from kivy.clock import Clock
from loguru import logger

from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    MissingArchiveFilesError,
    TooManyArchiveFilesError,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_settings import UNSET_FANTA_DIR_MARKER
from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

from .tree_view_nodes import BaseTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget

    from barks_reader.core.comic_reader_manager import ComicReaderManager
    from barks_reader.core.json_settings_manager import SettingsManager
    from barks_reader.core.reader_settings import ReaderSettings

    from .reader_tree_builder import ReaderTreeBuilder
    from .tree_view_manager import TreeViewManager
    from .tree_view_screen import TreeViewScreen
    from .user_error_handler import UserErrorHandler
    from .view_renderer import ViewRenderer


class _FantaVolumesState(Enum):
    VOLUMES_EXIST = auto()
    ALL_VOLUMES_MISSING = auto()
    SOME_VOLUMES_MISSING = auto()
    VOLUMES_NOT_SET = auto()
    VOLUMES_TOO_MANY = auto()
    DUPLICATE_VOLUMES = auto()
    VOLUMES_NOT_NEEDED = auto()


# No usable library, but the app stays fully browsable: show a single startup notice and
# still build the bundled override/extra pages, so the restored censored stories read.
# (VOLUMES_EXIST / SOME_VOLUMES_MISSING / VOLUMES_NOT_NEEDED are the ordinary ready states.)
_NO_LIBRARY_FANTA_VOLUMES_STATE = {
    _FantaVolumesState.VOLUMES_NOT_SET,
    _FantaVolumesState.ALL_VOLUMES_MISSING,
}
# Misconfiguration the user must fix and restart; reading is blocked with a popup.
_BAD_FANTA_VOLUMES_STATE = {
    _FantaVolumesState.VOLUMES_TOO_MANY,
    _FantaVolumesState.DUPLICATE_VOLUMES,
}


class AppInitializer:
    """Handles the application's startup sequence."""

    _FANTA_STATE_ERROR_MAP: ClassVar[dict[_FantaVolumesState, tuple[str, ErrorTypes]]] = {
        _FantaVolumesState.VOLUMES_NOT_SET: (
            "Fantagraphics Directory Not Set",
            ErrorTypes.FantagraphicsVolumeRootNotSet,
        ),
        _FantaVolumesState.ALL_VOLUMES_MISSING: (
            "Fantagraphics Directory Not Found",
            ErrorTypes.FantagraphicsVolumeRootNotFound,
        ),
        _FantaVolumesState.VOLUMES_TOO_MANY: (
            "Too Many Archive Files in Fantagraphics Directory",
            ErrorTypes.TooManyVolumeArchiveFiles,
        ),
        _FantaVolumesState.DUPLICATE_VOLUMES: (
            "Duplicate Archive Files in Fantagraphics Directory",
            ErrorTypes.DuplicateVolumeArchiveFiles,
        ),
    }

    def __init__(
        self,
        reader_settings: ReaderSettings,
        user_error_handler: UserErrorHandler,
        comic_reader_manager: ComicReaderManager,
        json_settings_manager: SettingsManager,
        renderer: ViewRenderer,
        tree_view_manager: TreeViewManager,
        tree_view_screen: TreeViewScreen,
    ) -> None:
        self._reader_settings = reader_settings
        self._user_error_handler = user_error_handler
        self._comic_reader_manager = comic_reader_manager
        self._json_settings_manager = json_settings_manager
        self._tree_view_screen = tree_view_screen
        self._tree_view_manager = tree_view_manager
        self._renderer = renderer

        self._fanta_volumes_state: _FantaVolumesState = _FantaVolumesState.VOLUMES_NOT_SET
        self._fanta_volumes_error_info: ErrorInfo | None = None
        self._on_tree_build_finished: Callable[[], None] | None = None

    def start(
        self, tree_builder: ReaderTreeBuilder, on_tree_build_finished: Callable[[], None]
    ) -> None:
        """Kick off the entire application initialization and tree build process."""
        self._on_tree_build_finished = on_tree_build_finished
        Clock.schedule_once(lambda _dt: tree_builder.build_main_screen_tree(), 0)

    def on_tree_build_finished(self, _instance: Widget) -> None:
        logger.debug("Received the 'on_finished_building_event' - dismiss the loading popup.")

        assert self._on_tree_build_finished is not None
        self._on_tree_build_finished()

        self._post_build_setup()

    def _post_build_setup(self) -> None:
        """Handle all setup tasks that must occur after the tree is built."""
        timing = Timing()
        try:
            self._fanta_volumes_state = self._get_post_build_fanta_volumes_state()
            logger.debug(f"_fanta_volumes_state = {self._fanta_volumes_state}.")

            self._renderer.render_state(ViewStates.INITIAL)

            # No usable library: show one dismissible notice, but keep going so the
            # bundled override/extra pages (e.g. the restored censored stories) still
            # load and the whole app stays browsable.
            no_library = self._fanta_volumes_state in _NO_LIBRARY_FANTA_VOLUMES_STATE
            if no_library:
                self._show_no_library_notice(self._fanta_volumes_state)

            if not self._init_comic_book_data(library_notice_shown=no_library):
                return

            if self._reader_settings.goto_saved_node_on_start:
                saved_node_path, saved_node_state = (
                    self._json_settings_manager.get_last_selected_node_path()
                )
                if saved_node_path:
                    self._goto_saved_node(saved_node_path, saved_node_state)
        finally:
            logger.info(f"Time of post tree setup: {timing.get_elapsed_time_with_unit()}.")

    def _goto_saved_node(
        self, saved_node_path: list[str], saved_node_state: dict[str, Any]
    ) -> None:
        logger.debug(f'Looking for saved node "{saved_node_path}"...')
        saved_node = self._tree_view_screen.find_node_by_path(saved_node_path)
        if saved_node:
            assert isinstance(saved_node, BaseTreeViewNode)
            saved_node.saved_state = saved_node_state
            self._tree_view_manager.setup_and_select_node(saved_node)

    def is_fanta_volumes_state_ok(self) -> tuple[bool, str]:
        if self._fanta_volumes_state not in _BAD_FANTA_VOLUMES_STATE:
            return True, ""

        reason, error_type = self.get_bad_fanta_volumes_reason()

        self._handle_error_ui(
            error_type,
            self._fanta_volumes_error_info,
            msg=f"Cannot Load Comic: {reason}",
        )

        return False, reason

    def get_bad_fanta_volumes_reason(self) -> tuple[str, ErrorTypes]:
        if self._fanta_volumes_state in self._FANTA_STATE_ERROR_MAP:
            return self._FANTA_STATE_ERROR_MAP[self._fanta_volumes_state]

        msg = f'Unexpected fanta volumes state: "{self._fanta_volumes_state}".'
        raise RuntimeError(msg)

    def _show_no_library_notice(self, state: _FantaVolumesState) -> None:
        """Show a single notice that the Fantagraphics library isn't available.

        The app stays fully browsable, so this deliberately does not set the persistent
        'files not loaded' tree overlay, and fires once. ``state`` selects the wording:
        VOLUMES_NOT_SET points at the unset setting, anything else at a directory that
        holds no readable volumes.
        """
        error_type = (
            ErrorTypes.FantagraphicsVolumeRootNotSet
            if state is _FantaVolumesState.VOLUMES_NOT_SET
            else ErrorTypes.FantagraphicsVolumeRootNotFound
        )
        # A no-op close callback: the notice is informational and must not set the
        # persistent overlay (unlike `_handle_error_ui`).
        self._user_error_handler.handle_error(error_type, None, lambda _msg: None)

    def _get_post_build_fanta_volumes_state(self) -> _FantaVolumesState:
        if self._reader_settings.use_prebuilt_archives:
            return _FantaVolumesState.VOLUMES_NOT_NEEDED
        if str(self._reader_settings.fantagraphics_volumes_dir) == UNSET_FANTA_DIR_MARKER:
            return _FantaVolumesState.VOLUMES_NOT_SET
        if not self._reader_settings.fantagraphics_volumes_dir.is_dir():
            return _FantaVolumesState.ALL_VOLUMES_MISSING
        return _FantaVolumesState.VOLUMES_EXIST

    def _init_comic_book_data(self, *, library_notice_shown: bool = False) -> bool:
        try:
            self._comic_reader_manager.init_comic_book_data()
        except TooManyArchiveFilesError as e:
            self._fanta_volumes_state = _FantaVolumesState.VOLUMES_TOO_MANY
            self._fanta_volumes_error_info = ErrorInfo(
                num_volumes=e.num_volumes, num_archive_files=e.num_archive_files
            )
            self._handle_error_ui(
                ErrorTypes.TooManyVolumeArchiveFiles, self._fanta_volumes_error_info
            )
            return False
        except DuplicateArchiveFilesError as e:
            self._fanta_volumes_state = _FantaVolumesState.DUPLICATE_VOLUMES
            self._fanta_volumes_error_info = ErrorInfo(
                file=str(e.archive_root), duplicate_volumes=e.duplicates
            )
            self._handle_error_ui(
                ErrorTypes.DuplicateVolumeArchiveFiles, self._fanta_volumes_error_info
            )
            return False
        except MissingArchiveFilesError as e:
            self._fanta_volumes_state = _FantaVolumesState.SOME_VOLUMES_MISSING
            self._fanta_volumes_error_info = ErrorInfo(missing_volumes=e.missing_file_vols)
            if library_notice_shown:
                # The one-time no-library notice was already shown up front (unset or
                # non-existent dir); stay quiet and don't set the persistent overlay.
                pass
            elif len(e.missing_file_vols) >= NUM_VOLUMES:
                # The dir exists but holds no volumes at all: same "no library"
                # experience - one browsable notice, no per-volume list, no overlay.
                self._show_no_library_notice(_FantaVolumesState.ALL_VOLUMES_MISSING)
            else:
                # A genuinely partial library: keep the informational per-volume popup.
                self._handle_error_ui(
                    ErrorTypes.MissingArchiveVolumes, self._fanta_volumes_error_info
                )
            return True

        return True

    def _handle_error_ui(
        self,
        error_type: ErrorTypes,
        error_info: ErrorInfo | None = None,
        msg: str = "",
    ) -> None:
        def _on_error_popup_closed(popup_msg: str) -> None:
            self._tree_view_screen.main_files_not_loaded_msg = popup_msg
            self._tree_view_screen.main_files_not_loaded = True

        self._user_error_handler.handle_error(
            error_type,
            error_info,
            _on_error_popup_closed,
            msg,
        )
