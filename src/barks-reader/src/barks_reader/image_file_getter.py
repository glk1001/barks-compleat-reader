from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from barks_reader.reader_file_paths import FileTypes

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_reader.reader_consts_and_types import PanelPath
    from barks_reader.reader_settings import ReaderSettings


class TitleImageFileGetter:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings

    def get_all_title_image_files(self, title_str: str) -> dict[FileTypes, set[tuple[Path, bool]]]:
        image_dict: dict[FileTypes, set[tuple[Path, bool]]] = defaultdict(set)

        for (
            file_type,
            getter_func,
        ) in self._reader_settings.file_paths.FILE_TYPE_FILE_GETTERS.items():
            edited_image_files = self._get_files(
                title_str, file_type, getter_func, use_only_edited_if_possible=True
            )
            all_image_files = self._get_files(
                title_str, file_type, getter_func, use_only_edited_if_possible=False
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
        getter_func: Callable[[str, bool], PanelPath | list[PanelPath] | None],
        use_only_edited_if_possible: bool,
    ) -> list[PanelPath]:
        if file_type == FileTypes.COVER:
            # getter for COVER returns a single Path or None
            cover_file = getter_func(title_str, use_only_edited_if_possible)
            return [cover_file] if cover_file else []

        # Other getters return a List[PanelPath].
        path_list = getter_func(title_str, use_only_edited_if_possible)
        assert path_list is not None
        return path_list
