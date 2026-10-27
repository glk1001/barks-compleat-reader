"""Production ``PageImageSource`` backed by ZIP archives.

Handles both prebuilt CBZ archives and Fantagraphics volume archives
(with override/extra image priority). Actual read/decode/resize
stages live in :mod:`image_pipeline`; this module composes them and
owns archive-specific source resolution.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comics_consts import IMAGES_SUBDIR
from loguru import logger

from .image_pipeline import (
    decode_pil,
    decoded_scale,
    image_size,
    load_pil,
    read_raw_bytes,
    resize_contain,
)
from .log_markers import EMPTY_PAGE_IMAGE
from .page_image import PageImage
from .reader_utils import is_blank_page, is_title_page

if TYPE_CHECKING:
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
        decode_whole: Decode every page image whole, however small the window: the
            reader's setting for the sharpest page at the cost of the load.

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
        decode_whole: bool = False,
    ) -> None:
        self._archive_path = archive_path
        self._archive: zipfile.ZipFile | None = None
        self._fanta_volume_archive = fanta_volume_archive
        self._comic_book_image_builder = comic_book_image_builder
        self._empty_page_image = empty_page_image
        self._use_fantagraphics_overrides = use_fantagraphics_overrides
        self._max_width = max_width
        self._max_height = max_height
        self._decode_whole = decode_whole

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
            override_archive = self._fanta_volume_archive.override_archive
            if override_archive is not None:
                override_archive.close()
            self._fanta_volume_archive.override_archive = None

    def load_page_image(self, page_info: PageInfo) -> PageImage:
        """Load, transform and resize a page image.

        Args:
            page_info: Metadata identifying which page to load.

        Returns:
            The page as the pixels a texture takes.

        """
        image_path, is_from_archive = self._get_image_path(page_info)

        logger.debug(
            f'Loading page index {page_info.page_index} (page "{page_info.display_page_num}"):'
            f' image_path = "{image_path}", is_from_archive = {is_from_archive}.'
        )

        pil_image, srce_scale = self._read_image(page_info, image_path, is_from_archive)

        if self._fanta_volume_archive:
            assert self._comic_book_image_builder
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image,
                page_info.srce_page,
                page_info.dest_page,
                fit_within=self._window_box(),
                srce_scale=srce_scale,
            )

        resized = resize_contain(pil_image, self._max_width, self._max_height)
        return PageImage.from_pil(resized)

    def get_image_info_str(self, page_info: PageInfo) -> str:
        """Return a human-readable description of the image source for *page_info*."""
        image_path, is_from_archive = self._get_image_path(page_info)
        file_source = "from archive" if is_from_archive else "from override"
        return f'"{image_path!s}" ({file_source})'

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _window_box(self) -> tuple[int, int]:
        return self._max_width, self._max_height

    def _get_image_path(self, page_info: PageInfo) -> tuple[str, bool]:
        if not self._fanta_volume_archive:
            raw = Path(IMAGES_SUBDIR) / page_info.dest_page.page_filename, True
        else:
            raw = self._get_fanta_volume_image_path(page_info)

        # ZIP files always use '/' as a separator (even on Windows).
        return str(raw[0]).replace("\\", "/"), raw[1]

    def _get_fanta_volume_image_path(self, page_info: PageInfo) -> tuple[Path, bool]:
        if is_title_page(page_info.srce_page) or is_blank_page(
            page_info.srce_page.page_filename, page_info.page_type
        ):
            return Path(EMPTY_PAGE_IMAGE), False

        page_str = Path(page_info.srce_page.page_filename).stem

        assert self._fanta_volume_archive

        if page_str in self._fanta_volume_archive.extra_images_page_map:
            return Path(self._fanta_volume_archive.extra_images_page_map[page_str]), False

        if self._use_fantagraphics_overrides and (
            page_str in self._fanta_volume_archive.override_images_page_map
        ):
            return Path(self._fanta_volume_archive.override_images_page_map[page_str]), False

        return Path(self._fanta_volume_archive.archive_images_page_map[page_str]), True

    def _read_image(
        self, page_info: PageInfo, image_path: str, is_from_archive: bool
    ) -> tuple[Image, float]:
        """Decode the page's source image, and say what scale of itself it was decoded at.

        A prebuilt page goes straight from the decode to the resize, so its JPEG is
        decoded no larger than the window needs. A volume page is laid out by the
        builder, which says how small its scan may be decoded for the page it will
        build at the window's scale; the scale it came out at goes back to the builder
        with the image, so the panels box can follow. Override pages are decoded whole,
        and so is every page when the reader is set to decode pages whole.
        """
        if is_from_archive:
            assert self._archive is not None, (
                "Page requires the Fantagraphics library archive, but it is not available."
            )
            raw = read_raw_bytes(zipfile.Path(self._archive, at=str(image_path)))
            ext = Path(image_path).suffix
            if self._decode_whole:
                return decode_pil(raw, ext=ext), 1.0
            if self._fanta_volume_archive is None:
                return decode_pil(raw, ext=ext, fit_within=self._window_box()), 1.0
            assert self._comic_book_image_builder
            srce_size = image_size(raw)
            needed = self._comic_book_image_builder.get_source_size_needed(
                page_info.srce_page, page_info.dest_page, srce_size, self._window_box()
            )
            image = decode_pil(raw, ext=ext, fit_within=needed)
            return image, decoded_scale(srce_size, image.size)

        if image_path == EMPTY_PAGE_IMAGE:
            # The resolver's verdict decides, not the page type: a TITLE-typed page that
            # resolved to a real override file is read like any other override page.
            # Nothing in any zip backs the placeholder; its bundled bytes are a JPEG.
            return decode_pil(self._empty_page_image, ext=".jpg"), 1.0

        assert self._fanta_volume_archive is not None
        assert self._fanta_volume_archive.override_archive is not None
        return load_pil(
            zipfile.Path(self._fanta_volume_archive.override_archive, at=str(image_path)),
            encrypted_zip=True,
            use_ext_hint=True,
        ), 1.0
