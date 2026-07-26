"""Whole-table verification of `ViewPipeline`'s top-view image dispatch.

`_set_next_top_view_image` is an ordered list of `(predicate, handler)` pairs
that must cover every `ViewStates` member. Testing one handler at a time cannot
see an inverted predicate: with `==` flipped to `!=` an earlier entry matches
instead and still produces *an* image, so a per-handler test passes either way.

This module pins the mapping as a whole. Each image source is stubbed to a
distinguishable filename (`inset:<TITLE>`, `random:<list marker>`, `search`,
`censor`, `history`), so driving every state through the dispatch and comparing
the resulting `ImageInfo` against a literal table catches a predicate that
routes a state to the wrong handler, a fixed title that changed, and any state
that fell off the table entirely.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import (
    ALL_LISTS,
    SERIES_COVERS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_ONE_PAGERS,
    SERIES_USA,
    SERIES_USS,
)
from barks_reader.core import view_pipeline as vp_module
from barks_reader.core.filtered_title_lists import CS_YEARS_KEY_PREFIX, US_YEARS_KEY_PREFIX
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline

if TYPE_CHECKING:
    from collections.abc import Iterator

# The navigation context every case is driven with. States ignore the fields
# they don't use, so one fully-populated context serves the whole table.
_CATEGORY = "MyCategory"
_YEAR_RANGE = "1942-1949"
_CS_YEAR_RANGE = "CS 1948"
_US_YEAR_RANGE = "US 1960"
_TAG = Tags.CLASSICS
_TAG_GROUP = TagGroups.PRIMARY_CHARACTERS
# One title per tag lookup, so the two fanta lists stay distinguishable.
_TAG_TITLE = Titles.ATTIC_ANTICS
_TAG_GROUP_TITLE = Titles.BACK_TO_LONG_AGO

_SERIES_KEY_FOR_STATE: dict[ViewStates, str] = {
    ViewStates.ON_CS_NODE: SERIES_CS,
    ViewStates.ON_DD_NODE: SERIES_DDA,
    ViewStates.ON_US_NODE: SERIES_USA,
    ViewStates.ON_DDS_NODE: SERIES_DDS,
    ViewStates.ON_USS_NODE: SERIES_USS,
    ViewStates.ON_GG_NODE: SERIES_GG,
    ViewStates.ON_MISC_NODE: SERIES_MISC,
    ViewStates.ON_ONE_PAGERS_NODE: SERIES_ONE_PAGERS,
    ViewStates.ON_COVERS_NODE: SERIES_COVERS,
}


def _fixed(title: Titles) -> ImageInfo:
    """Build the `ImageInfo` a fixed-inset handler must produce for *title*."""
    return ImageInfo(Path(f"inset:{title.name}"), title, FIT_MODE_COVER)


def _random_from(marker: str) -> ImageInfo:
    """Build the `ImageInfo` a random-image handler must produce for a marked list."""
    return ImageInfo(Path(f"random:{marker}"), None, FIT_MODE_COVER)


# state -> the exact ImageInfo the top view must end up with.
_EXPECTED_TOP_VIEW_IMAGE: dict[ViewStates, ImageInfo] = {
    # Fixed insets.
    ViewStates.PRE_INIT: _fixed(Titles.COLD_BARGAIN_A),
    ViewStates.INITIAL: _fixed(Titles.COLD_BARGAIN_A),
    ViewStates.ON_INTRO_NODE: _fixed(Titles.ADVENTURE_DOWN_UNDER),
    ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE: _fixed(Titles.ADVENTURE_DOWN_UNDER),
    ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE: _fixed(Titles.ADVENTURE_DOWN_UNDER),
    ViewStates.ON_APPENDIX_NODE: _fixed(Titles.FABULOUS_PHILOSOPHERS_STONE_THE),
    ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE: _fixed(
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE
    ),
    ViewStates.ON_APPENDIX_RICH_TOMMASO_ON_COLORING_BARKS_NODE: _fixed(
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE
    ),
    ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE: _fixed(
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE
    ),
    ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE: _fixed(
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE
    ),
    ViewStates.ON_APPENDIX_STATISTICS_NODE: _fixed(Titles.FABULOUS_PHILOSOPHERS_STONE_THE),
    ViewStates.ON_INDEX_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_MAIN_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_SPEECH_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_SPEECH_WORDS_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_NAMES_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_LOCATIONS_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    ViewStates.ON_INDEX_WIKI_NODE: _fixed(Titles.TRUANT_OFFICER_DONALD),
    # Per-series random images.
    ViewStates.ON_CS_NODE: _random_from(f"list:{SERIES_CS}"),
    ViewStates.ON_DD_NODE: _random_from(f"list:{SERIES_DDA}"),
    ViewStates.ON_US_NODE: _random_from(f"list:{SERIES_USA}"),
    ViewStates.ON_DDS_NODE: _random_from(f"list:{SERIES_DDS}"),
    ViewStates.ON_USS_NODE: _random_from(f"list:{SERIES_USS}"),
    ViewStates.ON_GG_NODE: _random_from(f"list:{SERIES_GG}"),
    ViewStates.ON_MISC_NODE: _random_from(f"list:{SERIES_MISC}"),
    ViewStates.ON_ONE_PAGERS_NODE: _random_from(f"list:{SERIES_ONE_PAGERS}"),
    ViewStates.ON_COVERS_NODE: _random_from(f"list:{SERIES_COVERS}"),
    # The whole-collection ("stories") pool.
    ViewStates.ON_THE_STORIES_NODE: _random_from(f"list:{ALL_LISTS}"),
    ViewStates.ON_CHRONO_BY_YEAR_NODE: _random_from(f"list:{ALL_LISTS}"),
    ViewStates.ON_SERIES_NODE: _random_from(f"list:{ALL_LISTS}"),
    ViewStates.ON_CATEGORIES_NODE: _random_from(f"list:{ALL_LISTS}"),
    ViewStates.ON_TITLE_NODE: _random_from(f"list:{ALL_LISTS}"),
    ViewStates.ON_CHOOSE_FOR_ME_NODE: _random_from(f"list:{ALL_LISTS}"),
    # Context-driven pools.
    ViewStates.ON_YEAR_RANGE_NODE: _random_from(f"list:{_YEAR_RANGE}"),
    ViewStates.ON_CS_YEAR_RANGE_NODE: _random_from(f"list:{CS_YEARS_KEY_PREFIX}{_CS_YEAR_RANGE}"),
    ViewStates.ON_US_YEAR_RANGE_NODE: _random_from(f"list:{US_YEARS_KEY_PREFIX}{_US_YEAR_RANGE}"),
    ViewStates.ON_CATEGORY_NODE: _random_from(f"list:{_CATEGORY}"),
    ViewStates.ON_TAG_NODE: _random_from(f"fanta:{_TAG_TITLE.name}"),
    ViewStates.ON_TAG_GROUP_NODE: _random_from(f"fanta:{_TAG_GROUP_TITLE.name}"),
    # 'Choose for me' children: a tag beats a year range beats a category.
    ViewStates.ON_RANDOM_TITLES_NODE: _random_from(f"fanta:{_TAG_TITLE.name}"),
    # Dedicated selector calls.
    ViewStates.ON_SEARCH_NODE: ImageInfo(Path("search")),
    ViewStates.ON_TITLE_SEARCH_NODE: ImageInfo(Path("search")),
    ViewStates.ON_TAG_SEARCH_NODE: ImageInfo(Path("search")),
    ViewStates.ON_WORD_SEARCH_NODE: ImageInfo(Path("search")),
    ViewStates.ON_HISTORY_NODE: ImageInfo(Path("history")),
    ViewStates.ON_READING_NODE: ImageInfo(Path("history")),
    ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE: ImageInfo(Path("censor")),
}


def _selector(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's image_selector as a MagicMock for assertion access."""
    return pipeline.__dict__["_image_selector"]


