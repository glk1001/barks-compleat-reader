from __future__ import annotations

from typing import TYPE_CHECKING, Any

from comic_utils.timing import Timing
from kivy.clock import Clock
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.fanta_volumes_state import (
    BAD_STATES,
    NO_LIBRARY_STATES,
    STATE_ERRORS,
    FantaVolumesState,
    LibraryNotice,
    check_library_error,
    no_library_error_type,
    post_build_state,
)
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    MissingArchiveFilesError,
    TooManyArchiveFilesError,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_tree_view_utils import ancestor_paths

from .tree_view_nodes import BaseTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget

    from barks_reader.core.comic_reader_manager import ComicReaderManager
    from barks_reader.core.json_settings_manager import SettingsManager
    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

    from .reader_tree_builder import ReaderTreeBuilder
    from .tree_view_manager import TreeViewManager
    from .tree_view_screen import TreeViewScreen
    from .user_error_handler import UserErrorHandler
    from .view_renderer import ViewRenderer


class AppInitializer:
    """Handles the application's startup sequence."""

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

        self._fanta_volumes_state = FantaVolumesState.VOLUMES_NOT_SET
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

        self._post_build_setup()

        # After the post-build setup, whose no-library notice must come first: a popup
        # the callback opens (the data pack offer) binds the window's keys, and Kivy
        # hands a key to the earliest binding, so a notice opened after it would sit on
        # top while the hidden offer answered the keys.
        assert self._on_tree_build_finished is not None
        self._on_tree_build_finished()

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
            no_library = self._fanta_volumes_state in NO_LIBRARY_STATES
            if no_library:
                self._show_no_library_notice(no_library_error_type(self._fanta_volumes_state))

            if not self._init_comic_book_data(library_notice_shown=no_library):
                return

            if self._reader_settings.goto_saved_node_on_start:
                saved_node_path, saved_node_state = (
                    self._json_settings_manager.get_last_selected_node_path()
                )
                if saved_node_path:
                    self._goto_saved_node(saved_node_path, saved_node_state)
        finally:
            logger.info(
                log_markers.POST_TREE_SETUP.format(elapsed=timing.get_elapsed_time_with_unit())
            )

    def _goto_saved_node(
        self, saved_node_path: list[str], saved_node_state: dict[str, Any]
    ) -> None:
        logger.debug(f'Looking for saved node "{saved_node_path}"...')
        saved_node = self._tree_view_screen.find_node_by_path(saved_node_path)
        if saved_node:
            assert isinstance(saved_node, BaseTreeViewNode)
            saved_node.saved_state = saved_node_state
            self._tree_view_manager.setup_and_select_node(saved_node)
            return

        # The saved node is gone (a title moved to another tag, say). Land on its nearest
        # surviving ancestor, so the keys start from a selection and not from nothing. The
        # path runs leaf to root; the state saved was the leaf's and is not applied.
        for ancestor_path in ancestor_paths(saved_node_path):
            ancestor = self._tree_view_screen.find_node_by_path(ancestor_path)
            if ancestor:
                assert isinstance(ancestor, BaseTreeViewNode)
                logger.info(log_markers.SAVED_NODE_ANCESTOR_SELECTED.format(name=ancestor_path[0]))
                self._tree_view_manager.setup_and_select_node(ancestor)
                return

    def is_fanta_volumes_state_ok(self) -> tuple[bool, str]:
        if self._fanta_volumes_state not in BAD_STATES:
            return True, ""

        reason, error_type = self.get_bad_fanta_volumes_reason()

        self._handle_error_ui(
            error_type,
            self._fanta_volumes_error_info,
            msg=f"Cannot Load Comic: {reason}",
        )

        return False, reason

    def get_bad_fanta_volumes_reason(self) -> tuple[str, ErrorTypes]:
        if self._fanta_volumes_state in STATE_ERRORS:
            return STATE_ERRORS[self._fanta_volumes_state]

        msg = f'Unexpected fanta volumes state: "{self._fanta_volumes_state}".'
        raise RuntimeError(msg)

    def _show_no_library_notice(self, error_type: ErrorTypes) -> None:
        """Show a single notice that the Fantagraphics library isn't available.

        The app stays fully browsable, so this deliberately does not set the persistent
        'files not loaded' tree overlay, and fires once. ``error_type`` selects the
        wording: the unset setting, or a directory that holds no readable volumes.
        """
        # A no-op close callback: the notice is informational and must not set the
        # persistent overlay (unlike `_handle_error_ui`).
        self._user_error_handler.handle_error(error_type, None, lambda _msg: None)

    def _get_post_build_fanta_volumes_state(self) -> FantaVolumesState:
        return post_build_state(
            use_prebuilt_archives=self._reader_settings.use_prebuilt_archives,
            volumes_dir=self._reader_settings.fantagraphics_volumes_dir,
        )

    def _init_comic_book_data(self, *, library_notice_shown: bool = False) -> bool:
        try:
            self._comic_reader_manager.init_comic_book_data()
        except (
            TooManyArchiveFilesError,
            DuplicateArchiveFilesError,
            MissingArchiveFilesError,
        ) as e:
            check = check_library_error(e, library_notice_shown=library_notice_shown)
            self._fanta_volumes_state = check.state
            self._fanta_volumes_error_info = check.error_info
            if check.notice is not LibraryNotice.NONE:
                assert check.error_type is not None
                if check.notice is LibraryNotice.NO_LIBRARY:
                    self._show_no_library_notice(check.error_type)
                else:
                    self._handle_error_ui(check.error_type, check.error_info)
            return check.readable

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
