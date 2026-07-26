"""Direct unit tests for `ViewPipeline`.

Covers context state, top-view dispatch, fun-image theme expansion,
file-type fallback, and public delegations. Complements
`test_view_pipeline_snapshot.py` (which drives end-to-end snapshot emission)
by exercising the individual private helpers in isolation.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, COVERS_SET, ONE_PAGERS
from barks_fantagraphics.fanta_comics_info import ALL_LISTS
from barks_reader.core import view_pipeline as vp_module
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_file_paths import ALL_TYPES, FileTypes
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ImageThemes, ViewPipeline
from barks_reader.core.view_request import ViewRequest

if TYPE_CHECKING:
    from zipfile import Path as ZipPath

EXPECTED_FIFTIES_YEAR_COUNT = 10


def _make_pipeline() -> ViewPipeline:
    """Create a ViewPipeline with mocked image selection + fake scheduler/colors."""
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")

    image_selector = MagicMock()
    image_selector.get_random_image.return_value = ImageInfo(
        filename=Path("random.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
    )
    image_selector.get_random_search_image.return_value = ImageInfo(
        filename=Path("search.png"), from_title=Titles.BACK_TO_LONG_AGO
    )
    image_selector.get_random_censorship_fix_image.return_value = ImageInfo(
        filename=Path("censor.png")
    )
    image_selector.get_search_image_for_title.return_value = ImageInfo(
        filename=Path("search-for-title.png")
    )

    title_lists = {ALL_LISTS: [MagicMock()]}

    return ViewPipeline(
        reader_settings=reader_settings,
        title_lists=title_lists,  # ty: ignore[invalid-argument-type]
        image_selector=image_selector,
        scheduler=FakeScheduler(),
        colors=ScriptedColorSource(),
    )


def _selector(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's image_selector as a MagicMock for assertion access."""
    return pipeline.__dict__["_image_selector"]


def _title_lists(pipeline: ViewPipeline) -> dict:
    """Return the pipeline's title_lists as an untyped dict for arbitrary key assignment."""
    return pipeline.__dict__["_title_lists"]


