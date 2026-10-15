"""A ``ViewPipeline`` over fakes, for the pipeline tests to share.

Reached as a top-level module: ``conftest.py`` puts this directory on ``sys.path``.
Every image source the pipeline can ask for is stubbed with a distinct, real
``ImageInfo`` (or list), so a code path that reaches a new one fails here, once,
rather than in whichever test module happened to stub it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import ALL_LISTS
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline


def make_pipeline() -> ViewPipeline:
    """Create a ViewPipeline with mocked image selection and a fake scheduler and colors."""
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")
    # Theme expansion iterates this; a MagicMock return value is not iterable.
    reader_settings.file_paths.get_file_type_titles.return_value = []

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
    image_selector.get_random_reading_history_image.return_value = ImageInfo(
        filename=Path("history.png")
    )
    image_selector.get_search_image_for_title.return_value = ImageInfo(
        filename=Path("search-for-title.png")
    )
    image_selector.get_random_image_for_title.return_value = Path("title.png")

    title_lists = {ALL_LISTS: [MagicMock()]}

    return ViewPipeline(
        reader_settings=reader_settings,
        title_lists=title_lists,  # ty: ignore[invalid-argument-type]
        image_selector=image_selector,
        scheduler=FakeScheduler(),
        colors=ScriptedColorSource(),
    )


def selector_of(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's image_selector as a MagicMock for assertion access."""
    return pipeline.__dict__["_image_selector"]


def settings_of(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's reader_settings as a MagicMock for assertion access."""
    return pipeline.__dict__["_reader_settings"]


def title_lists_of(pipeline: ViewPipeline) -> dict:
    """Return the pipeline's title_lists as an untyped dict for arbitrary key assignment."""
    return pipeline.__dict__["_title_lists"]


def scheduler_of(pipeline: ViewPipeline) -> FakeScheduler:
    """Return the pipeline's scheduler as the concrete fake, for interval assertions."""
    return pipeline.__dict__["_scheduler"]
