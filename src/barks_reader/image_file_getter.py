from __future__ import annotations

from collections import defaultdict
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_reader.reader_settings import ReaderSettings


class FileTypes(Enum):
    BLACK_AND_WHITE = auto()
    CENSORSHIP = auto()
    CLOSEUP = auto()
    COVER = auto()
    FAVOURITE = auto()
    INSET = auto()
    NONTITLE = auto()
    ORIGINAL_ART = auto()
    SILHOUETTE = auto()
    SPLASH = auto()


ALL_TYPES = set(FileTypes)


class TitleImageFileGetter:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings

        self._FILE_TYPE_GETTERS: dict[
            FileTypes, Callable[[str, bool], None | Path | list[Path]]
        ] = {
            # COVER special case: returns single string or None
            FileTypes.COVER: self._reader_settings.file_paths.get_comic_cover_file,
            FileTypes.BLACK_AND_WHITE: self._reader_settings.file_paths.get_comic_bw_files,
            FileTypes.CENSORSHIP: self._reader_settings.file_paths.get_comic_censorship_files,
            FileTypes.CLOSEUP: self._reader_settings.file_paths.get_comic_closeup_files,
            FileTypes.FAVOURITE: self._reader_settings.file_paths.get_comic_favourite_files,
            FileTypes.INSET: self._reader_settings.file_paths.get_comic_inset_files,
            FileTypes.ORIGINAL_ART: self._reader_settings.file_paths.get_comic_original_art_files,
            FileTypes.SILHOUETTE: self._reader_settings.file_paths.get_comic_silhouette_files,
            FileTypes.SPLASH: self._reader_settings.file_paths.get_comic_splash_files,
        }

    def get_all_title_image_files(self, title_str: str) -> dict[FileTypes, set[tuple[Path, bool]]]:
        image_dict: dict[FileTypes, set[tuple[Path, bool]]] = defaultdict(set)

        for file_type, getter_func in self._FILE_TYPE_GETTERS.items():
            edited_image_files = self._get_files(
                title_str, file_type, getter_func, must_be_edited=True
            )
            all_image_files = self._get_files(
                title_str, file_type, getter_func, must_be_edited=False
            )
            if edited_image_files:
                new_files = {(f, True) for f in edited_image_files}
                image_dict[file_type].update(new_files)
            if all_image_files:
                new_files = {(f, False) for f in all_image_files if f not in edited_image_files}
                image_dict[file_type].update(new_files)

        return image_dict

    @staticmethod
    def _get_files(
        title_str: str,
        file_type: FileTypes,
        getter_func: Callable[[str, bool], None | Path | list[Path]],
        must_be_edited: bool,
    ) -> list[Path]:
        if file_type == FileTypes.COVER:
            # getter for COVER returns a single Path or None
            cover_file = getter_func(title_str, must_be_edited)
            return [cover_file] if cover_file else []

        # Other getters return a List[Path]
        return getter_func(title_str, must_be_edited)
