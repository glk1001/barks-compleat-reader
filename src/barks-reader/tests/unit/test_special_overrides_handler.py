# ruff: noqa: SLF001

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.special_overrides_handler import SpecialFantaOverrides


class TestIsTitleWhereOverridesAreOptional:
    def test_returns_true_for_special_titles(self) -> None:
        settings = MagicMock()
        handler = SpecialFantaOverrides(settings)
        special_titles = [
            Titles.FIREBUG_THE,
            Titles.LOST_IN_THE_ANDES,
            Titles.VOODOO_HOODOO,
            Titles.GOLDEN_FLEECING_THE,
        ]
        for title in special_titles:
            assert handler.is_title_where_overrides_are_optional(title) is True

    def test_returns_false_for_non_special_title(self) -> None:
        settings = MagicMock()
        handler = SpecialFantaOverrides(settings)
        # Use a title that is not one of the four special ones
        assert handler.is_title_where_overrides_are_optional(Titles(0)) is False


class TestGetSpecialInsetFile:
    def test_use_overrides_returns_original(self) -> None:
        inset = Path("/some/inset.png")
        result = SpecialFantaOverrides._get_special_inset_file(inset, use_overrides=True)
        assert result == inset

    def test_no_overrides_constructs_no_overrides_path(self, tmp_path: Path) -> None:
        # Create the no-overrides file so it gets returned
        original = tmp_path / "inset.png"
        original.touch()
        no_override = tmp_path / "inset-no-overrides.png"
        no_override.touch()

        result = SpecialFantaOverrides._get_special_inset_file(original, use_overrides=False)
        assert result == no_override

    def test_no_overrides_falls_back_when_file_missing(self, tmp_path: Path) -> None:
        original = tmp_path / "inset.png"
        original.touch()
        # Don't create the no-overrides file

        result = SpecialFantaOverrides._get_special_inset_file(original, use_overrides=False)
        assert result == original


class TestGetDescription:
    def test_returns_configured_description(self) -> None:
        settings = MagicMock()
        handler = SpecialFantaOverrides(settings)
        assert handler.get_description(Titles.FIREBUG_THE) == "Use GLK alternate ending"
        assert handler.get_description(Titles.LOST_IN_THE_ANDES) == "Use 'dere' instead of 'theah'"


class TestGetOverridesSetting:
    def test_calls_the_bound_getter(self) -> None:
        settings = MagicMock()
        settings.get_use_glk_firebug_ending.return_value = True
        settings.get_use_harpies_instead_of_larkies.return_value = False
        handler = SpecialFantaOverrides(settings)

        assert handler.get_overrides_setting(Titles.FIREBUG_THE) is True
        assert handler.get_overrides_setting(Titles.GOLDEN_FLEECING_THE) is False
        settings.get_use_glk_firebug_ending.assert_called_once()
        settings.get_use_harpies_instead_of_larkies.assert_called_once()


class TestGetInsetFile:
    def test_uses_non_edited_std_file_and_returns_it_when_overrides_enabled(
        self, tmp_path: Path
    ) -> None:
        std = tmp_path / "inset.png"
        std.touch()

        settings = MagicMock()
        settings.file_paths.get_comic_inset_file.return_value = std
        handler = SpecialFantaOverrides(settings)

        result = handler.get_inset_file(Titles.FIREBUG_THE, use_overrides=True)

        settings.file_paths.get_comic_inset_file.assert_called_once_with(
            Titles.FIREBUG_THE, use_only_edited_if_possible=False
        )
        assert result == std

    def test_returns_no_overrides_variant_when_overrides_disabled(self, tmp_path: Path) -> None:
        std = tmp_path / "inset.png"
        std.touch()
        no_override = tmp_path / "inset-no-overrides.png"
        no_override.touch()

        settings = MagicMock()
        settings.file_paths.get_comic_inset_file.return_value = std
        handler = SpecialFantaOverrides(settings)

        result = handler.get_inset_file(Titles.FIREBUG_THE, use_overrides=False)

        assert result == no_override


class TestGetTitlePageInsetFile:
    def test_uses_edited_std_file_when_overrides_enabled(self, tmp_path: Path) -> None:
        std = tmp_path / "inset.png"
        std.touch()

        settings = MagicMock()
        settings.file_paths.get_comic_inset_file.return_value = std
        handler = SpecialFantaOverrides(settings)

        result = handler.get_title_page_inset_file(Titles.VOODOO_HOODOO, use_overrides=True)

        settings.file_paths.get_comic_inset_file.assert_called_once_with(
            Titles.VOODOO_HOODOO, use_only_edited_if_possible=True
        )
        assert result == std

    def test_falls_back_to_std_when_no_overrides_file_missing(self, tmp_path: Path) -> None:
        std = tmp_path / "inset.png"
        std.touch()
        # Do not create the no-overrides variant.

        settings = MagicMock()
        settings.file_paths.get_comic_inset_file.return_value = std
        handler = SpecialFantaOverrides(settings)

        result = handler.get_title_page_inset_file(Titles.VOODOO_HOODOO, use_overrides=False)

        assert result == std
