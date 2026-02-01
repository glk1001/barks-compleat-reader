# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from barks_reader.core.fantagraphics_volumes import TooManyArchiveFilesError
from barks_reader.core.reader_settings import UNSET_FANTA_DIR_MARKER
from barks_reader.ui import app_initializer as app_initializer_module

# noinspection PyProtectedMember
from barks_reader.ui.app_initializer import AppInitializer, _FantaVolumesState
from barks_reader.ui.reader_ui_classes import BaseTreeViewNode
from barks_reader.ui.user_error_handler import ErrorTypes
from barks_reader.ui.view_states import ViewStates


@pytest.fixture
def mock_dependencies() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "user_error_handler": MagicMock(),
        "comic_reader_manager": MagicMock(),
        "json_settings_manager": MagicMock(),
        "view_state_manager": MagicMock(),
        "tree_view_manager": MagicMock(),
        "tree_view_screen": MagicMock(),
        "set_next_title_func": MagicMock(),
    }


@pytest.fixture
def app_initializer(mock_dependencies: dict[str, MagicMock]) -> AppInitializer:
    return AppInitializer(**mock_dependencies)


class TestAppInitializer:
    def test_start(self, app_initializer: AppInitializer) -> None:
        mock_tree_builder = MagicMock()
        mock_callback = MagicMock()

        with patch.object(app_initializer_module, "Clock") as mock_clock:
            app_initializer.start(mock_tree_builder, mock_callback)

            mock_clock.schedule_once.assert_called_once()
            # Verify the lambda calls build_main_screen_tree
            args, _ = mock_clock.schedule_once.call_args
            lambda_func = args[0]
            lambda_func(0)
            mock_tree_builder.build_main_screen_tree.assert_called_once()

    def test_on_tree_build_finished(self, app_initializer: AppInitializer) -> None:
        mock_callback = MagicMock()
        # Manually set the callback as start() would
        # noinspection PyProtectedMember
        app_initializer._on_tree_build_finished = mock_callback

        with patch.object(
            app_initializer, AppInitializer._post_build_setup.__name__
        ) as mock_post_setup:
            app_initializer.on_tree_build_finished(MagicMock())

            mock_callback.assert_called_once()
            mock_post_setup.assert_called_once()

    def test_post_build_setup_prebuilt(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_dependencies["reader_settings"].use_prebuilt_archives = True
        mock_dependencies["reader_settings"].goto_saved_node_on_start = False

        # Mock _init_comic_book_data to return True
        with patch.object(
            app_initializer, AppInitializer._init_comic_book_data.__name__, return_value=True
        ) as mock_init_data:
            # noinspection PyProtectedMember
            app_initializer._post_build_setup()

            # Check state
            # noinspection PyProtectedMember
            assert app_initializer._fanta_volumes_state == _FantaVolumesState.VOLUMES_NOT_NEEDED

            # Check view state set to INITIAL
            mock_dependencies["view_state_manager"].set_view_state.assert_called_with(
                ViewStates.INITIAL
            )

            # Check init called
            mock_init_data.assert_called_once()

    def test_post_build_setup_unset_dir(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_dependencies["reader_settings"].use_prebuilt_archives = False
        mock_dependencies["reader_settings"].goto_saved_node_on_start = False
        mock_dependencies["reader_settings"].fantagraphics_volumes_dir = UNSET_FANTA_DIR_MARKER

        with patch.object(
            app_initializer, AppInitializer._handle_error_ui.__name__
        ) as mock_handle_error:
            # noinspection PyProtectedMember
            app_initializer._post_build_setup()

            # noinspection PyProtectedMember
            assert app_initializer._fanta_volumes_state == _FantaVolumesState.VOLUMES_NOT_SET

            mock_handle_error.assert_called_with(ErrorTypes.FantagraphicsVolumeRootNotSet)

    def test_post_build_setup_missing_dir(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_dependencies["reader_settings"].use_prebuilt_archives = False
        mock_dependencies["reader_settings"].goto_saved_node_on_start = False
        mock_path = MagicMock()
        mock_path.__str__.return_value = "/some/path"
        mock_path.is_dir.return_value = False
        mock_dependencies["reader_settings"].fantagraphics_volumes_dir = mock_path

        with patch.object(
            app_initializer, AppInitializer._handle_error_ui.__name__
        ) as mock_handle_error:
            # noinspection PyProtectedMember
            app_initializer._post_build_setup()

            # noinspection PyProtectedMember
            assert app_initializer._fanta_volumes_state == _FantaVolumesState.ALL_VOLUMES_MISSING

            mock_handle_error.assert_called_with(ErrorTypes.FantagraphicsVolumeRootNotFound)

    def test_post_build_setup_goto_saved_node(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        mock_dependencies["reader_settings"].use_prebuilt_archives = True
        mock_dependencies["reader_settings"].goto_saved_node_on_start = True

        mock_dependencies["json_settings_manager"].get_last_selected_node_path.return_value = (
            ["root", "node"],
            {"state": "data"},
        )

        mock_node = MagicMock(spec=BaseTreeViewNode)
        mock_dependencies["tree_view_screen"].find_node_by_path.return_value = mock_node

        with patch.object(
            app_initializer, AppInitializer._init_comic_book_data.__name__, return_value=True
        ):
            # noinspection PyProtectedMember
            app_initializer._post_build_setup()

            mock_dependencies["tree_view_screen"].find_node_by_path.assert_called_with(
                ["root", "node"]
            )
            assert mock_node.saved_state == {"state": "data"}
            mock_dependencies["tree_view_manager"].setup_and_select_node.assert_called_with(
                mock_node
            )

    def test_init_comic_book_data_success(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # noinspection PyProtectedMember
        assert app_initializer._init_comic_book_data() is True
        mock_dependencies["comic_reader_manager"].init_comic_book_data.assert_called_once()

    def test_init_comic_book_data_too_many_files(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        error = TooManyArchiveFilesError(10, 12, Path("/root"))
        mock_dependencies["comic_reader_manager"].init_comic_book_data.side_effect = error

        with patch.object(
            app_initializer, AppInitializer._handle_error_ui.__name__
        ) as mock_handle_error:
            # noinspection PyProtectedMember
            assert app_initializer._init_comic_book_data() is False

            # noinspection PyProtectedMember
            assert app_initializer._fanta_volumes_state == _FantaVolumesState.VOLUMES_TOO_MANY

            mock_handle_error.assert_called_with(ErrorTypes.TooManyVolumeArchiveFiles, ANY)

    def test_is_fanta_volumes_state_ok(self, app_initializer: AppInitializer) -> None:
        # Case OK
        # noinspection PyProtectedMember
        app_initializer._fanta_volumes_state = _FantaVolumesState.VOLUMES_EXIST
        assert app_initializer.is_fanta_volumes_state_ok() == (True, "")

        # Case Bad
        # noinspection PyProtectedMember
        app_initializer._fanta_volumes_state = _FantaVolumesState.ALL_VOLUMES_MISSING

        with patch.object(
            app_initializer, AppInitializer._handle_error_ui.__name__
        ) as mock_handle_error:
            ok, reason = app_initializer.is_fanta_volumes_state_ok()
            assert ok is False
            assert reason == "Fantagraphics Directory Not Found"
            mock_handle_error.assert_called()

    def test_handle_error_ui(
        self, app_initializer: AppInitializer, mock_dependencies: dict[str, MagicMock]
    ) -> None:
        # Test that the callback passed to user_error_handler works as expected

        # noinspection PyProtectedMember
        app_initializer._handle_error_ui(ErrorTypes.FantagraphicsVolumeRootNotFound)

        mock_dependencies["user_error_handler"].handle_error.assert_called_once()
        args, _ = mock_dependencies["user_error_handler"].handle_error.call_args
        callback = args[2]

        # Execute callback
        callback("Popup Message")

        assert mock_dependencies["tree_view_screen"].main_files_not_loaded_msg == "Popup Message"
        assert mock_dependencies["tree_view_screen"].main_files_not_loaded is True
