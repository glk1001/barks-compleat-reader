from collections.abc import Callable

from barks_fantagraphics.barks_titles import Titles
from comic_utils.comic_consts import PanelPath

from .reader_consts_and_types import NO_OVERRIDES_SUFFIX
from .reader_settings import ReaderSettings


class SpecialFantaOverrides:
    def __init__(self, reader_settings: ReaderSettings) -> None:
        self._reader_settings = reader_settings

        self._FANTA_OVERRIDES_SETTINGS: dict[Titles, tuple[str, Callable[[], bool]]] = (
            self._get_use_fanta_overrides(reader_settings)
        )

    @staticmethod
    def _get_use_fanta_overrides(
        reader_settings: ReaderSettings,
    ) -> dict[Titles, tuple[str, Callable[[], bool]]]:
        return {
            Titles.FIREBUG_THE: (
                "Use GLK alternate ending",
                reader_settings.get_use_glk_firebug_ending,
            ),
            Titles.LOST_IN_THE_ANDES: (
                "Use 'deah' instead of 'theah'",
                reader_settings.get_use_deah_instead_of_theah,
            ),
            Titles.VOODOO_HOODOO: (
                "Blank-eyed Bombie",
                reader_settings.get_use_blank_eyeballs_for_bombie,
            ),
            Titles.GOLDEN_FLEECING_THE: (
                "Use 'Harpies' not 'Larkies'",
                reader_settings.get_use_harpies_instead_of_larkies,
            ),
        }

    def is_title_where_overrides_are_optional(self, title: Titles) -> bool:
        """Return whether a setting chooses between Fantagraphics' version and an override."""
        return title in self._FANTA_OVERRIDES_SETTINGS

    def get_description(self, title: Titles) -> str:
        """Return the label of the title's override setting."""
        return self._FANTA_OVERRIDES_SETTINGS[title][0]

    def get_overrides_setting(self, title: Titles) -> bool:
        """Return the title's override setting as it is now."""
        return self._FANTA_OVERRIDES_SETTINGS[title][1]()

    def get_inset_file(self, title: Titles, use_overrides: bool) -> PanelPath:
        """Return the title's inset, or its no-overrides copy when overrides are off.

        Args:
            title: One of the titles whose overrides are optional.
            use_overrides: Keep the standard inset, which shows the overrides.

        Returns:
            The ``-no-overrides`` inset when ``use_overrides`` is off and it exists, else
            the standard one.

        """
        std_inset_file = self._reader_settings.file_paths.get_comic_inset_file(
            title, use_only_edited_if_possible=False
        )

        return self._get_special_inset_file(std_inset_file, use_overrides)

    def get_title_page_inset_file(self, title: Titles, use_overrides: bool) -> PanelPath:
        """Return the title page's inset: as `get_inset_file`, preferring the edited inset."""
        std_inset_file = self._reader_settings.file_paths.get_comic_inset_file(
            title, use_only_edited_if_possible=True
        )

        return self._get_special_inset_file(std_inset_file, use_overrides)

    @staticmethod
    def _get_special_inset_file(std_inset_file: PanelPath, use_overrides: bool) -> PanelPath:
        if use_overrides:
            return std_inset_file

        # It's a special title and at this point the user has said don't
        # use Fantagraphics overrides.
        no_overrides_stem = std_inset_file.stem + NO_OVERRIDES_SUFFIX
        # zipfile.Path does not have `with_stem`, so we reconstruct the path manually.
        # This works for both pathlib.Path and zipfile.Path.
        no_overrides_inset_file = std_inset_file.parent / (  # ty: ignore[unsupported-operator]
            no_overrides_stem + std_inset_file.suffix
        )

        return no_overrides_inset_file if no_overrides_inset_file.is_file() else std_inset_file