def _scheduler(pipeline: ViewPipeline) -> FakeScheduler:
    """Return the pipeline's scheduler as the concrete fake, for interval assertions."""
    return pipeline.__dict__["_scheduler"]


def _make_dispatch_pipeline() -> ViewPipeline:
    """Create a pipeline whose every top-view image source is separately identifiable."""
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.side_effect = lambda title: Path(
        f"inset:{title.name}"
    )

    image_selector = MagicMock()
    # The marker is carried by the list's first element, so the resulting
    # filename says which title list the handler reached for.
    image_selector.get_random_image.side_effect = lambda title_list, **_kwargs: ImageInfo(
        Path(f"random:{title_list[0]}")
    )
    image_selector.get_random_search_image.return_value = ImageInfo(Path("search"))
    image_selector.get_random_censorship_fix_image.return_value = ImageInfo(Path("censor"))
    image_selector.get_random_reading_history_image.return_value = ImageInfo(Path("history"))

    title_lists: dict[str, list[str]] = {ALL_LISTS: [f"list:{ALL_LISTS}"]}
    for key in _SERIES_KEY_FOR_STATE.values():
        title_lists[key] = [f"list:{key}"]
    for key in (
        _CATEGORY,
        _YEAR_RANGE,
        f"{CS_YEARS_KEY_PREFIX}{_CS_YEAR_RANGE}",
        f"{US_YEARS_KEY_PREFIX}{_US_YEAR_RANGE}",
    ):
        title_lists[key] = [f"list:{key}"]

    pipeline = ViewPipeline(
        reader_settings=reader_settings,
        title_lists=title_lists,  # ty: ignore[invalid-argument-type]
        image_selector=image_selector,
        scheduler=FakeScheduler(),
        colors=ScriptedColorSource(),
    )
    pipeline._current_category = _CATEGORY
    pipeline._current_year_range = _YEAR_RANGE
    pipeline._current_cs_year_range = _CS_YEAR_RANGE
    pipeline._current_us_year_range = _US_YEAR_RANGE
    pipeline._current_tag = _TAG
    pipeline._current_tag_group = _TAG_GROUP
    return pipeline


