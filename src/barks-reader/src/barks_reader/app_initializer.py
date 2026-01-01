from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from comic_utils.timing import Timing
from kivy.clock import Clock
from loguru import logger

from barks_reader.background_views import ViewStates
from barks_reader.fantagraphics_volumes import (
    TooManyArchiveFilesError,
    WrongFantagraphicsVolumeError,
)
from barks_reader.reader_settings import UNSET_FANTA_DIR_MARKER
from barks_reader.reader_ui_classes import BaseTreeViewNode
from barks_reader.user_error_handler import ErrorInfo, ErrorTypes

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.uix.widget import Widget

    from barks_reader.comic_reader_manager import ComicReaderManager
    from barks_reader.json_settings_manager import SettingsManager
    from barks_reader.reader_settings import ReaderSettings
    from barks_reader.reader_tree_builder import ReaderTreeBuilder
    from barks_reader.tree_view_manager import TreeViewManager
    from barks_reader.tree_view_screen import TreeViewScreen
    from barks_reader.user_error_handler import UserErrorHandler
    from barks_reader.view_state_manager import ViewStateManager


class _FantaVolumesState(Enum):
    VOLUMES_EXIST = auto()
    VOLUMES_MISSING = auto()
    VOLUMES_NOT_SET = auto()
    VOLUMES_WRONG_ORDER = auto()
    VOLUMES_TOO_MANY = auto()
    VOLUMES_NOT_NEEDED = auto()


_READY_FANTA_VOLUMES_STATE = {
    _FantaVolumesState.VOLUMES_EXIST,
    _FantaVolumesState.VOLUMES_NOT_NEEDED,
}
_BAD_FANTA_VOLUMES_STATE = set(_FantaVolumesState) - _READY_FANTA_VOLUMES_STATE


class AppInitializer:
    """Handles the application's startup sequence."""

    def __init__(
        self,
        reader_settings: ReaderSettings,
        user_error_handler: UserErrorHandler,
        comic_reader_manager: ComicReaderManager,
        json_settings_manager: SettingsManager,
        view_state_manager: ViewStateManager,
        tree_view_manager: TreeViewManager,
        tree_view_screen: TreeViewScreen,
        set_next_title_func: Callable[[FantaComicBookInfo, Tags | TagGroups | None], None],
    ) -> None:
        self._reader_settings = reader_settings
        self._user_error_handler = user_error_handler
        self._comic_reader_manager = comic_reader_manager
        self._json_settings_manager = json_settings_manager
        self._tree_view_screen = tree_view_screen
        self._tree_view_manager = tree_view_manager
        self._view_state_manager = view_state_manager
        self._set_next_title_func = set_next_title_func

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
            self._set_post_build_fanta_volumes_state()
            logger.debug(f"_fanta_volumes_state = {self._fanta_volumes_state}.")

            self._view_state_manager.update_background_views(ViewStates.INITIAL)

            if (self._fanta_volumes_state in _READY_FANTA_VOLUMES_STATE) and (
                not self._init_comic_book_data()
            ):
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

        def _on_error_popup_closed(fanta_volumes_missing_msg: str) -> None:
            self._tree_view_screen.main_files_not_loaded_msg = fanta_volumes_missing_msg
            self._tree_view_screen.main_files_not_loaded = True

        self._user_error_handler.handle_error(
            error_type,
            self._fanta_volumes_error_info,
            _on_error_popup_closed,
            f"Cannot Load Comic: {reason}",
        )

        return False, reason

    def get_bad_fanta_volumes_reason(self) -> tuple[str, ErrorTypes]:
        if self._fanta_volumes_state == _FantaVolumesState.VOLUMES_NOT_SET:
            return "Fantagraphics Directory Not Set", ErrorTypes.FantagraphicsVolumeRootNotSet
        if self._fanta_volumes_state == _FantaVolumesState.VOLUMES_MISSING:
            return "Fantagraphics Directory Not Found", ErrorTypes.FantagraphicsVolumeRootNotFound
        if self._fanta_volumes_state == _FantaVolumesState.VOLUMES_WRONG_ORDER:
            return "Wrong Content in Fantagraphics Directory", ErrorTypes.WrongFantagraphicsVolume
        if self._fanta_volumes_state == _FantaVolumesState.VOLUMES_TOO_MANY:
            return "Wrong Content in Fantagraphics Directory", ErrorTypes.WrongFantagraphicsVolume

        msg = f'Unexpected fanta volumes state: "{self._fanta_volumes_state}".'
        raise RuntimeError(msg)

    def _set_post_build_fanta_volumes_state(self) -> None:
        self._fanta_volumes_state = self._get_post_build_fanta_volumes_state()
        if self._fanta_volumes_state in _READY_FANTA_VOLUMES_STATE:
            return

        error_type = (
            ErrorTypes.FantagraphicsVolumeRootNotSet
            if self._fanta_volumes_state == _FantaVolumesState.VOLUMES_NOT_SET
            else ErrorTypes.FantagraphicsVolumeRootNotFound
        )

        def _on_error_popup_closed(fanta_volumes_missing_msg: str) -> None:
            self._tree_view_screen.main_files_not_loaded_msg = fanta_volumes_missing_msg
            self._tree_view_screen.main_files_not_loaded = True

        self._user_error_handler.handle_error(
            error_type,
            None,
            _on_error_popup_closed,
        )

    def _get_post_build_fanta_volumes_state(self) -> _FantaVolumesState:
        if self._reader_settings.use_prebuilt_archives:
            return _FantaVolumesState.VOLUMES_NOT_NEEDED
        if str(self._reader_settings.fantagraphics_volumes_dir) == UNSET_FANTA_DIR_MARKER:
            return _FantaVolumesState.VOLUMES_NOT_SET
        if not self._reader_settings.fantagraphics_volumes_dir.is_dir():
            return _FantaVolumesState.VOLUMES_MISSING
        return _FantaVolumesState.VOLUMES_EXIST

    def _init_comic_book_data(self) -> bool:
        try:
            self._comic_reader_manager.init_comic_book_data()
        except (WrongFantagraphicsVolumeError, TooManyArchiveFilesError) as e:

            def _on_error_popup_closed(wrong_fanta_volumes_msg: str) -> None:
                self._tree_view_screen.main_files_not_loaded_msg = wrong_fanta_volumes_msg
                self._tree_view_screen.main_files_not_loaded = True

            if type(e) is WrongFantagraphicsVolumeError:
                error_type = ErrorTypes.WrongFantagraphicsVolume
                self._fanta_volumes_error_info = ErrorInfo(
                    file=str(e.file), file_volume=e.file_volume, expected_volume=e.expected_volume
                )
                self._fanta_volumes_state = _FantaVolumesState.VOLUMES_WRONG_ORDER
            else:
                assert type(e) is TooManyArchiveFilesError  # noqa: PT017
                error_type = ErrorTypes.TooManyArchiveFiles
                self._fanta_volumes_error_info = ErrorInfo(
                    num_volumes=e.num_volumes, num_archive_files=e.num_archive_files
                )
                self._fanta_volumes_state = _FantaVolumesState.VOLUMES_TOO_MANY

            self._user_error_handler.handle_error(
                error_type, self._fanta_volumes_error_info, _on_error_popup_closed
            )

            return False

        except Exception:
            raise
        else:
            return True
