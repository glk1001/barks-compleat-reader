"""Integration tests for :class:`ArchivePageImageSource`.

Uses real ZIP archives with real PNG bytes on disk to exercise the prebuilt
(non-Fantagraphics) path end-to-end: open → resolve → read → resize → encode.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import CleanPage
from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.comic_book_page_info import PageInfo
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path


def _make_png_bytes(size: tuple[int, int], color: tuple[int, int, int] = (40, 80, 120)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _write_cbz(zip_path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


def _make_page_info(filename: str, index: int = 0) -> PageInfo:
    srce = CleanPage(filename, PageType.BODY)
    dest = CleanPage(filename, PageType.BODY)
    return PageInfo(
        page_index=index,
        display_page_num=str(index + 1),
        page_type=PageType.BODY,
        srce_page=srce,
        dest_page=dest,
    )


@pytest.fixture
def prebuilt_cbz(tmp_path: Path) -> Path:
    """Real CBZ with one 1000x500 page under images/p01.png."""
    cbz = tmp_path / "book.cbz"
    _write_cbz(cbz, {"images/p01.png": _make_png_bytes((1000, 500))})
    return cbz


class TestArchivePageImageSourcePrebuilt:
    """End-to-end tests against a real CBZ (no Fantagraphics overrides)."""

    def test_load_page_image_returns_resized_png(self, prebuilt_cbz: Path) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=200,
            max_height=200,
        )
        source.open()
        try:
            stream, ext = source.load_page_image(_make_page_info("p01.png"))
        finally:
            source.close()

        assert ext == "png"
        assert stream.tell() == 0
        decoded = Image.open(stream)
        decoded.load()
        # 1000x500 contained within 200x200 -> 200x100 (aspect preserved).
        assert decoded.size == (200, 100)

    def test_close_releases_archive(self, prebuilt_cbz: Path) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=100,
            max_height=100,
        )
        source.open()
        source.close()

        # Second close is a no-op.
        source.close()

    def test_get_image_info_str_describes_source(self, prebuilt_cbz: Path) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=100,
            max_height=100,
        )

        info = source.get_image_info_str(_make_page_info("p01.png"))

        assert "images/p01.png" in info
        assert "from archive" in info

    def test_missing_page_raises(self, prebuilt_cbz: Path) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=100,
            max_height=100,
        )
        source.open()
        try:
            with pytest.raises(FileNotFoundError):
                source.load_page_image(_make_page_info("missing.png"))
        finally:
            source.close()
