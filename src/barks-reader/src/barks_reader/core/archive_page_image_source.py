"""Production ``PageImageSource`` backed by ZIP archives.

Handles both prebuilt CBZ archives and Fantagraphics volume archives
(with override/extra image priority), image transformation via
``ComicBookImageBuilder``, and resizing to display dimensions.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.comics_consts import PageType
from comic_utils.pil_image_utils import (
    get_pil_image_as_png_bytes,
    load_pil_image_from_bytes,
    load_pil_image_from_zip,
)
from loguru import logger
from PIL import Image as PilImage
from PIL import ImageOps

from barks_reader.core.reader_utils import PNG_EXT_FOR_KIVY, is_blank_page, is_title_page

if TYPE_CHECKING:
    import io

    from barks_build_comic_images.build_comic_images import ComicBookImageBuilder

    from barks_reader.core.comic_book_page_info import PageInfo
    from barks_reader.core.fantagraphics_volumes import FantagraphicsArchive


class ArchivePageImageSource:
    """Loads display-ready page images from ZIP archives.

    Owns the archive lifecycle: call :meth:`open` before loading pages
    and :meth:`close` when done.  Handles image source resolution
    (prebuilt vs. Fantagraphics with override priority), raw I/O
    (ZIP reads, decryption), optional transformation via
    ``ComicBookImageBuilder``, and LANCZOS resizing.

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
        return self._transform_and_encode(pil_image, page_info)

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

    def _read_image(
        self, page_info: PageInfo, image_path: str, is_from_archive: bool
    ) -> PilImage.Image:
        assert self._archive is not None

        if is_from_archive:
            zip_path = zipfile.Path(self._archive, at=str(image_path))
            return load_pil_image_from_zip(zip_path, encrypted=False)

        if page_info.srce_page.page_type in [PageType.BLANK_PAGE, PageType.TITLE]:
            ext = Path(image_path).suffix if image_path != "__empty_page__" else ".png"
            return load_pil_image_from_bytes(self._empty_page_image, ext)

        assert self._fanta_volume_archive is not None
        assert self._fanta_volume_archive.override_archive is not None
        zip_path = zipfile.Path(self._fanta_volume_archive.override_archive, at=str(image_path))
        return load_pil_image_from_zip(zip_path, encrypted=True)

    def _transform_and_encode(
        self, pil_image: PilImage.Image, page_info: PageInfo
    ) -> tuple[io.BytesIO, str]:
        if self._fanta_volume_archive:
            assert self._comic_book_image_builder
            pil_image = self._comic_book_image_builder.get_dest_page_image(
                pil_image, page_info.srce_page, page_info.dest_page
            )

        pil_image_resized = ImageOps.contain(
            pil_image,
            (self._max_width, self._max_height),
            PilImage.Resampling.LANCZOS,
        )

        return get_pil_image_as_png_bytes(pil_image_resized, compress_level=0), PNG_EXT_FOR_KIVY
