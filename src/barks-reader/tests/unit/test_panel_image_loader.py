# ruff: noqa: SLF001, ARG005

from __future__ import annotations

import threading
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import panel_image_loader as loader_module
from barks_reader.core.panel_image_loader import PanelImageLoader
from barks_reader.core.services import schedule_once

# noinspection PyUnresolvedReferences
from comic_utils.get_panel_bytes import get_decrypted_bytes  # ty:ignore[unresolved-import]
from PIL import Image


@pytest.fixture
def mock_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def loader() -> PanelImageLoader:
    return PanelImageLoader(barks_panels_are_encrypted=False)


class TestPanelImageLoader:
    def test_init(self) -> None:
        loader = PanelImageLoader(barks_panels_are_encrypted=True)
        assert loader._barks_panels_are_encrypted is True
        assert loader._cancel is False
        assert loader._current_thread is None

    def test_cancel(self, loader: PanelImageLoader) -> None:
        loader.cancel()
        assert loader._cancel is True

    def test_load_pil_success_path(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)
        mock_path.read_bytes.return_value = b"fake_image_data"

        mock_image = MagicMock(spec=Image.Image)
        mock_converted_image = MagicMock(spec=Image.Image)
        mock_image.convert.return_value = mock_converted_image

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(
                loader_module.Image, Image.open.__name__, return_value=mock_image
            ) as mock_img_open,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            # Execute worker synchronously
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_path.read_bytes.assert_called_once()
            mock_img_open.assert_called_once()
            mock_image.load.assert_called_once()
            mock_image.convert.assert_called_with("RGBA")

            mock_callback.assert_called_once_with(mock_converted_image, None)

    def test_load_pil_encrypted(self, mock_callback: MagicMock) -> None:
        loader = PanelImageLoader(barks_panels_are_encrypted=True)
        mock_path = MagicMock(spec=Path)
        mock_path.read_bytes.return_value = b"encrypted_data"

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(
                loader_module, get_decrypted_bytes.__name__, return_value=b"decrypted"
            ) as mock_decrypt,
            patch.object(loader_module.Image, Image.open.__name__) as mock_img_open,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_decrypt.assert_called_once_with(b"encrypted_data")
            mock_img_open.assert_called_once()

    def test_load_pil_zip_path(self, loader: PanelImageLoader, mock_callback: MagicMock) -> None:
        mock_path = MagicMock(spec=zipfile.Path)
        mock_path.read_bytes.return_value = b"zip_data"

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module.Image, Image.open.__name__) as mock_img_open,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_img_open.assert_called_once()

    def test_load_pil_error(self, loader: PanelImageLoader, mock_callback: MagicMock) -> None:
        mock_path = MagicMock(spec=Path)
        error = OSError("Read failed")
        mock_path.read_bytes.side_effect = error

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_callback.assert_called_once_with(None, error)

    # noinspection PyShadowingNames
    def test_load_pil_unsupported_type(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            # noinspection PyTypeChecker
            loader.load_pil("not a path", mock_callback)  # ty:ignore[invalid-argument-type]

            args, _ = mock_callback.call_args
            assert args[0] is None
            assert isinstance(args[1], TypeError)

    def test_worker_cancel_early(self, loader: PanelImageLoader, mock_callback: MagicMock) -> None:
        """Test cancellation after read_bytes but before image processing."""
        mock_path = MagicMock(spec=Path)
        mock_path.read_bytes.return_value = b"data"

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module.Image, Image.open.__name__) as mock_img_open,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            # Side effect to cancel during read_bytes
            def side_effect_cancel() -> bytes:
                loader.cancel()
                return b"data"

            mock_path.read_bytes.side_effect = side_effect_cancel

            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )

            loader.load_pil(mock_path, mock_callback)

            # Should return early
            mock_img_open.assert_not_called()
            mock_schedule.assert_not_called()

    def test_worker_cancel_late(self, loader: PanelImageLoader, mock_callback: MagicMock) -> None:
        """Test cancellation after image processing but before callback."""
        mock_path = MagicMock(spec=Path)
        mock_path.read_bytes.return_value = b"data"

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module.Image, Image.open.__name__) as mock_img_open,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_image = MagicMock()
            mock_img_open.return_value = mock_image

            # Set cancel during image conversion
            # noinspection PyUnusedLocal
            def side_effect_convert(mode: str) -> MagicMock:  # noqa: ARG001
                loader.cancel()
                return MagicMock()

            mock_image.convert.side_effect = side_effect_convert

            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )

            loader.load_pil(mock_path, mock_callback)

            mock_img_open.assert_called()
            mock_schedule.assert_not_called()

    def test_start_worker_kills_previous_thread(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)

        with patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance

            # Start first thread
            loader.load_pil(mock_path, mock_callback)
            assert loader._current_thread == mock_thread_instance

            # Start second thread
            loader.load_pil(mock_path, mock_callback)

            # Verify join called on first thread
            mock_thread_instance.join.assert_called_once()
            assert loader._cancel is False  # Reset to false
