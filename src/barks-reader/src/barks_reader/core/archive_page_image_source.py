"""Production ``PageImageSource`` backed by ZIP archives.

Handles both prebuilt CBZ archives and Fantagraphics volume archives
(with override/extra image priority). Actual read/decode/resize/encode
stages live in :mod:`image_pipeline`; this module composes them and
owns archive-specific source resolution.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comics_consts import PageType
from loguru import logger

from .image_pipeline import (
    decode_pil,
    encode_png_stream,
    load_pil,
    resize_contain,
)
from .reader_utils import PNG_EXT_FOR_KIVY, is_blank_page, is_title_page

if TYPE_CHECKING:
    import io

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
    from PIL.Image import Image

    from .comic_book_page_info import PageInfo
    from .fantagraphics_volumes import FantagraphicsArchive


class ArchivePageImageSource:
    """Loads display-ready page images from ZIP archives.

    Owns the archive lifecycle: call :meth:`open` before loading pages
    and :meth:`close` when done. Composes the shared
    :mod:`image_pipeline` stages; this class only adds the logic that
    is archive-specific: source resolution (prebuilt vs. Fantagraphics
    with override priority) and optional transformation via
    ``ComicBookImageBuilder``.

    Args:
        archive_path: Path to the main ZIP archive (prebuilt CBZ or Fantagraphics volume).
        fanta_volume_archive: Fantagraphics volume metadata, or ``None`` for prebuilt mode.
        comic_book_image_builder: Image builder for Fantagraphics sources, or ``None``.
        empty_page_image: Raw bytes for the blank/title page placeholder.
        use_fantagraphics_overrides: Whether to prefer override images over originals.
        max_width: Maximum display width for resizing.
        max_height: Maximum display height for resizing.

    """

    def __init__(
        self,
        archive_path: Path,
        fanta_volume_archive: FantagraphicsArchive | None,
        comic_book_image_builder: ComicBookImageBuilder | None,
        empty_page_image: bytes,
        use_fantagraphics_overrides: bool,
        max_width: int,
        max_height: int,
    ) -> None:
        self._archive_path = archive_path
        self._archive: zipfile.ZipFile | None = None
        self._fanta_volume_archive = fanta_volume_archive
        self._comic_book_image_builder = comic_book_image_builder
        self._empty_page_image = empty_page_image
        self._use_fantagraphics_overrides = use_fantagraphics_overrides
        self._max_width = max_width
        self._max_height = max_height

    def open(self) -> None:
        """Open the backing ZIP archive. Must be called before :meth:`load_page_image`."""
        if self._fanta_volume_archive is not None and self._fanta_volume_archive.is_missing:
            # The library volume is absent; this comic is served entirely from bundled
            # override/extra pages. There is no real archive to open (its filename is a
            # "N-MISSING.cbz" placeholder), so leave it unopened.
            self._archive = None
            return
        self._archive = zipfile.ZipFile(self._archive_path, "r")

    def close(self) -> None:
        """Close the backing ZIP archive and release override resources."""
        if self._archive:
            self._archive.close()
            self._archive = None
        if self._fanta_volume_archive:
            self._fanta_volume_archive.override_archive = None

    def load_page_image(self, page_info: PageInfo) -> tuple[io.BytesIO, str]:
        """Load, transform, resize, and encode a page image.

        Args:
            page_info: Metadata identifying which page to load.

        Returns:
            A tuple of (*png_bytes_stream*, *kivy_image_ext*).

        """
        image_path, is_from_archive = self._get_image_path(page_info)

        logger.debug(
            f'Loading page index {page_info.page_index} (page "{page_info.display_page_num}"):'
            f' image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        pil_image = self._read_image(page_info, image_path, is_from_archive)

        if self._fanta_volume_archive:
            assert self._comic_book_image_builder
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        resized = resize_contain(pil_image, self._max_width, self._max_height)
        return encode_png_stream(resized, compress_level=0), PNG_EXT_FOR_KIVY

    def get_image_info_str(self, page_info: PageInfo) -> str:
        """Return a human-readable description of the image source for *page_info*."""
        image_path, is_from_archive = self._get_image_path(page_info)
        file_source = "from archive" if is_from_archive else "from override"
        return f'"{image_path!s}" ({file_source})'

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_image_path(self, page_info: PageInfo) -> tuple[str, bool]:
        if not self._fanta_volume_archive:
            raw = Path("images") / page_info.dest_page.page_filename, True
        else:
            raw = self._get_fanta_volume_image_path(page_info)

        # ZIP files always use '/' as a separator (even on Windows).
        return str(raw[0]).replace("\\", "/"), raw[1]

    def _get_fanta_volume_image_path(self, page_info: PageInfo) -> tuple[Path, bool]:
        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return Path("__empty_page__"), False

        page_str = Path(page_info.srce_page.page_filename).stem

        assert self._fanta_volume_archive

        if page_str in self._fanta_volume_archive.extra_images_page_map:
            return Path(self._fanta_volume_archive.extra_images_page_map[page_str]), False

        if self._use_fantagraphics_overrides and (
            page_str in self._fanta_volume_archive.override_images_page_map
        ):
            return Path(self._fanta_volume_archive.override_images_page_map[page_str]), False

        return Path(self._fanta_volume_archive.archive_images_page_map[page_str]), True

    def _read_image(self, page_info: PageInfo, image_path: str, is_from_archive: bool) -> Image:
        if is_from_archive:
            assert self._archive is not None, (
                "Page requires the Fantagraphics library archive, but it is not available."
            )
            return load_pil(
                zipfile.Path(self._archive, at=str(image_path)),
                encrypted_zip=False,
                use_ext_hint=True,
            )

        if page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            ext = Path(image_path).suffix if image_path != "__empty_page__" else ".jpg"
            return decode_pil(self._empty_page_image, ext=ext)

        assert self._fanta_volume_archive is not None
        assert self._fanta_volume_archive.override_archive is not None
        return load_pil(
            zipfile.Path(self._fanta_volume_archive.override_archive, at=str(image_path)),
            encrypted_zip=True,
            use_ext_hint=True,
        )