def _settings(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's reader_settings as a MagicMock for assertion access."""
    return pipeline.__dict__["_reader_settings"]


# ---------------------------------------------------------------------------
# A. Context getters / setters
# ---------------------------------------------------------------------------


class TestContextAccessors:
    def test_get_view_state_returns_pre_init_by_default(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline.get_view_state() == ViewStates.PRE_INIT

    def test_get_search_screen_image_info_returns_current(self) -> None:
        pipeline = _make_pipeline()
        sentinel = ImageInfo(filename=Path("preset.png"))
        pipeline._search_screen_image_info = sentinel

        assert pipeline.get_search_screen_image_info() is sentinel

    def test_current_request_round_trips_navigation_context(self) -> None:
        """`render` writes the request's nav context; `current_request` reads it back.

        ON_INTRO_NODE uses a fixed top image and the default fun-image titles, so
        the nav fields are stored without needing per-context title lists.
        """
        pipeline = _make_pipeline()
        pipeline.render(
            ViewRequest(
                view_state=ViewStates.ON_INTRO_NODE,
                category="Adventures",
                year_range="1950-1959",
                cs_year_range="CS 1948",
                us_year_range="US 1960",
                tag_group=TagGroups.PRIMARY_CHARACTERS,
                tag=Tags.CLASSICS,
                title_str="Lost in the Andes",
            )
        )

        request = pipeline.current_request()
        assert request.view_state == ViewStates.ON_INTRO_NODE
        assert request.category == "Adventures"
        assert request.year_range == "1950-1959"
        assert request.cs_year_range == "CS 1948"
        assert request.us_year_range == "US 1960"
        assert request.tag_group == TagGroups.PRIMARY_CHARACTERS
        assert request.tag == Tags.CLASSICS
        assert request.title_str == "Lost in the Andes"
        # The one-shot title image file is never carried back out.
        assert request.title_image_file is None


# ---------------------------------------------------------------------------
# B. Top-view setter dispatch
# ---------------------------------------------------------------------------


class TestTopViewSetters:
    def test_set_top_view_image_for_series_picks_from_series_title_list(self) -> None:
        pipeline = _make_pipeline()
        # Need a populated title list for the CS series key.
        from barks_fantagraphics.fanta_comics_info import SERIES_CS  # noqa: PLC0415

        cs_titles = [MagicMock()]
        _title_lists(pipeline)[SERIES_CS] = cs_titles
        pipeline._view_state = ViewStates.ON_CS_NODE

        pipeline._set_top_view_image_for_series()

        _selector(pipeline).get_random_image.assert_called_once()
        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is cs_titles

    def test_set_top_view_image_for_covers_series_picks_from_covers_title_list(self) -> None:
        pipeline = _make_pipeline()
        from barks_fantagraphics.fanta_comics_info import SERIES_COVERS  # noqa: PLC0415

        covers_titles = [MagicMock()]
        _title_lists(pipeline)[SERIES_COVERS] = covers_titles
        pipeline._view_state = ViewStates.ON_COVERS_NODE

        pipeline._set_top_view_image_for_series()

        _selector(pipeline).get_random_image.assert_called_once()
        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is covers_titles

    def test_set_top_view_image_for_category_uses_good_neighbors_when_empty(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_category = ""

        pipeline._set_top_view_image_for_category()

        assert pipeline._top_view_image_info.from_title == Titles.GOOD_NEIGHBORS

    def test_set_top_view_image_for_category_uses_random_when_populated(self) -> None:
        pipeline = _make_pipeline()
        cat_titles = [MagicMock()]
        _title_lists(pipeline)["MyCategory"] = cat_titles
        pipeline._current_category = "MyCategory"

        pipeline._set_top_view_image_for_category()

        _selector(pipeline).get_random_image.assert_called_once()
        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is cat_titles

    def test_set_top_view_image_for_tag_group_uses_good_neighbors_when_none(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_tag_group = None

        pipeline._set_top_view_image_for_tag_group()

        assert pipeline._top_view_image_info.from_title == Titles.GOOD_NEIGHBORS

    def test_set_top_view_image_for_tag_group_uses_random_when_set(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_tag_group = TagGroups.PRIMARY_CHARACTERS

        with patch.object(
            vp_module,
            "BARKS_TAG_GROUPS_TITLES",
            {TagGroups.PRIMARY_CHARACTERS: [Titles.ATTIC_ANTICS]},
        ):
            pipeline._set_top_view_image_for_tag_group()

        _selector(pipeline).get_random_image.assert_called_once()

    def test_set_top_view_image_for_tag_uses_good_neighbors_when_none(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_tag = None

        pipeline._set_top_view_image_for_tag()

        assert pipeline._top_view_image_info.from_title == Titles.GOOD_NEIGHBORS

    def test_set_top_view_image_for_tag_uses_random_when_set(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_tag = Tags.CLASSICS

        with patch.object(vp_module, "BARKS_TAGGED_TITLES", {Tags.CLASSICS: [Titles.ATTIC_ANTICS]}):
            pipeline._set_top_view_image_for_tag()

        _selector(pipeline).get_random_image.assert_called_once()

    def test_set_top_view_image_for_year_range_uses_good_neighbors_when_empty(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_year_range = ""

        pipeline._set_top_view_image_for_year_range()

        assert pipeline._top_view_image_info.from_title == Titles.GOOD_NEIGHBORS

    def test_set_top_view_image_for_year_range_uses_random_when_populated(self) -> None:
        pipeline = _make_pipeline()
        year_titles = [MagicMock()]
        _title_lists(pipeline)["1942-1949"] = year_titles
        pipeline._current_year_range = "1942-1949"

        pipeline._set_top_view_image_for_year_range()

        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is year_titles

    def test_set_top_view_image_for_random_titles_uses_tag_when_set(self) -> None:
        # A 'With <character>' node: the backdrop comes from the character's tag.
        pipeline = _make_pipeline()
        pipeline._current_tag = Tags.CLASSICS
        pipeline._current_year_range = ""

        with patch.object(vp_module, "BARKS_TAGGED_TITLES", {Tags.CLASSICS: [Titles.ATTIC_ANTICS]}):
            pipeline._set_top_view_image_for_random_titles()

        _selector(pipeline).get_random_image.assert_called_once()

    def test_set_top_view_image_for_random_titles_uses_year_range_when_no_tag(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_tag = None
        year_titles = [MagicMock()]
        _title_lists(pipeline)["1942-1949"] = year_titles
        pipeline._current_year_range = "1942-1949"

        pipeline._set_top_view_image_for_random_titles()

        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is year_titles

    def test_set_top_view_image_for_random_titles_falls_back_to_stories(self) -> None:
        # 'Surprise me' carries neither tag nor year range.
        pipeline = _make_pipeline()
        pipeline._current_tag = None
        pipeline._current_year_range = ""
        all_titles = [MagicMock()]
        _title_lists(pipeline)[vp_module.ALL_LISTS] = all_titles

        pipeline._set_top_view_image_for_random_titles()

        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is all_titles

    def test_set_top_view_image_for_cs_year_range_uses_good_neighbors_when_empty(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_cs_year_range = ""

        pipeline._set_top_view_image_for_cs_year_range()

        assert pipeline._top_view_image_info.from_title == Titles.GOOD_NEIGHBORS

    def test_set_top_view_image_for_cs_year_range_routes_through_filtered_key(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_cs_year_range = "CS 1948"
        keyed_titles = [MagicMock()]
        _title_lists(pipeline)["cs-1948-key"] = keyed_titles

        with patch.object(
            vp_module.FilteredTitleLists,
            "get_cs_year_range_key_from_range",
            return_value="cs-1948-key",
        ):
            pipeline._set_top_view_image_for_cs_year_range()

        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is keyed_titles

    def test_set_top_view_image_for_us_year_range_uses_back_to_klondike_when_empty(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_us_year_range = ""

        pipeline._set_top_view_image_for_us_year_range()

        assert pipeline._top_view_image_info.from_title == Titles.BACK_TO_THE_KLONDIKE

    def test_set_top_view_image_for_us_year_range_routes_through_filtered_key(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_us_year_range = "US 1960"
        keyed_titles = [MagicMock()]
        _title_lists(pipeline)["us-1960-key"] = keyed_titles

        with patch.object(
            vp_module.FilteredTitleLists,
            "get_us_year_range_key_from_range",
            return_value="us-1960-key",
        ):
            pipeline._set_top_view_image_for_us_year_range()

        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is keyed_titles

    def test_set_top_view_image_for_appendix_censorship_fixes_delegates(self) -> None:
        pipeline = _make_pipeline()

        pipeline._set_top_view_image_for_appendix_censorship_fixes()

        _selector(pipeline).get_random_censorship_fix_image.assert_called_once()
        assert pipeline._top_view_image_info.filename == Path("censor.png")


# ---------------------------------------------------------------------------
# C. Theme expansion + file-type fallback
# ---------------------------------------------------------------------------


def _fake_fcbi(title_enum: Titles) -> MagicMock:
    """Build a FantaComicBookInfo stub with the comic_book_info.title field set."""
    m = MagicMock()
    m.comic_book_info.title = title_enum
    return m


class TestThemeExpansion:
    def test_get_fun_image_titles_no_themes_returns_all_lists(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = None
        sentinel_list = [MagicMock()]
        _title_lists(pipeline)[ALL_LISTS] = sentinel_list

        titles, file_types = pipeline._get_fun_image_titles()

        assert titles is sentinel_list
        assert file_types == ALL_TYPES

    def test_themed_titles_forties_includes_1942_through_1949(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.FORTIES}
        # Populate title lists for each year in the FORTIES range.
        for year in range(1942, 1950):
            _title_lists(pipeline)[str(year)] = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()

        with (
            patch.object(vp_module, "ENUM_TO_STR_TITLE", {Titles.ATTIC_ANTICS: "Attic Antics"}),
            patch.object(vp_module, "STR_TITLE_TO_ENUM", {"Attic Antics": Titles.ATTIC_ANTICS}),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {Titles.ATTIC_ANTICS: _fake_fcbi(Titles.ATTIC_ANTICS)},
            ),
        ):
            titles, _ = pipeline._get_themed_fun_image_titles()

        assert len(titles) == 1
        assert titles[0].comic_book_info.title == Titles.ATTIC_ANTICS

    def test_themed_titles_fifties_includes_1950_through_1959(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.FIFTIES}
        years_populated: list[int] = []
        for year in range(1950, 1960):
            _title_lists(pipeline)[str(year)] = [_fake_fcbi(Titles.LOST_IN_THE_ANDES)]
            years_populated.append(year)
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()

        lita = Titles.LOST_IN_THE_ANDES
        with (
            patch.object(vp_module, "ENUM_TO_STR_TITLE", {lita: "Lost in the Andes"}),
            patch.object(vp_module, "STR_TITLE_TO_ENUM", {"Lost in the Andes": lita}),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {lita: _fake_fcbi(lita)},
            ),
        ):
            titles, _ = pipeline._get_themed_fun_image_titles()

        assert len(years_populated) == EXPECTED_FIFTIES_YEAR_COUNT
        assert len(titles) == 1

    def test_themed_titles_sixties_includes_1960_and_1961(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.SIXTIES}
        _title_lists(pipeline)["1960"] = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        _title_lists(pipeline)["1961"] = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()

        with (
            patch.object(vp_module, "ENUM_TO_STR_TITLE", {Titles.ATTIC_ANTICS: "Attic Antics"}),
            patch.object(vp_module, "STR_TITLE_TO_ENUM", {"Attic Antics": Titles.ATTIC_ANTICS}),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {Titles.ATTIC_ANTICS: _fake_fcbi(Titles.ATTIC_ANTICS)},
            ),
        ):
            titles, _ = pipeline._get_themed_fun_image_titles()

        assert len(titles) == 1

    def test_themed_titles_classics_includes_tag(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.CLASSICS}
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()

        with (
            patch.object(
                vp_module, "BARKS_TAGGED_TITLES", {Tags.CLASSICS: [Titles.LOST_IN_THE_ANDES]}
            ),
            patch.object(
                vp_module,
                "ENUM_TO_STR_TITLE",
                {Titles.LOST_IN_THE_ANDES: "Lost in the Andes"},
            ),
            patch.object(
                vp_module,
                "STR_TITLE_TO_ENUM",
                {"Lost in the Andes": Titles.LOST_IN_THE_ANDES},
            ),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {Titles.LOST_IN_THE_ANDES: _fake_fcbi(Titles.LOST_IN_THE_ANDES)},
            ),
        ):
            titles, _ = pipeline._get_themed_fun_image_titles()

        assert len(titles) == 1
        assert titles[0].comic_book_info.title == Titles.LOST_IN_THE_ANDES

    def test_themed_titles_multi_theme_unions_results(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.FORTIES, ImageThemes.SIXTIES}
        _title_lists(pipeline)["1942"] = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        for year in range(1943, 1950):
            _title_lists(pipeline)[str(year)] = []
        _title_lists(pipeline)["1960"] = [_fake_fcbi(Titles.LOST_IN_THE_ANDES)]
        _title_lists(pipeline)["1961"] = []
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()

        with (
            patch.object(
                vp_module,
                "ENUM_TO_STR_TITLE",
                {
                    Titles.ATTIC_ANTICS: "Attic Antics",
                    Titles.LOST_IN_THE_ANDES: "Lost in the Andes",
                },
            ),
            patch.object(
                vp_module,
                "STR_TITLE_TO_ENUM",
                {
                    "Attic Antics": Titles.ATTIC_ANTICS,
                    "Lost in the Andes": Titles.LOST_IN_THE_ANDES,
                },
            ),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {
                    Titles.ATTIC_ANTICS: _fake_fcbi(Titles.ATTIC_ANTICS),
                    Titles.LOST_IN_THE_ANDES: _fake_fcbi(Titles.LOST_IN_THE_ANDES),
                },
            ),
        ):
            titles, _ = pipeline._get_themed_fun_image_titles()

        title_enums = {t.comic_book_info.title for t in titles}
        assert title_enums == {Titles.ATTIC_ANTICS, Titles.LOST_IN_THE_ANDES}

    def test_get_file_types_to_use_none_themes_returns_all_types(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = None

        assert pipeline._get_file_types_to_use() == ALL_TYPES

    def test_get_file_types_to_use_unknown_theme_falls_back_to_all_minus_nontitle(self) -> None:
        pipeline = _make_pipeline()
        # CLASSICS is in IMAGE_THEMES_WITH_NO_FILES — not in IMAGE_THEME_TO_FILE_TYPE_MAP.
        pipeline._fun_image_themes = {ImageThemes.CLASSICS}

        result = pipeline._get_file_types_to_use()

        expected = ALL_TYPES.copy()
        expected.discard(FileTypes.NONTITLE)
        assert result == expected

    def test_get_file_types_to_use_mapped_theme_returns_matching_file_type(self) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.SPLASHES}

        result = pipeline._get_file_types_to_use()

        assert result == {FileTypes.SPLASH}


# ---------------------------------------------------------------------------
# D. Public delegations + small branches
# ---------------------------------------------------------------------------


class TestPublicDelegations:
    def test_set_bottom_view_fun_image_stores_image_directly(self) -> None:
        pipeline = _make_pipeline()
        info = ImageInfo(filename=Path("override.png"), from_title=Titles.ATTIC_ANTICS)

        pipeline.set_bottom_view_fun_image(info)

        assert pipeline._bottom_view_fun_image_info is info

    def test_set_search_screen_image_for_title_delegates_to_image_selector(self) -> None:
        pipeline = _make_pipeline()

        pipeline.set_search_screen_image_for_title(Titles.LOST_IN_THE_ANDES)

        _selector(pipeline).get_search_image_for_title.assert_called_once_with(
            Titles.LOST_IN_THE_ANDES
        )
        assert pipeline._search_screen_image_info.filename == Path("search-for-title.png")

    def test_get_fanta_title_list_filters_unknown_titles(self) -> None:
        pipeline = _make_pipeline()
        known = _fake_fcbi(Titles.ATTIC_ANTICS)
        unknown = Titles.LOST_IN_THE_ANDES

        from barks_fantagraphics import fanta_comics_info as fci_module  # noqa: PLC0415

        def fake_get_fanta_info(title: Titles) -> MagicMock | None:
            return known if title == Titles.ATTIC_ANTICS else None

        with patch.object(fci_module, "get_fanta_info", side_effect=fake_get_fanta_info):
            result = pipeline._get_fanta_title_list([Titles.ATTIC_ANTICS, unknown])

        # Only the known title survives the None filter.
        assert result == [known]

    def test_get_next_fun_view_image_info_uses_censorship_fixes_branch(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE
        tagged = _fake_fcbi(Titles.ATTIC_ANTICS)

        with (
            patch.object(
                vp_module,
                "BARKS_TAGGED_TITLES",
                {Tags.CENSORED_STORIES_BUT_FIXED: [Titles.ATTIC_ANTICS]},
            ),
            patch.object(
                vp_module,
                "ALL_FANTA_COMIC_BOOK_INFO",
                {Titles.ATTIC_ANTICS: tagged},
            ),
        ):
            pipeline._get_next_fun_view_image_info()

        # get_random_image was called with use_adaptive_fit_mode=True for the censorship branch.
        _selector(pipeline).get_random_image.assert_called_once()
        _args, kwargs = _selector(pipeline).get_random_image.call_args
        assert kwargs.get("use_adaptive_fit_mode") is True

    def test_random_titles_fun_image_uses_tag_for_character_node(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_RANDOM_TITLES_NODE
        pipeline._current_tag = Tags.GLADSTONE_GANDER
        pipeline._current_year_range = ""

        with patch.object(
            vp_module, "BARKS_TAGGED_TITLES", {Tags.GLADSTONE_GANDER: [Titles.ATTIC_ANTICS]}
        ):
            pipeline._get_next_fun_view_image_info()

        # The character node's tagged title list feeds the fun image, with NONTITLE
        # excluded so an unrelated nontitle image can't leak in, and adaptive fit.
        _selector(pipeline).get_random_image.assert_called_once()
        _args, kwargs = _selector(pipeline).get_random_image.call_args
        assert kwargs.get("use_adaptive_fit_mode") is True
        assert kwargs.get("file_types") == ALL_TYPES - {FileTypes.NONTITLE}

    def test_random_titles_fun_image_uses_year_range_for_decade_node(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_RANDOM_TITLES_NODE
        pipeline._current_tag = None
        pipeline._current_year_range = "1950-1959"
        decade_list = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        _title_lists(pipeline)["1950-1959"] = decade_list

        pipeline._get_next_fun_view_image_info()

        # The decade node draws from its year-range title list.
        _selector(pipeline).get_random_image.assert_called_once()
        args, kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is decade_list
        assert kwargs.get("file_types") == ALL_TYPES - {FileTypes.NONTITLE}

    def test_random_titles_fun_image_surprise_me_falls_through_to_generic_pool(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_RANDOM_TITLES_NODE
        pipeline._current_tag = None
        pipeline._current_year_range = ""
        # 'Surprise me' carries no theme, so the generic cached pool is used.
        generic_pool = [_fake_fcbi(Titles.LOST_IN_THE_ANDES)]
        pipeline.__dict__["_cached_fun_titles"] = (generic_pool, ALL_TYPES)

        pipeline._get_next_fun_view_image_info()

        _selector(pipeline).get_random_image.assert_called_once()
        args, _kwargs = _selector(pipeline).get_random_image.call_args
        assert args[0] is generic_pool

    def test_set_next_bottom_view_title_image_no_title_short_circuits(self) -> None:
        pipeline = _make_pipeline()
        pipeline._current_bottom_view_title = ""
        # Empty filename forces the else-branch; empty title then short-circuits.
        pipeline._bottom_view_title_image_info = ImageInfo()

        pipeline._set_next_bottom_view_title_image()

        # No image was picked — image_selector was never consulted.
        _selector(pipeline).get_random_image_for_title.assert_not_called()
        assert pipeline._bottom_view_title_image_info.filename is None

    def test_set_next_bottom_view_title_image_one_pager_uses_collection_image(self) -> None:
        pipeline = _make_pipeline()
        one_pager_title_str = BARKS_TITLE_INFO[ONE_PAGERS[0]].get_title_str()
        pipeline._current_bottom_view_title = one_pager_title_str
        # An explicitly provided file should be overridden for one-pagers.
        pipeline._bottom_view_title_image_info = ImageInfo(filename=Path("individual.png"))
        collection_image = Path("all-one-pagers.png")
        _selector(pipeline).get_random_image_for_title.return_value = collection_image

        pipeline._set_next_bottom_view_title_image()

        # A random image is picked from the synthetic "All One-Pagers" collection's
        # title-view types - not the individual gag image, and not the Insets directory.
        _selector(pipeline).get_random_image_for_title.assert_called_once_with(
            ENUM_TO_STR_TITLE[Titles.ALL_ONE_PAGERS],
            vp_module._TITLE_VIEW_IMAGE_TYPES,
            use_only_edited_if_possible=True,
        )
        assert pipeline._bottom_view_title_image_info.filename == collection_image

    def test_one_pager_title_render_rerolls_collection_image_each_time(self) -> None:
        # Every one-pager title node change must re-roll a fresh random "All
        # One-Pagers" image (overriding any cached/provided file), so the large
        # background image refreshes on each selection.
        pipeline = _make_pipeline()
        picks = iter([Path("p1.png"), Path("p2.png"), Path("p3.png")])
        _selector(pipeline).get_random_image_for_title.side_effect = lambda *_a, **_k: next(picks)

        title_a = BARKS_TITLE_INFO[ONE_PAGERS[0]].get_title_str()
        title_b = BARKS_TITLE_INFO[ONE_PAGERS[1]].get_title_str()

        shown: list[Path | ZipPath | None] = []
        for title_str in (title_a, title_b, title_a):
            snapshot = pipeline.render(
                ViewRequest(view_state=ViewStates.ON_TITLE_NODE, title_str=title_str)
            )
            image_info = snapshot.title_view.image_info
            assert image_info is not None
            shown.append(image_info.filename)

        # A fresh image is picked on each render - even re-selecting the same one-pager.
        assert shown == [Path("p1.png"), Path("p2.png"), Path("p3.png")]
        assert _selector(pipeline).get_random_image_for_title.call_count == len(shown)
        assert all(
            call.args[0] == ENUM_TO_STR_TITLE[Titles.ALL_ONE_PAGERS]
            for call in _selector(pipeline).get_random_image_for_title.call_args_list
        )

    def test_set_next_bottom_view_title_image_non_one_pager_uses_random(self) -> None:
        pipeline = _make_pipeline()
        # A real title, so `STR_TITLE_TO_ENUM` resolves it and the one-pager and
        # cover guards are both exercised against a known non-member.
        pipeline._current_bottom_view_title = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]
        pipeline._bottom_view_title_image_info = ImageInfo()
        _selector(pipeline).get_random_image_for_title.return_value = Path("random-title.png")

        pipeline._set_next_bottom_view_title_image()

        # The title's own image — not the one-pager or cover collection's.
        _selector(pipeline).get_random_image_for_title.assert_called_once_with(
            ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES],
            vp_module._TITLE_VIEW_IMAGE_TYPES,
            use_only_edited_if_possible=True,
        )
        assert pipeline._bottom_view_title_image_info.filename == Path("random-title.png")


# ---------------------------------------------------------------------------
# E. The cover / one-pager collection redirects
# ---------------------------------------------------------------------------


class TestCollectionTitleRedirects:
    """One-pagers and covers draw their large image from their collection.

    Both guards are `title is not None and (title in <SET> or is_<x>_collection(title))`,
    so three cases are needed to see the whole expression: a member of the set,
    the synthetic collection title itself, and a title that is neither.
    """

    def _redirect_target(self, pipeline: ViewPipeline, title_str: str) -> str:
        pipeline._current_bottom_view_title = title_str
        # A provided file must lose to a collection redirect, so set one.
        pipeline._bottom_view_title_image_info = ImageInfo(filename=Path("provided.png"))
        _selector(pipeline).get_random_image_for_title.return_value = Path("picked.png")

        pipeline._set_next_bottom_view_title_image()

        picker = _selector(pipeline).get_random_image_for_title
        picker.assert_called_once()
        assert pipeline._bottom_view_title_image_info.filename == Path("picked.png")
        assert picker.call_args.args[1:] == (vp_module._TITLE_VIEW_IMAGE_TYPES,)
        assert picker.call_args.kwargs == {"use_only_edited_if_possible": True}
        return picker.call_args.args[0]

    def test_a_cover_redirects_to_the_all_covers_collection(self) -> None:
        pipeline = _make_pipeline()
        cover_str = ENUM_TO_STR_TITLE[next(iter(sorted(COVERS_SET, key=lambda t: t.name)))]

        assert self._redirect_target(pipeline, cover_str) == ENUM_TO_STR_TITLE[Titles.ALL_COVERS]

    def test_the_covers_collection_itself_redirects_to_itself(self) -> None:
        """`ALL_COVERS` is not *in* `COVERS_SET`, so only `is_covers_collection` sees it."""
        pipeline = _make_pipeline()
        all_covers = ENUM_TO_STR_TITLE[Titles.ALL_COVERS]

        assert self._redirect_target(pipeline, all_covers) == all_covers

    def test_the_one_pagers_collection_itself_redirects_to_itself(self) -> None:
        """Likewise `ALL_ONE_PAGERS` is not in `ONE_PAGERS`."""
        pipeline = _make_pipeline()
        all_one_pagers = ENUM_TO_STR_TITLE[Titles.ALL_ONE_PAGERS]

        assert self._redirect_target(pipeline, all_one_pagers) == all_one_pagers

    def test_an_ordinary_title_keeps_a_provided_image(self) -> None:
        """Neither guard fires, so the explicitly provided file survives."""
        pipeline = _make_pipeline()
        pipeline._current_bottom_view_title = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]
        pipeline._bottom_view_title_image_info = ImageInfo(filename=Path("provided.png"))

        pipeline._set_next_bottom_view_title_image()

        _selector(pipeline).get_random_image_for_title.assert_not_called()
        assert pipeline._bottom_view_title_image_info.filename == Path("provided.png")


# ---------------------------------------------------------------------------
# F. The search-screen image and its anti-repeat reroll
# ---------------------------------------------------------------------------


def _search_pipeline(picks: list[str]) -> ViewPipeline:
    """Create a pipeline in a search state whose search images follow *picks* in order."""
    pipeline = _make_pipeline()
    sequence = iter(picks)
    _selector(pipeline).get_random_search_image.side_effect = lambda: ImageInfo(
        filename=Path(next(sequence))
    )
    pipeline._view_state = ViewStates.ON_TITLE_SEARCH_NODE
    return pipeline


class TestSearchScreenImage:
    """The search screen must not show the same artwork as the top view.

    Both draw from the same small pool, so `_set_next_search_screen_image`
    rerolls up to five times before giving up. The top view is chosen first and
    consumes the first pick.
    """

    def test_a_different_first_pick_is_used_straight_away(self) -> None:
        pipeline = _search_pipeline(["top.png", "other.png"])
        pipeline._set_next_top_view_image()

        pipeline._set_next_search_screen_image()

        assert pipeline.get_search_screen_image_info().filename == Path("other.png")
        assert _selector(pipeline).get_random_search_image.call_count == 2  # noqa: PLR2004

    def test_a_pick_matching_the_top_view_is_rerolled(self) -> None:
        pipeline = _search_pipeline(["dup.png", "dup.png", "fresh.png"])
        pipeline._set_next_top_view_image()

        pipeline._set_next_search_screen_image()

        assert pipeline.get_search_screen_image_info().filename == Path("fresh.png")
        assert _selector(pipeline).get_random_search_image.call_count == 3  # noqa: PLR2004

    def test_the_reroll_gives_up_after_five_attempts(self) -> None:
        pipeline = _search_pipeline(["dup.png"] * 20)
        pipeline._set_next_top_view_image()

        pipeline._set_next_search_screen_image()

        # One pick for the top view, one initial pick, then five rerolls.
        assert _selector(pipeline).get_random_search_image.call_count == 7  # noqa: PLR2004
        assert pipeline.get_search_screen_image_info().filename == Path("dup.png")

    def test_a_non_search_state_leaves_the_search_image_alone(self) -> None:
        pipeline = _make_pipeline()
        sentinel = ImageInfo(filename=Path("kept.png"))
        pipeline._search_screen_image_info = sentinel
        pipeline._view_state = ViewStates.ON_INTRO_NODE

        pipeline._set_next_search_screen_image()

        assert pipeline.get_search_screen_image_info() is sentinel
        _selector(pipeline).get_random_search_image.assert_not_called()


# ---------------------------------------------------------------------------
# G. Fun-image selection arguments
# ---------------------------------------------------------------------------


class TestFunImageSelectionArguments:
    """The fun image's *arguments* are the whole behaviour — the return is a mock."""

    def test_censorship_fixes_draws_from_the_fixed_stories_tag(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE
        fanta = _fake_fcbi(Titles.ATTIC_ANTICS)

        from barks_fantagraphics import fanta_comics_info as fci_module  # noqa: PLC0415

        with (
            patch.object(
                vp_module,
                "BARKS_TAGGED_TITLES",
                {Tags.CENSORED_STORIES_BUT_FIXED: [Titles.ATTIC_ANTICS]},
            ),
            patch.object(fci_module, "get_fanta_info", return_value=fanta),
        ):
            pipeline._get_next_fun_view_image_info()

        # No `file_types` here: the censorship pool is already narrow.
        _selector(pipeline).get_random_image.assert_called_once_with(
            [fanta], use_adaptive_fit_mode=True
        )

    def test_the_generic_pool_passes_its_cached_titles_and_file_types(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_INTRO_NODE
        pool = [_fake_fcbi(Titles.LOST_IN_THE_ANDES)]
        pipeline.__dict__["_cached_fun_titles"] = (pool, {FileTypes.SPLASH})

        pipeline._get_next_fun_view_image_info()

        _selector(pipeline).get_random_image.assert_called_once_with(
            pool,
            file_types={FileTypes.SPLASH},
            use_adaptive_fit_mode=True,
        )

    def test_random_titles_tag_branch_passes_the_tagged_title_list(self) -> None:
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_RANDOM_TITLES_NODE
        pipeline._current_tag = Tags.GLADSTONE_GANDER
        fanta = _fake_fcbi(Titles.ATTIC_ANTICS)

        from barks_fantagraphics import fanta_comics_info as fci_module  # noqa: PLC0415

        with (
            patch.object(
                vp_module, "BARKS_TAGGED_TITLES", {Tags.GLADSTONE_GANDER: [Titles.ATTIC_ANTICS]}
            ),
            patch.object(fci_module, "get_fanta_info", return_value=fanta),
        ):
            pipeline._get_next_fun_view_image_info()

        _selector(pipeline).get_random_image.assert_called_once_with(
            [fanta],
            file_types=ALL_TYPES - {FileTypes.NONTITLE},
            use_adaptive_fit_mode=True,
        )

    def test_random_titles_category_branch_passes_the_category_title_list(self) -> None:
        """'From favourites' carries a category, and no tag or year range."""
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_RANDOM_TITLES_NODE
        pipeline._current_tag = None
        pipeline._current_year_range = ""
        pipeline._current_category = "Favourites"
        cat_list = [_fake_fcbi(Titles.ATTIC_ANTICS)]
        _title_lists(pipeline)["Favourites"] = cat_list

        pipeline._get_next_fun_view_image_info()

        _selector(pipeline).get_random_image.assert_called_once_with(
            cat_list,
            file_types=ALL_TYPES - {FileTypes.NONTITLE},
            use_adaptive_fit_mode=True,
        )


# ---------------------------------------------------------------------------
# H. Decade-theme year boundaries
# ---------------------------------------------------------------------------


def _named_fcbi(marker: str) -> MagicMock:
    """Build a `FantaComicBookInfo` stub whose `title` is a plain, printable marker."""
    m = MagicMock()
    m.comic_book_info.title = marker
    return m


class TestDecadeThemeBoundaries:
    @pytest.mark.parametrize(
        ("theme", "expected_range"),
        [
            (ImageThemes.FORTIES, (1942, 1949)),
            (ImageThemes.FIFTIES, (1950, 1959)),
            # The sixties bucket runs past the last year with titles (1971).
            (ImageThemes.SIXTIES, (1960, 1980)),
        ],
    )
    def test_each_decade_theme_spans_its_exact_years(
        self, theme: ImageThemes, expected_range: tuple[int, int]
    ) -> None:
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {theme}
        _settings(pipeline).file_paths.get_file_type_titles.return_value = set()
        recorded: list[tuple[int, int]] = []

        with patch.object(
            ViewPipeline,
            "_update_titles",
            side_effect=lambda _titles, year_range: recorded.append(year_range),
        ):
            pipeline._get_themed_fun_image_titles()

        assert recorded == [expected_range]

    def test_update_titles_includes_both_endpoints_and_nothing_outside(self) -> None:
        pipeline = _make_pipeline()
        for year in range(1940, 1953):
            _title_lists(pipeline)[str(year)] = [_named_fcbi(f"t{year}")]
        collected: set[str] = set()

        pipeline._update_titles(collected, (1942, 1949))  # ty: ignore[invalid-argument-type]

        assert collected == {f"t{year}" for year in range(1942, 1950)}

    def test_update_titles_tolerates_years_with_no_title_list(self) -> None:
        """Decade buckets run past the years that have lists; missing years are skipped."""
        pipeline = _make_pipeline()
        _title_lists(pipeline)["1971"] = [_named_fcbi("t1971")]
        collected: set[str] = set()

        pipeline._update_titles(collected, (1970, 1980))  # ty: ignore[invalid-argument-type]

        assert collected == {"t1971"}

    def test_file_type_titles_are_filtered_by_the_accumulated_theme_titles(self) -> None:
        """The enum title set is projected to strings before it reaches the resolver."""
        pipeline = _make_pipeline()
        pipeline._fun_image_themes = {ImageThemes.CLASSICS, ImageThemes.SPLASHES}
        _settings(pipeline).file_paths.get_file_type_titles.return_value = []

        with patch.object(
            vp_module, "BARKS_TAGGED_TITLES", {Tags.CLASSICS: [Titles.LOST_IN_THE_ANDES]}
        ):
            _titles, file_types = pipeline._get_themed_fun_image_titles()

        # SPLASHES maps to a file type; CLASSICS only seeds the title set.
        assert file_types == {FileTypes.SPLASH}
        _settings(pipeline).file_paths.get_file_type_titles.assert_called_once_with(
            FileTypes.SPLASH, {ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]}
        )

    def test_an_unmapped_theme_is_skipped_not_a_stop(self) -> None:
        """A theme with no file type must not hide the mapped themes after it."""
        pipeline = _make_pipeline()
        # A list, not a set: the skip is only observable when an unmapped theme is
        # iterated before a mapped one, and set order over enum members is not
        # stable across runs.
        pipeline._fun_image_themes = [  # ty: ignore[invalid-assignment]
            ImageThemes.CLASSICS,
            ImageThemes.SPLASHES,
        ]

        assert pipeline._get_file_types_to_use() == {FileTypes.SPLASH}
