from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from barks_reader.core.reader_file_paths import FileTypes

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.reader_file_paths import ReaderFilePaths


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
            List of (path, is_edited) tuples.

        """
        getter = self._file_paths.FILE_TYPE_FILE_GETTERS.get(category)
        if getter is None:
            return []

        if category == FileTypes.COVER:
            # COVER getter returns a single PanelPath or None.
            cover_file = getter(title_str, prefer_edited)
            if not cover_file:
                return []
            return [(cover_file, prefer_edited)]  # ty: ignore[invalid-return-type]

        # Other getters return list[PanelPath].
        path_list = getter(title_str, prefer_edited)
        assert path_list is not None
        if not path_list:
            return []
        return [(f, prefer_edited) for f in path_list]  # ty: ignore[not-iterable]

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
        return self._file_paths.get_comic_favourite_files_dir()

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
            Dict mapping FileTypes to sets of (path, is_edited) tuples.

        """
        image_dict: dict[FileTypes, set[tuple[PanelPath, bool]]] = defaultdict(set)

        for file_type in FileTypes:
            if file_type == FileTypes.NONTITLE:
                continue

            edited_files = self.resolve(title_str, file_type, prefer_edited=True)
            all_files = self.resolve(title_str, file_type, prefer_edited=False)

            edited_paths = {path for path, _ in edited_files}

            if edited_files:
                image_dict[file_type].update({(f, True) for f, _ in edited_files})
            if all_files:
                image_dict[file_type].update(
                    {(f, False) for f, _ in all_files if f not in edited_paths}
                )

        return image_dict
