"""Integration tests for :class:`ArchivePageImageSource`.

Uses real ZIP archives with real PNG bytes on disk to exercise the prebuilt
(non-Fantagraphics) path end-to-end: open → resolve → read → resize → encode.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import CleanPage
from barks_reader.core import archive_page_image_source as apis_module
from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.fantagraphics_volumes import FantagraphicsArchive
from barks_reader.core.reader_utils import PNG_EXT_FOR_KIVY
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


def _title_page_info(filename: str, page_type: PageType = PageType.TITLE) -> PageInfo:
    srce = CleanPage(filename, page_type)
    return PageInfo(
        page_index=0,
        display_page_num="1",
        page_type=page_type,
        srce_page=srce,
        dest_page=srce,
    )


class TestSourceDescription:
    """`get_image_info_str` is what the reader's debug overlay shows."""

    def test_archive_page_description_in_full(self) -> None:
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)

        assert (
            source.get_image_info_str(_make_page_info("101.jpg")) == '"arch/101.jpg" (from archive)'
        )

    def test_override_page_description_in_full(self) -> None:
        fanta = _make_fanta_archive(
            archive={"101": "arch/101.jpg"}, overrides={"101": "over/101.png"}
        )
        source = _fanta_source(fanta, use_overrides=True)

        assert (
            source.get_image_info_str(_make_page_info("101.jpg"))
            == '"over/101.png" (from override)'
        )

    def test_prebuilt_page_resolves_under_the_images_subdir(self, prebuilt_cbz: Path) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=100,
            max_height=100,
        )

        assert (
            source.get_image_info_str(_make_page_info("p01.png"))
            == '"images/p01.png" (from archive)'
        )

    def test_a_blank_page_resolves_to_the_placeholder(self) -> None:
        """A page named `empty_page` that is *not* a title is a blank page."""
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)

        info = source.get_image_info_str(
            _title_page_info("empty_page.jpg", page_type=PageType.BODY)
        )

        assert info == '"__empty_page__" (from override)'


