from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from loguru import logger

from barks_reader.background_views import ViewStates
from barks_reader.fantagraphics_volumes import (
    TooManyArchiveFilesError,
    WrongFantagraphicsVolumeError,
)
from barks_reader.reader_settings import FantaVolumesState
from barks_reader.reader_tree_view_utils import get_tree_view_node_id_text
from barks_reader.reader_ui_classes import (
    ButtonTreeViewNode,
    TitleTreeViewNode,
)
from barks_reader.user_error_handler import ErrorTypes

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.uix.treeview import TreeViewNode
    from kivy.uix.widget import Widget

    from barks_reader.comic_reader_manager import ComicReaderManager
    from barks_reader.json_settings_manager import SettingsManager
    from barks_reader.reader_settings import ReaderSettings
    from barks_reader.reader_tree_builder import ReaderTreeBuilder
    from barks_reader.reader_ui_classes import LoadingDataPopup
    from barks_reader.tree_view_manager import TreeViewManager
    from barks_reader.tree_view_screen import TreeViewScreen
    from barks_reader.user_error_handler import UserErrorHandler
    from barks_reader.view_state_manager import ViewStateManager

BAD_FANTA_VOLUMES_STATE = [FantaVolumesState.VOLUMES_MISSING, FantaVolumesState.VOLUMES_NOT_SET]
READY_FANTA_VOLUMES_STATE = [FantaVolumesState.VOLUMES_EXIST, FantaVolumesState.VOLUMES_NOT_NEEDED]


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

        self._fanta_volumes_state: FantaVolumesState = FantaVolumesState.VOLUMES_NOT_SET
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
        self._fanta_volumes_state = self._get_fanta_volumes_state()
        logger.debug(f"_fanta_volumes_state = {self._fanta_volumes_state}.")

        self._view_state_manager.update_background_views(ViewStates.INITIAL)

        if (self._fanta_volumes_state in READY_FANTA_VOLUMES_STATE) and (
            not self._init_comic_book_data()
        ):
            return

        if self._reader_settings.goto_saved_node_on_start:
            saved_node_path = self._json_settings_manager.get_last_selected_node_path()
            if saved_node_path:
                self._goto_saved_node(saved_node_path)

    def _goto_saved_node(self, saved_node_path: list[str]) -> None:
        logger.debug(f'Looking for saved node "{saved_node_path}"...')
        saved_node = self._tree_view_screen.find_node_by_path(saved_node_path)
        if saved_node:
            self._setup_and_select_saved_node(saved_node)

    def _setup_and_select_saved_node(self, saved_node: TreeViewNode) -> None:
        logger.debug(
            f'Selecting and setting up start node "{get_tree_view_node_id_text(saved_node)}".',
        )

        self._tree_view_screen.select_node(saved_node)

        if isinstance(saved_node, ButtonTreeViewNode):
            saved_node.trigger_action()
        elif isinstance(saved_node, TitleTreeViewNode):
            fanta_info = saved_node.ids.num_label.parent.fanta_info
            self._set_next_title_func(fanta_info, None)
            self._tree_view_manager.scroll_to_node(saved_node)

    def is_fanta_volumes_state_ok(self) -> tuple[bool, str]:
        if self._fanta_volumes_state not in BAD_FANTA_VOLUMES_STATE:
            return True, ""

        reason = (
            "Fantagraphics Directory Not Set"
            if self._fanta_volumes_state == FantaVolumesState.VOLUMES_NOT_SET
            else "Fantagraphics Directory Not Found"
        )
        error_type = (
            ErrorTypes.FantagraphicsVolumeRootNotSet
            if self._fanta_volumes_state == FantaVolumesState.VOLUMES_NOT_SET
            else ErrorTypes.FantagraphicsVolumeRootNotFound
        )

        def _on_error_popup_closed(fanta_volumes_missing_msg: str) -> None:
            self._tree_view_screen.main_files_not_loaded_msg = fanta_volumes_missing_msg
            self._tree_view_screen.main_files_not_loaded = True

        self._user_error_handler.handle_error(
            error_type,
            None,
            _on_error_popup_closed,
            f"Cannot Load Comic: {reason}",
        )

        return False, reason

    def _get_fanta_volumes_state(self) -> FantaVolumesState:
        volumes_state = self._reader_settings.get_fantagraphics_volumes_state()
        if volumes_state in [FantaVolumesState.VOLUMES_EXIST, FantaVolumesState.VOLUMES_NOT_NEEDED]:
            return volumes_state

        error_type = (
            ErrorTypes.FantagraphicsVolumeRootNotSet
            if volumes_state == FantaVolumesState.VOLUMES_NOT_SET
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

        return volumes_state

    def _init_comic_book_data(self) -> bool:
        try:
            self._comic_reader_manager.init_comic_book_data()
        except (WrongFantagraphicsVolumeError, TooManyArchiveFilesError) as e:

            def _on_error_popup_closed(wrong_fanta_volumes_msg: str) -> None:
                self._tree_view_screen.main_files_not_loaded_msg = wrong_fanta_volumes_msg
                self._tree_view_screen.main_files_not_loaded = True

            error_type = (
                ErrorTypes.WrongFantagraphicsVolume
                if type(e) is WrongFantagraphicsVolumeError
                else ErrorTypes.TooManyArchiveFiles
            )
            self._user_error_handler.handle_error(error_type, e, _on_error_popup_closed)

            return False

        except Exception:
            raise
        else:
            return True
