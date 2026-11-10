# ruff: noqa: SLF001
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.panel_image_loader import PanelImageLoader
from barks_reader.ui import panel_texture_loader as loader_module
from barks_reader.ui.panel_texture_loader import PanelTextureLoader
from kivy.core.image import Texture
from PIL import Image


@pytest.fixture
def mock_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_pil_loader() -> MagicMock:
    return MagicMock(spec=PanelImageLoader)


@pytest.fixture
def loader(mock_pil_loader: MagicMock) -> PanelTextureLoader:
    return PanelTextureLoader(pil_loader=mock_pil_loader)


class TestPanelTextureLoaderComposition:
    """Composition (not inheritance) over :class:`PanelImageLoader`."""

    def test_default_constructs_own_pil_loader(self) -> None:
        tl = PanelTextureLoader()
        assert isinstance(tl._pil_loader, PanelImageLoader)

    def test_cancel_delegates_to_pil_loader(
        self, loader: PanelTextureLoader, mock_pil_loader: MagicMock
    ) -> None:
        loader.cancel()
        mock_pil_loader.cancel.assert_called_once()

    def test_is_not_subclass_of_pil_loader(self) -> None:
        assert not issubclass(PanelTextureLoader, PanelImageLoader)


class TestLoadTexture:
    def test_load_texture_success(
        self,
        loader: PanelTextureLoader,
        mock_pil_loader: MagicMock,
        mock_callback: MagicMock,
    ) -> None:
        mock_path = MagicMock()
        mock_pil = MagicMock(spec=Image.Image)
        mock_pil.size = (100, 100)
        mock_pil.tobytes.return_value = b"pixels"

        with patch.object(loader_module, "Texture") as mock_texture_cls:
            mock_texture = MagicMock(spec=Texture)
            mock_texture_cls.create.return_value = mock_texture

            loader.load_texture(mock_path, mock_callback)

            # Verify the pil loader was delegated to with an internal wrapping callback.
            mock_pil_loader.load_pil.assert_called_once()
            args, _ = mock_pil_loader.load_pil.call_args
            assert args[0] is mock_path
            pil_callback = args[1]

            # Simulate successful PIL load arriving on the UI thread.
            pil_callback(mock_pil, None)

            mock_texture_cls.create.assert_called_once_with(size=(100, 100))
            mock_texture.blit_buffer.assert_called_once_with(
                b"pixels", colorfmt="rgba", bufferfmt="ubyte"
            )
            mock_texture.flip_vertical.assert_called_once()
            mock_callback.assert_called_once_with(mock_texture, None)

    def test_load_texture_error(
        self,
        loader: PanelTextureLoader,
        mock_pil_loader: MagicMock,
        mock_callback: MagicMock,
    ) -> None:
        mock_path = MagicMock()
        error = OSError("Load failed")

        loader.load_texture(mock_path, mock_callback)

        args, _ = mock_pil_loader.load_pil.call_args
        pil_callback = args[1]

        pil_callback(None, error)

        mock_callback.assert_called_once_with(None, error)

    def test_pil_to_texture_is_static(self) -> None:
        mock_pil = MagicMock(spec=Image.Image)
        mock_pil.size = (50, 50)
        mock_pil.tobytes.return_value = b"data"

        with patch.object(loader_module, "Texture") as mock_texture_cls:
            mock_tex = MagicMock()
            mock_texture_cls.create.return_value = mock_tex

            result = PanelTextureLoader._pil_to_texture(mock_pil)

            mock_texture_cls.create.assert_called_once_with(size=(50, 50))
            mock_tex.blit_buffer.assert_called_once_with(
                b"data", colorfmt="rgba", bufferfmt="ubyte"
            )
            mock_tex.flip_vertical.assert_called_once()
            assert result is mock_tex


class TestRealTexture:
    """The image and the texture are real here: the tests above stand both in."""

    def test_an_rgba_images_pixels_are_the_textures_top_row_first(self) -> None:
        red, green, blue, clear = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (9, 8, 7, 0)
        pixels = bytes([*red, *green, *blue, *clear])  # top row, then bottom row
        image = Image.new("RGBA", (2, 2), red)
        image.paste(green, (1, 0, 2, 1))
        image.paste(blue, (0, 1, 1, 2))
        image.paste(clear, (1, 1, 2, 2))
        assert image.tobytes() == pixels

        texture = PanelTextureLoader._pil_to_texture(image)

        assert texture.size == (2, 2)
        assert texture.colorfmt == "rgba"
        assert texture.pixels == pixels
        # Kivy's origin is bottom-left: flipped, the image's top row is drawn at the top.
        bottom_left_v, top_left_v = texture.tex_coords[1], texture.tex_coords[5]
        assert (bottom_left_v, top_left_v) == (1.0, 0.0)
