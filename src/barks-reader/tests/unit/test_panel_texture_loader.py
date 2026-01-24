# ruff: noqa: SLF001
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import panel_texture_loader as loader_module
from barks_reader.ui.panel_texture_loader import PanelTextureLoader

# noinspection PyProtectedMember
from kivy.core.image import Texture
from PIL import Image


@pytest.fixture
def mock_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def loader() -> PanelTextureLoader:
    return PanelTextureLoader(barks_panels_are_encrypted=False)


class TestPanelTextureLoader:
    def test_init(self, loader: PanelTextureLoader) -> None:
        assert isinstance(loader, PanelTextureLoader)
        assert loader._barks_panels_are_encrypted is False

    def test_load_texture_success(
        self, loader: PanelTextureLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock()
        mock_pil = MagicMock(spec=Image.Image)
        mock_pil.size = (100, 100)
        mock_pil.tobytes.return_value = b"pixels"

        # Mock Texture class in the module
        with patch.object(loader_module, Texture.__name__) as mock_texture_cls:
            mock_texture = MagicMock(spec=Texture)
            mock_texture_cls.create.return_value = mock_texture

            # Mock _start_worker to intercept the internal callback
            with patch.object(
                loader, PanelTextureLoader._start_worker.__name__
            ) as mock_start_worker:
                loader.load_texture(mock_path, mock_callback)

                # Verify _start_worker called
                mock_start_worker.assert_called_once()
                args, kwargs = mock_start_worker.call_args
                assert args[0] == mock_path
                pil_callback = kwargs["callback"]

                # Simulate success in worker
                pil_callback(mock_pil, None)

                # Verify Texture creation
                mock_texture_cls.create.assert_called_once_with(size=(100, 100))
                mock_texture.blit_buffer.assert_called_once_with(
                    b"pixels", colorfmt="rgba", bufferfmt="ubyte"
                )
                mock_texture.flip_vertical.assert_called_once()

                # Verify user callback
                mock_callback.assert_called_once_with(mock_texture, None)

    def test_load_texture_error(self, loader: PanelTextureLoader, mock_callback: MagicMock) -> None:
        mock_path = MagicMock()
        error = Exception("Load failed")

        with patch.object(loader, PanelTextureLoader._start_worker.__name__) as mock_start_worker:
            loader.load_texture(mock_path, mock_callback)

            _args, kwargs = mock_start_worker.call_args
            pil_callback = kwargs["callback"]

            # Simulate error
            pil_callback(None, error)

            mock_callback.assert_called_once_with(None, error)

    def test_pil_to_texture(self) -> None:
        # Test the static method directly.
        mock_pil = MagicMock(spec=Image.Image)
        mock_pil.size = (50, 50)
        mock_pil.tobytes.return_value = b"data"

        with patch.object(loader_module, Texture.__name__) as mock_texture_cls:
            mock_tex = MagicMock()
            mock_texture_cls.create.return_value = mock_tex

            # noinspection PyProtectedMember
            result = PanelTextureLoader._pil_to_texture(mock_pil)

            mock_texture_cls.create.assert_called_once_with(size=(50, 50))
            mock_tex.blit_buffer.assert_called_once_with(
                b"data", colorfmt="rgba", bufferfmt="ubyte"
            )
            mock_tex.flip_vertical.assert_called_once()
            assert result == mock_tex
