from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.panel_image_loader import PanelImageLoader


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths.barks_panels_are_encrypted = False
    return settings


@pytest.fixture
def loader(mock_settings: MagicMock) -> PanelImageLoader:
    return PanelImageLoader(mock_settings.file_paths.barks_panels_are_encrypted)


class TestPanelImageLoader:
    def test_init(self, loader: PanelImageLoader) -> None:
        assert loader is not None

    @patch("barks_reader.panel_image_loader.Thread")
    @patch("barks_reader.panel_image_loader.Clock")
    @patch("barks_reader.panel_image_loader.Texture")
    @patch("barks_reader.panel_image_loader.Image")
    @patch("pathlib.Path.read_bytes")
    def test_load_texture_file_system(
        self,
        mock_read_bytes: MagicMock,
        mock_pil_image: MagicMock,
        mock_texture_cls: MagicMock,
        mock_clock: MagicMock,
        mock_thread_cls: MagicMock,
        loader: PanelImageLoader,
    ) -> None:
        # Setup Thread to run immediately
        def start_thread() -> None:
            args = mock_thread_cls.call_args[1]["args"]
            target = mock_thread_cls.call_args[1]["target"]
            target(*args)

        mock_thread_cls.return_value.start.side_effect = start_thread

        # Setup Clock to run callback immediately
        mock_clock.schedule_once.side_effect = lambda func, _dt: func(0)

        path = Path("image.png")
        mock_read_bytes.return_value = b"fake_image_data"

        mock_pil_instance = MagicMock()
        mock_pil_image.open.return_value = mock_pil_instance
        mock_pil_instance.tobytes.return_value = b"pixels"
        mock_pil_instance.size = (100, 100)

        mock_texture_instance = MagicMock()
        mock_texture_cls.create.return_value = mock_texture_instance

        mock_callback = MagicMock()

        loader.load_texture(path, mock_callback)

        mock_read_bytes.assert_called_once()
        mock_pil_image.open.assert_called_once()
        mock_texture_cls.create.assert_called_once()
        mock_callback.assert_called_once_with(mock_texture_instance, None)

    @patch("barks_reader.panel_image_loader.Thread")
    @patch("barks_reader.panel_image_loader.Clock")
    @patch("barks_reader.panel_image_loader.Texture")
    @patch("barks_reader.panel_image_loader.Image")
    @patch("pathlib.Path.read_bytes")
    @patch("barks_reader.panel_image_loader.get_decrypted_bytes")
    def test_load_texture_encrypted(
        self,
        mock_get_decrypted: MagicMock,
        mock_read_bytes: MagicMock,
        mock_pil_image: MagicMock,
        mock_texture_cls: MagicMock,
        mock_clock: MagicMock,
        mock_thread_cls: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.file_paths.barks_panels_are_encrypted = True
        loader = PanelImageLoader(mock_settings.file_paths.barks_panels_are_encrypted)

        # Setup Thread
        def start_thread() -> None:
            args = mock_thread_cls.call_args[1]["args"]
            target = mock_thread_cls.call_args[1]["target"]
            target(*args)

        mock_thread_cls.return_value.start.side_effect = start_thread

        # Setup Clock
        mock_clock.schedule_once.side_effect = lambda func, _dt: func(0)

        path = Path("image.png")
        mock_read_bytes.return_value = b"encrypted_data"
        mock_get_decrypted.return_value = b"decrypted_data"

        mock_pil_instance = MagicMock()
        mock_pil_image.open.return_value = mock_pil_instance

        mock_texture_instance = MagicMock()
        mock_texture_cls.create.return_value = mock_texture_instance

        mock_callback = MagicMock()

        loader.load_texture(path, mock_callback)

        mock_read_bytes.assert_called_once()
        mock_get_decrypted.assert_called_once_with(b"encrypted_data")
        mock_pil_image.open.assert_called_once()
        mock_callback.assert_called_once_with(mock_texture_instance, None)

    @patch("barks_reader.panel_image_loader.Thread")
    @patch("barks_reader.panel_image_loader.Clock")
    @patch("pathlib.Path.read_bytes")
    def test_load_texture_error(
        self,
        mock_read_bytes: MagicMock,
        mock_clock: MagicMock,
        mock_thread_cls: MagicMock,
        loader: PanelImageLoader,
    ) -> None:
        # Setup Thread
        def start_thread() -> None:
            args = mock_thread_cls.call_args[1]["args"]
            target = mock_thread_cls.call_args[1]["target"]
            target(*args)

        mock_thread_cls.return_value.start.side_effect = start_thread

        # Setup Clock
        mock_clock.schedule_once.side_effect = lambda func, _dt: func(0)

        path = Path("missing.png")
        error = Exception("Read Error")
        mock_read_bytes.side_effect = error
        mock_callback = MagicMock()

        loader.load_texture(path, mock_callback)

        mock_callback.assert_called_once_with(None, error)
