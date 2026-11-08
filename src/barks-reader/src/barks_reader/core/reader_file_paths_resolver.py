from __future__ import annotations

from typing import TYPE_CHECKING

from .image_selector import resolve_all_title_image_files
from .reader_file_paths import FileTypes, PanelDirNames, is_edited_file

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles
    from comic_utils.comic_consts import PanelPath

    from .reader_file_paths import ReaderFilePaths


class ReaderFilePathsResolver:
    """Concrete ImageFileResolver that delegates to ReaderFilePaths.

    Wraps the existing ReaderFilePaths getter methods behind the
    ImageFileResolver protocol, providing a single `resolve()` entry point.
    """

    def __init__(self, file_paths: ReaderFilePaths) -> None:
        self._file_paths = file_paths

    def resolve(
        self, title_str: str, category: FileTypes, prefer_edited: bool
    ) -> list[tuple[PanelPath, bool]]:
        """Resolve image files for a title and category.

        Args:
            title_str: The title string to look up.
            category: The file type category to search.
            prefer_edited: If True, return only edited versions when available.

        Returns:
            List of (path, is_edited) tuples: is_edited says whether the file is an
            edited copy, not which pass found it (with no edited copy, the edited pass
            returns the plain files).

        """
        return [
            (f, is_edited_file(f))
            for f in self._file_paths.get_title_files(category, title_str, prefer_edited)
        ]

    def get_nontitle_files(self) -> list[PanelPath]:
        """Return all non-title image files."""
        return self._file_paths.get_nontitle_files()

    def get_comic_inset_file(self, title: Titles, prefer_edited: bool = False) -> PanelPath:
        """Return the inset file path for a title."""
        return self._file_paths.get_comic_inset_file(title, prefer_edited)

    def get_edited_version_if_possible(self, image_file: PanelPath) -> tuple[PanelPath, bool]:
        """Return an edited version of the image if available."""
        return self._file_paths.get_edited_version_if_possible(image_file)

    def get_comic_favourite_files_dir(self) -> PanelPath:
        """Return the directory containing favourite image files."""
        return self._file_paths.get_panel_dir(PanelDirNames.FAVOURITES)

    def get_file_ext(self) -> str:
        """Return the file extension used for panel images."""
        return self._file_paths.get_file_ext()

    def get_comic_search_files(self, title_str: str, prefer_edited: bool) -> list[PanelPath]:
        """Return search image files for a title."""
        return self._file_paths.get_comic_search_files(title_str, prefer_edited)

    def get_file_type_titles(
        self, file_type: FileTypes, allowed_titles: set[str] | None = None
    ) -> list[str]:
        """Return titles that have files of the given type."""
        return self._file_paths.get_file_type_titles(file_type, allowed_titles)

    def resolve_all_title_image_files(
        self, title_str: str
    ) -> dict[FileTypes, set[tuple[PanelPath, bool]]]:
        """Resolve all image files for a title across all categories.

        Args:
            title_str: The title string to look up.

        Returns:
            Dict mapping FileTypes to sets of (path, is_edited) tuples; see
            `image_selector.resolve_all_title_image_files`.

        """
        return resolve_all_title_image_files(self, title_str)
