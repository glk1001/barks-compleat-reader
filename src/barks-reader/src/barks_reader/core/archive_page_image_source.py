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
from comic_utils.comic_consts import JPG_FILE_EXT
from loguru import logger

from .fantagraphics_volumes import PageSourceKind
from .image_pipeline import (
    decode_pil,
    decode_pil_for,
    load_pil,
    read_raw_bytes,
    resize_contain,
)
from .page_image import PageImage

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
        # This source's own, not on the volume's archive record: that is shared with
        # every comic of the volume, and a source closing must close only what it opened.
        self._override_archive: zipfile.ZipFile | None = None
        self._fanta_volume_archive = fanta_volume_archive
        self._comic_book_image_builder = comic_book_image_builder
        self._empty_page_image = empty_page_image
        self._use_fantagraphics_overrides = use_fantagraphics_overrides
        self._max_width = max_width
        self._max_height = max_height
        self._decode_whole = decode_whole

    def open(self) -> None:
        """Open the backing ZIP archives. Must be called before :meth:`load_page_image`."""
        if self._fanta_volume_archive is not None and self._fanta_volume_archive.has_overrides():
            assert self._fanta_volume_archive.override_archive_filename
            self._override_archive = zipfile.ZipFile(
                self._fanta_volume_archive.override_archive_filename, "r"
            )

        if self._fanta_volume_archive is not None and self._fanta_volume_archive.is_missing:
            # The library volume is absent; this comic is served entirely from bundled
            # override/extra pages. There is no real archive to open (its filename is a
            # "N-MISSING.cbz" placeholder), so leave it unopened.
            self._archive = None
            return
        self._archive = zipfile.ZipFile(self._archive_path, "r")

    def close(self) -> None:
        """Close the backing ZIP archives. Safe to call again: the loader thread may."""
        archive, self._archive = self._archive, None
        if archive:
            archive.close()
        override_archive, self._override_archive = self._override_archive, None
        if override_archive:
            override_archive.close()

    def load_page_image(self, page_info: PageInfo) -> PageImage:
        """Load, transform and resize a page image.

        Args:
            page_info: Metadata identifying which page to load.

        Returns:
            The page as the pixels a texture takes.

        """
        image_path, kind = self._get_image_path(page_info)

        logger.debug(
            f'Loading page index {page_info.page_index} (page "{page_info.display_page_num}"):'
            f' image_path = "{image_path}", source = {kind.value}.'
        )

        pil_image, srce_scale = self._read_image(page_info, image_path, kind)

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
        image_path, kind = self._get_image_path(page_info)
        return f'"{image_path}" (from {kind.value})'

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _window_box(self) -> tuple[int, int]:
        return self._max_width, self._max_height

    def _get_image_path(self, page_info: PageInfo) -> tuple[str, PageSourceKind]:
        if not self._fanta_volume_archive:
            path = Path(IMAGES_SUBDIR) / page_info.dest_page.page_filename
            kind = PageSourceKind.ARCHIVE
        else:
            source = self._fanta_volume_archive.page_source_for(
                page_info, use_overrides=self._use_fantagraphics_overrides
            )
            if source.path is None:
                raise KeyError(page_info.srce_page.page_filename)
            path, kind = source.path, source.kind

        # ZIP files always use '/' as a separator (even on Windows).
        return path.as_posix(), kind

    def _read_image(
        self, page_info: PageInfo, image_path: str, kind: PageSourceKind
    ) -> tuple[Image, float]:
        """Decode the page's source image, and say what scale of itself it was decoded at.

        A prebuilt page goes straight from the decode to the resize, so its JPEG is
        decoded no larger than the window needs. A volume page is laid out by the
        builder, which says how small its scan may be decoded for the page it will
        build at the window's scale; the scale it came out at goes back to the builder
        with the image, so the panels box can follow. Override pages are decoded whole,
        and so is every page when the reader is set to decode pages whole.
        """
        if kind is PageSourceKind.ARCHIVE:
            assert self._archive is not None, (
                "Page requires the Fantagraphics library archive, but it is not available."
            )
            raw = read_raw_bytes(zipfile.Path(self._archive, at=image_path))
            ext = Path(image_path).suffix
            if self._decode_whole:
                return decode_pil(raw, ext=ext), 1.0
            if self._fanta_volume_archive is None:
                return decode_pil(raw, ext=ext, fit_within=self._window_box()), 1.0
            builder = self._comic_book_image_builder
            assert builder
            return decode_pil_for(
                raw,
                ext=ext,
                size_needed=lambda srce_size: builder.get_source_size_needed(
                    page_info.srce_page, page_info.dest_page, srce_size, self._window_box()
                ),
            )

        if kind is PageSourceKind.PLACEHOLDER:
            # The resolver's verdict decides, not the page type: a TITLE-typed page that
            # resolved to a real override file is read like any other override page.
            # Nothing in any zip backs the placeholder; its bundled bytes are a JPEG.
            return decode_pil(self._empty_page_image, ext=JPG_FILE_EXT), 1.0

        assert self._override_archive is not None
        return load_pil(
            zipfile.Path(self._override_archive, at=image_path),
            encrypted_zip=True,
            use_ext_hint=True,
        ), 1.0
