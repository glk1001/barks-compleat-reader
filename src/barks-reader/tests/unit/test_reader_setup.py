from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.core import reader_setup
from barks_reader.core.reader_setup import (
    bootstrap_reader_environment,
    prepare_comic_for_reading,
)
from comic_utils.get_panel_bytes import get_decrypted_bytes


class TestBootstrapReaderEnvironment:
    def test_wires_config_and_inset_info(self) -> None:
        reader_settings = MagicMock()
        reader_settings.file_paths.get_comic_inset_files_dir.return_value = "/inset/dir"
        reader_settings.file_paths.get_inset_file_ext.return_value = ".png"
        reader_settings.reader_files_dir = "/reader/files"

        comics_database = MagicMock()
        parser = MagicMock()
        config_info = MagicMock()
        config_info.app_config_path = "/cfg/app.ini"
        config_info.app_data_dir = "/data"

        bootstrap_reader_environment(reader_settings, comics_database, parser, config_info)

        reader_settings.set_config.assert_called_once_with(parser, "/cfg/app.ini", "/data")
        reader_settings.set_barks_panels_dir.assert_called_once_with()
        comics_database.set_inset_info.assert_called_once_with("/inset/dir", ".png")
        reader_settings.sys_file_paths.set_barks_reader_files_dir.assert_called_once_with(
            "/reader/files"
        )

    def test_set_config_called_before_inset_dir_lookup(self) -> None:
        # The config must be wired before file_paths is read, otherwise the
        # inset lookup runs against an unconfigured ReaderSettings.
        reader_settings = MagicMock()
        comics_database = MagicMock()

        call_order: list[str] = []
        reader_settings.set_config.side_effect = lambda *_a, **_k: call_order.append("set_config")
        reader_settings.file_paths.get_comic_inset_files_dir.side_effect = lambda: (
            call_order.append("get_inset_dir") or "/x"
        )

        bootstrap_reader_environment(reader_settings, comics_database, MagicMock(), MagicMock())

        assert call_order.index("set_config") < call_order.index("get_inset_dir")


class TestPrepareComicForReading:
    def test_returns_layout_and_image_builder(self) -> None:
        comic = MagicMock()
        reader_settings = MagicMock()
        reader_settings.file_paths.barks_panels_are_encrypted = False
        reader_settings.sys_file_paths.get_empty_page_file.return_value = "/empty.png"

        layout_builder = MagicMock()
        layout = MagicMock()
        layout_builder.build.return_value = layout
        required_dim = MagicMock()
        layout_builder.get_required_dimensions.return_value = required_dim

        with patch.object(reader_setup, "ComicBookImageBuilder") as builder_cls:
            instance = builder_cls.return_value

            result_layout, result_builder = prepare_comic_for_reading(
                comic, reader_settings, layout_builder
            )

            layout_builder.build.assert_called_once_with(comic)
            builder_cls.assert_called_once_with(comic, "/empty.png", get_inset_decrypted_bytes=None)
            instance.set_required_dim.assert_called_once_with(required_dim)

        assert result_layout is layout
        assert result_builder is instance

    def test_passes_decrypt_func_when_panels_are_encrypted(self) -> None:
        comic = MagicMock()
        reader_settings = MagicMock()
        reader_settings.file_paths.barks_panels_are_encrypted = True
        reader_settings.sys_file_paths.get_empty_page_file.return_value = "/empty.png"

        layout_builder = MagicMock()

        with patch.object(reader_setup, "ComicBookImageBuilder") as builder_cls:
            prepare_comic_for_reading(comic, reader_settings, layout_builder)

            _, kwargs = builder_cls.call_args
            assert kwargs["get_inset_decrypted_bytes"] is get_decrypted_bytes

    def test_required_dim_built_from_same_comic(self) -> None:
        comic = MagicMock()
        reader_settings = MagicMock()
        reader_settings.file_paths.barks_panels_are_encrypted = False

        layout_builder = MagicMock()

        with patch.object(reader_setup, "ComicBookImageBuilder"):
            prepare_comic_for_reading(comic, reader_settings, layout_builder)

        layout_builder.get_required_dimensions.assert_called_once_with(comic)
