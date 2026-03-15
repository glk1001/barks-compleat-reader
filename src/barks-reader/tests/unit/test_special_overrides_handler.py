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