@pytest.fixture
def dispatch_pipeline() -> Iterator[ViewPipeline]:
    """Yield a dispatch pipeline with both tag lookup tables stubbed to one title each."""
    from barks_fantagraphics import fanta_comics_info as fci_module  # noqa: PLC0415

    with (
        patch.object(vp_module, "BARKS_TAGGED_TITLES", {_TAG: [_TAG_TITLE]}),
        patch.object(vp_module, "BARKS_TAG_GROUPS_TITLES", {_TAG_GROUP: [_TAG_GROUP_TITLE]}),
        patch.object(
            fci_module,
            "get_fanta_info",
            side_effect=lambda title: f"fanta:{title.name}",
        ),
    ):
        yield _make_dispatch_pipeline()


class TestTopViewDispatchTable:
    def test_the_table_covers_every_view_state(self) -> None:
        """Every state must appear, so no state can silently fall off the dispatch."""
        assert set(_EXPECTED_TOP_VIEW_IMAGE) == set(ViewStates)

    @pytest.mark.parametrize("state", list(_EXPECTED_TOP_VIEW_IMAGE), ids=lambda s: s.name)
    def test_state_routes_to_its_image_source(
        self, dispatch_pipeline: ViewPipeline, state: ViewStates
    ) -> None:
        dispatch_pipeline._view_state = state

        dispatch_pipeline._set_next_top_view_image()

        assert dispatch_pipeline._top_view_image_info == _EXPECTED_TOP_VIEW_IMAGE[state]

    def test_unhandled_state_raises_with_the_state_in_the_message(
        self, dispatch_pipeline: ViewPipeline
    ) -> None:
        """The fall-through is a tripwire for a state added without a dispatch entry."""
        dispatch_pipeline._view_state = "not-a-view-state"  # ty: ignore[invalid-assignment]

        with pytest.raises(AssertionError, match=r"^Unhandled view state: not-a-view-state$"):
            dispatch_pipeline._set_next_top_view_image()

    def test_random_top_view_images_come_from_the_top_view_pool(
        self, dispatch_pipeline: ViewPipeline
    ) -> None:
        """The top view excludes nontitle/original-art images and prefers edited ones."""
        dispatch_pipeline._view_state = ViewStates.ON_THE_STORIES_NODE

        dispatch_pipeline._set_next_top_view_image()

        _selector(dispatch_pipeline).get_random_image.assert_called_once_with(
            [f"list:{ALL_LISTS}"],
            file_types=vp_module._TOP_VIEW_IMAGE_TYPES,
            use_only_edited_if_possible=True,
        )

    def test_each_render_rearms_the_rotation_timer(self, dispatch_pipeline: ViewPipeline) -> None:
        """A stale interval must be cancelled, not left firing alongside the new one."""
        scheduler = _scheduler(dispatch_pipeline)
        dispatch_pipeline._view_state = ViewStates.ON_THE_STORIES_NODE

        dispatch_pipeline._set_next_top_view_image()
        dispatch_pipeline._set_next_top_view_image()

        assert len(scheduler.active_intervals) == 1
        assert scheduler.active_intervals[0].period_secs == (
            ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS
        )
