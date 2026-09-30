"""Tests for the PIL helpers: loading from a file, bytes or a zip, and saving by format."""

from __future__ import annotations

import io
import logging
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from comic_utils import get_panel_bytes, pil_image_utils
from comic_utils.decryption import DecryptionError
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


def _image(size: tuple[int, int] = (40, 20), mode: str = "RGB") -> Image.Image:
    return Image.new(mode, size, (200, 100, 50, 255)[: len(mode)])


def _png(tmp_path: Path, size: tuple[int, int] = (40, 20), mode: str = "RGB") -> Path:
    path = tmp_path / "page.png"
    _image(size, mode).save(path, format="PNG")
    return path


def _png_bytes() -> bytes:
    data = io.BytesIO()
    _image().save(data, format="PNG")
    return data.getvalue()


@pytest.fixture
def root_at_warning() -> Iterator[None]:
    """Hold the root logger at WARNING, and check the loaders put it back after quietening PIL."""
    root = logging.getLogger()
    before = root.level
    root.setLevel(logging.WARNING)
    yield
    assert root.level == logging.WARNING
    root.setLevel(before)


@pytest.mark.usefixtures("root_at_warning")
class TestLoading:
    def test_from_a_file(self, tmp_path: Path) -> None:
        image = pil_image_utils.load_pil_image_for_reading(_png(tmp_path))
        assert image.size == (40, 20)

    def test_its_size(self, tmp_path: Path) -> None:
        assert pil_image_utils.get_image_size(_png(tmp_path, size=(7, 9))) == (7, 9)

    @pytest.mark.parametrize("ext", [".png", ".PNG"])
    def test_from_bytes_by_extension(self, ext: str) -> None:
        assert pil_image_utils.load_pil_image_from_bytes(_png_bytes(), ext).size == (40, 20)

    def test_from_bytes_with_an_unknown_extension_is_refused(self) -> None:
        with pytest.raises(ValueError, match=r"Unsupported image extension for PIL: '\.gif'"):
            pil_image_utils.load_pil_image_from_bytes(_png_bytes(), ".gif")

    def test_from_a_zip_entry(self, tmp_path: Path) -> None:
        with zipfile.ZipFile(tmp_path / "panels.zip", "w") as zf:
            zf.writestr("Insets/page.png", _png_bytes())
        entry = zipfile.Path(tmp_path / "panels.zip", "Insets/page.png")

        image = pil_image_utils.load_pil_image_from_zip(entry, encrypted=False)

        assert image.size == (40, 20)

    def test_from_an_encrypted_zip_entry_decrypts_it_first(self, tmp_path: Path) -> None:
        with zipfile.ZipFile(tmp_path / "panels.zip", "w") as zf:
            zf.writestr("page.png", b"sealed")
        entry = zipfile.Path(tmp_path / "panels.zip", "page.png")

        with patch.object(
            get_panel_bytes, "get_decrypted_bytes", return_value=_png_bytes()
        ) as decrypt:
            image = pil_image_utils.load_pil_image_from_zip(entry, encrypted=True)

        decrypt.assert_called_once_with(b"sealed")
        assert image.size == (40, 20)

    def test_a_decryption_that_gives_nothing_is_an_error(self, tmp_path: Path) -> None:
        with zipfile.ZipFile(tmp_path / "panels.zip", "w") as zf:
            zf.writestr("page.png", b"sealed")
        entry = zipfile.Path(tmp_path / "panels.zip", "page.png")

        with (
            patch.object(get_panel_bytes, "get_decrypted_bytes", return_value=b""),
            pytest.raises(DecryptionError, match="empty bytes"),
        ):
            pil_image_utils.load_pil_image_from_zip(entry, encrypted=True)


class TestInMemory:
    def test_png_bytes(self) -> None:
        data = pil_image_utils.get_pil_image_as_png_bytes(_image())
        data.seek(0)
        with Image.open(data) as image:
            assert (image.format, image.size) == ("PNG", (40, 20))

    def test_jpg_bytes(self) -> None:
        data = pil_image_utils.get_pil_image_as_jpg_bytes(_image())
        data.seek(0)
        with Image.open(data) as image:
            assert (image.format, image.size) == ("JPEG", (40, 20))


class TestFiles:
    def test_copied_to_a_jpg_drops_the_alpha(self, tmp_path: Path) -> None:
        srce = _png(tmp_path, mode="RGBA")
        pil_image_utils.copy_file_to_jpg(srce, tmp_path / "page.jpg")
        with Image.open(tmp_path / "page.jpg") as image:
            assert (image.format, image.mode, image.size) == ("JPEG", "RGB", (40, 20))

    def test_copied_to_a_png_keeps_the_alpha(self, tmp_path: Path) -> None:
        srce = _png(tmp_path, mode="RGBA")
        pil_image_utils.copy_file_to_png(srce, tmp_path / "copy.png")
        with Image.open(tmp_path / "copy.png") as image:
            assert (image.format, image.mode, image.size) == ("PNG", "RGBA", (40, 20))

    @pytest.mark.parametrize(
        ("downscale", "name", "fmt"),
        [
            (pil_image_utils.downscale_jpg, "small.jpg", "JPEG"),
            (pil_image_utils.downscale_png, "small.png", "PNG"),
        ],
    )
    def test_a_downscale_keeps_the_aspect(
        self,
        downscale: Callable[[int, int, Path, Path], None],
        name: str,
        fmt: str,
        tmp_path: Path,
    ) -> None:
        srce = _png(tmp_path, size=(400, 200))
        downscale(100, 100, srce, tmp_path / name)
        with Image.open(tmp_path / name) as image:
            assert (image.format, image.size) == (fmt, (100, 50))

    @pytest.mark.parametrize(("name", "fmt"), [("exact.jpg", "JPEG"), ("exact.png", "PNG")])
    def test_an_exact_resize_takes_the_size_given(
        self, name: str, fmt: str, tmp_path: Path
    ) -> None:
        srce = _png(tmp_path, size=(400, 200), mode="RGBA")
        pil_image_utils.downscale_to_exact_size(50, 60, srce, tmp_path / name)
        with Image.open(tmp_path / name) as image:
            assert (image.format, image.size) == (fmt, (50, 60))

    def test_saving_to_an_unknown_extension_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unsupported image extension"):
            pil_image_utils.save_pil_image(_image(), tmp_path / "page.bmp")

    def test_png_metadata_is_written_under_the_barks_group(self, tmp_path: Path) -> None:
        png = _png(tmp_path)
        pil_image_utils.add_png_metadata(png, {"title": "Lost in the Andes!"})
        with Image.open(png) as image:
            assert image.info["BARKS:title"] == "Lost in the Andes!"

    def test_a_jpg_given_metadata_is_still_the_same_image(self, tmp_path: Path) -> None:
        jpg = tmp_path / "page.jpg"
        _image().save(jpg, format="JPEG")
        pil_image_utils.add_jpg_metadata(jpg, {"title": "Lost in the Andes!"})
        with Image.open(jpg) as image:
            assert (image.format, image.size) == ("JPEG", (40, 20))
