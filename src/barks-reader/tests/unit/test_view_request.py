"""Which themes the fun view draws from (barks_reader.core.view_request)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_reader.core.view_request import (
    FunImageThemeChoice,
    ImageThemes,
    ImageThemesChange,
    ImageThemesToUse,
)


class TestFunImageThemeChoice:
    def test_all_the_themes_are_in_use_to_begin_with(self) -> None:
        assert FunImageThemeChoice().themes is None

    def test_the_user_s_own_set_starts_as_every_theme(self) -> None:
        choice = FunImageThemeChoice()
        choice.use(ImageThemesToUse.CUSTOM)
        assert choice.themes == set(ImageThemes)

    def test_a_theme_is_taken_out_of_the_set_and_put_back(self) -> None:
        choice = FunImageThemeChoice()
        choice.use(ImageThemesToUse.CUSTOM)

        choice.alter(ImageThemes.FORTIES, ImageThemesChange.DISCARD)
        assert choice.themes == set(ImageThemes) - {ImageThemes.FORTIES}

        choice.alter(ImageThemes.FORTIES, ImageThemesChange.ADD)
        assert choice.themes == set(ImageThemes)

    def test_the_set_is_kept_while_all_the_themes_are_in_use(self) -> None:
        choice = FunImageThemeChoice()
        choice.alter(ImageThemes.FORTIES, ImageThemesChange.DISCARD)
        assert choice.themes is None  # altered, but not in use

        choice.use(ImageThemesToUse.CUSTOM)
        choice.use(ImageThemesToUse.ALL)
        choice.use(ImageThemesToUse.CUSTOM)

        assert choice.themes == set(ImageThemes) - {ImageThemes.FORTIES}

    def test_the_themes_handed_out_are_a_copy(self) -> None:
        """A request keeps the themes it was made with, whatever is ticked after it."""
        choice = FunImageThemeChoice()
        choice.use(ImageThemesToUse.CUSTOM)
        handed_out = choice.themes
        assert handed_out is not None

        choice.alter(ImageThemes.FORTIES, ImageThemesChange.DISCARD)

        assert ImageThemes.FORTIES in handed_out

    def test_an_unknown_choice_is_refused_and_changes_nothing(self) -> None:
        choice = FunImageThemeChoice()
        choice.use(ImageThemesToUse.CUSTOM)

        with pytest.raises(ValueError, match="Unimplemented ImageThemesToUse"):
            choice.use(MagicMock(name="SOME"))

        assert choice.themes == set(ImageThemes)
