"""Integration tests for :class:`ArchivePageImageSource`.

Uses real ZIP archives with real PNG bytes on disk to exercise the prebuilt
(non-Fantagraphics) path end-to-end: open → resolve → read → resize → encode.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import CleanPage
from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.fantagraphics_volumes import FantagraphicsArchive
from PIL import Image


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


def _make_fanta_archive(
    *,
    archive: dict[str, str],
    overrides: dict[str, str] | None = None,
    extras: dict[str, str] | None = None,
) -> FantagraphicsArchive:
    return FantagraphicsArchive(
        fanta_volume=1,
        archive_filename=Path("vol1.zip"),
        archive_image_subdir=None,
        image_ext=".jpg",
        first_page=1,
        last_page=10,
        archive_images_page_map={k: Path(v) for k, v in archive.items()},
        override_images_page_map={k: Path(v) for k, v in (overrides or {}).items()},
        extra_images_page_map={k: Path(v) for k, v in (extras or {}).items()},
        override_archive_filename=None,
    )


def _fanta_source(
    fanta_archive: FantagraphicsArchive, *, use_overrides: bool
) -> ArchivePageImageSource:
    return ArchivePageImageSource(
        archive_path=Path("vol1.zip"),
        fanta_volume_archive=fanta_archive,
        comic_book_image_builder=None,
        empty_page_image=b"",
        use_fantagraphics_overrides=use_overrides,
        max_width=100,
        max_height=100,
    )


class TestFantagraphicsSourceResolution:
    """The extra > override > archive priority chain in `_get_fanta_volume_image_path`.

    Exercised through the public `get_image_info_str`, which reports both the
    resolved path and whether it came from the archive or an override/extra.
    """

    def test_archive_used_when_no_overrides(self) -> None:
        """With overrides off, a body page resolves to the archive image."""
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)

        info = source.get_image_info_str(_make_page_info("101.jpg"))

        assert "arch/101.jpg" in info
        assert "from archive" in info

    def test_override_preferred_when_enabled(self) -> None:
        """With overrides on, an override image wins over the archive original."""
        fanta = _make_fanta_archive(
            archive={"101": "arch/101.jpg"}, overrides={"101": "over/101.png"}
        )
        source = _fanta_source(fanta, use_overrides=True)

        info = source.get_image_info_str(_make_page_info("101.jpg"))

        assert "over/101.png" in info
        assert "from override" in info

    def test_override_ignored_when_disabled(self) -> None:
        """An override present but disabled falls back to the archive original."""
        fanta = _make_fanta_archive(
            archive={"101": "arch/101.jpg"}, overrides={"101": "over/101.png"}
        )
        source = _fanta_source(fanta, use_overrides=False)

        info = source.get_image_info_str(_make_page_info("101.jpg"))

        assert "arch/101.jpg" in info
        assert "from archive" in info

    def test_extra_image_wins_over_override(self) -> None:
        """An extra image takes priority over an override for the same page."""
        fanta = _make_fanta_archive(
            archive={"200": "arch/200.jpg"},
            overrides={"200": "over/200.png"},
            extras={"200": "extra/200.png"},
        )
        source = _fanta_source(fanta, use_overrides=True)

        info = source.get_image_info_str(_make_page_info("200.jpg"))

        assert "extra/200.png" in info
        assert "from override" in info  # "from override" == not from the main archive

    def test_title_page_resolves_to_empty_placeholder(self) -> None:
        """A title page short-circuits to the empty-page placeholder, off-archive."""
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)

        srce = CleanPage("empty_page.jpg", PageType.TITLE)
        page_info = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.TITLE,
            srce_page=srce,
            dest_page=srce,
        )

        info = source.get_image_info_str(page_info)

        assert "__empty_page__" in info
        assert "from override" in info