class TestReadImageDelegation:
    """Which loader `_read_image` calls, and with exactly what.

    The stages themselves live in `image_pipeline`; everything this module decides —
    which zip a page comes from, whether it is encrypted, what extension hint to
    pass — is visible only in the arguments it forwards.
    """

    def test_archive_pages_are_read_from_the_open_archive_unencrypted(
        self, prebuilt_cbz: Path
    ) -> None:
        source = ArchivePageImageSource(
            archive_path=prebuilt_cbz,
            fanta_volume_archive=None,
            comic_book_image_builder=None,
            empty_page_image=b"",
            use_fantagraphics_overrides=False,
            max_width=64,
            max_height=64,
        )
        source.open()
        try:
            with (
                patch.object(apis_module, "load_pil") as mock_load,
                patch.object(apis_module, "resize_contain") as mock_resize,
                patch.object(apis_module, "encode_png_stream") as mock_encode,
            ):
                stream, ext = source.load_page_image(_make_page_info("p01.png"))
        finally:
            source.close()

        zip_path = mock_load.call_args.args[0]
        assert zip_path.at == "images/p01.png"
        assert mock_load.call_args.kwargs == {"encrypted_zip": False, "use_ext_hint": True}

        # The decoded image goes straight to resize, then to a fast (level 0) encode.
        mock_resize.assert_called_once_with(mock_load.return_value, 64, 64)
        mock_encode.assert_called_once_with(mock_resize.return_value, compress_level=0)
        assert (stream, ext) == (mock_encode.return_value, PNG_EXT_FOR_KIVY)

    def test_override_pages_are_read_from_the_encrypted_override_zip(self, tmp_path: Path) -> None:
        override_zip_path = tmp_path / "overrides.zip"
        _write_cbz(override_zip_path, {"over/101.png": _make_png_bytes((4, 4))})
        fanta = _make_fanta_archive(
            archive={"101": "arch/101.jpg"}, overrides={"101": "over/101.png"}
        )
        source = _fanta_source(fanta, use_overrides=True)
        source._comic_book_image_builder = MagicMock()  # noqa: SLF001

        with (
            zipfile.ZipFile(override_zip_path, "r") as override_archive,
            patch.object(apis_module, "load_pil") as mock_load,
            patch.object(apis_module, "resize_contain"),
            patch.object(apis_module, "encode_png_stream"),
        ):
            fanta.override_archive = override_archive
            source.load_page_image(_make_page_info("101.jpg"))

        zip_path = mock_load.call_args.args[0]
        assert Path(zip_path.root.filename) == override_zip_path
        assert zip_path.at == "over/101.png"
        # Bundled override zips are encrypted; the library archive is not.
        assert mock_load.call_args.kwargs == {"encrypted_zip": True, "use_ext_hint": True}

    def test_the_placeholder_page_is_decoded_as_a_jpeg(self) -> None:
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)
        source._comic_book_image_builder = MagicMock()  # noqa: SLF001
        source._empty_page_image = b"placeholder-bytes"  # noqa: SLF001

        with (
            patch.object(apis_module, "decode_pil") as mock_decode,
            patch.object(apis_module, "resize_contain"),
            patch.object(apis_module, "encode_png_stream"),
        ):
            source.load_page_image(_title_page_info("empty_page.jpg"))

        # There is no real file behind `__empty_page__`, so the extension is assumed.
        mock_decode.assert_called_once_with(b"placeholder-bytes", ext=".jpg")

    def test_a_real_off_archive_page_keeps_its_own_extension(self) -> None:
        """A TITLE-typed page that is *not* the placeholder still has a real file.

        `is_title_page` only matches the `empty_page` stem, so this page resolves
        through the override map and its extension must come from that path.
        """
        fanta = _make_fanta_archive(
            archive={"101": "arch/101.jpg"}, overrides={"101": "over/101.png"}
        )
        fanta.override_archive = MagicMock()
        source = _fanta_source(fanta, use_overrides=True)
        source._comic_book_image_builder = MagicMock()  # noqa: SLF001
        source._empty_page_image = b"placeholder-bytes"  # noqa: SLF001

        with (
            patch.object(apis_module, "decode_pil") as mock_decode,
            patch.object(apis_module, "resize_contain"),
            patch.object(apis_module, "encode_png_stream"),
        ):
            source.load_page_image(_title_page_info("101.jpg"))

        mock_decode.assert_called_once_with(b"placeholder-bytes", ext=".png")

    def test_fantagraphics_pages_are_rebuilt_by_the_image_builder(self, tmp_path: Path) -> None:
        volume_zip = tmp_path / "vol1.zip"
        _write_cbz(volume_zip, {"arch/101.jpg": _make_png_bytes((4, 4))})
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        source = _fanta_source(fanta, use_overrides=False)
        source._archive_path = volume_zip  # noqa: SLF001
        builder = MagicMock()
        source._comic_book_image_builder = builder  # noqa: SLF001
        source.open()
        page_info = _make_page_info("101.jpg")

        try:
            with (
                patch.object(apis_module, "load_pil") as mock_load,
                patch.object(apis_module, "resize_contain") as mock_resize,
                patch.object(apis_module, "encode_png_stream"),
            ):
                source.load_page_image(page_info)
        finally:
            source.close()

        # The raw page is transformed before resizing, using *this* page's geometry.
        builder.get_dest_page_image.assert_called_once_with(
            mock_load.return_value, page_info.srce_page, page_info.dest_page
        )
        mock_resize.assert_called_once_with(builder.get_dest_page_image.return_value, 100, 100)

    def test_a_page_needing_the_library_archive_fails_loudly_when_it_is_absent(self) -> None:
        """A missing volume leaves `_archive` unopened.

        Archive-backed pages must not silently load from nothing.
        """
        fanta = _make_fanta_archive(archive={"101": "arch/101.jpg"})
        fanta.is_missing = True
        source = _fanta_source(fanta, use_overrides=False)
        source.open()

        assert source._archive is None  # noqa: SLF001
        with pytest.raises(AssertionError, match="requires the Fantagraphics library archive"):
            source.load_page_image(_make_page_info("101.jpg"))
