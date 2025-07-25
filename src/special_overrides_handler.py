import os.path
from pathlib import Path
from typing import Dict, Tuple, Callable

from barks_fantagraphics.barks_titles import Titles
from reader_settings import ReaderSettings


class SpecialFantaOverrides:
    def __init__(self, reader_settings: ReaderSettings):
        self._reader_settings = reader_settings

        self._FANTA_OVERRIDES_SETTINGS: Dict[Titles, Tuple[str, Callable[[], bool]]] = (
            self._get_use_fanta_overrides(reader_settings)
        )

    @staticmethod
    def _get_use_fanta_overrides(
        reader_settings: ReaderSettings,
    ) -> Dict[Titles, Tuple[str, Callable[[], bool]]]:
        return {
            Titles.FIREBUG_THE: (
                "Use GLK alternate ending",
                reader_settings.get_use_glk_firebug_ending,
            ),
            Titles.LOST_IN_THE_ANDES: (
                "Use 'dere' instead of 'theah'",
                reader_settings.get_use_dere_instead_of_theah,
            ),
            Titles.VOODOO_HOODOO: (
                "Use blank eyeballs for Bombie",
                reader_settings.get_use_blank_eyeballs_for_bombie,
            ),
            Titles.GOLDEN_FLEECING_THE: (
                "Use 'Harpies' not 'Larkies'",
                reader_settings.get_use_harpies_instead_of_larkies,
            ),
        }

    def is_title_where_overrides_are_optional(self, title: Titles):
        return title in self._FANTA_OVERRIDES_SETTINGS

    def get_description(self, title: Titles) -> str:
        return self._FANTA_OVERRIDES_SETTINGS[title][0]

    def get_overrides_setting(self, title: Titles) -> bool:
        return self._FANTA_OVERRIDES_SETTINGS[title][1]()

    def get_inset_file(self, title: Titles, use_overrides: bool) -> str:
        std_inset_file = self._reader_settings.file_paths.get_comic_inset_file(
            title, use_edited_only=False
        )

        return self._get_special_inset_file(std_inset_file, use_overrides)

    def get_title_page_inset_file(self, title: Titles, use_overrides: bool) -> str:
        std_inset_file = self._reader_settings.file_paths.get_comic_inset_file(
            title, use_edited_only=True
        )

        return self._get_special_inset_file(std_inset_file, use_overrides)

    @staticmethod
    def _get_special_inset_file(std_inset_file: str, use_overrides: bool) -> str:
        if use_overrides:
            return std_inset_file

        # It's a special title and at this point we don't want
        # to use Fantagraphics overrides.
        std_inset_path = Path(std_inset_file)
        no_overrides_stem = std_inset_path.stem + "-no-overrides"
        no_overrides_inset_file = str(std_inset_path.with_stem(no_overrides_stem))

        return (
            no_overrides_inset_file if os.path.isfile(no_overrides_inset_file) else std_inset_file
        )
