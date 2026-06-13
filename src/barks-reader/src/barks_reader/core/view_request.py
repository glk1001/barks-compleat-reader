"""Immutable input to the view-rendering pipeline.

`ViewRequest` bundles the navigation context (category, year ranges, tag, tag
group, current title), the fun-image theme policy, the target view state, the
one-shot provided title-image file, and the preserve-top-view flag into a single
immutable value. `NavigationModel.view_state_for()` builds one from a
`Destination`; `ui.view_renderer.ViewRenderer` layers on the renderer-owned
fields and passes it to `ViewPipeline.render()`.

`ImageThemes` lives here (rather than in the 797-line `view_pipeline`) so that
`NavigationModel` and other lightweight callers can reference the request type
without importing the whole pipeline. `view_pipeline` re-exports `ImageThemes`
for back-compat.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from comic_utils.comic_consts import PanelPath

    from .navigation.view_states import ViewStates


class ImageThemes(Enum):
    """Tag-style filters that constrain which titles feed the fun-image view."""

    AI = auto()
    BLACK_AND_WHITE = auto()
    CENSORSHIP = auto()
    CLASSICS = auto()
    FAVOURITES = auto()
    INSETS = auto()
    SILHOUETTES = auto()
    SPLASHES = auto()
    FORTIES = auto()
    FIFTIES = auto()
    SIXTIES = auto()


@dataclass(frozen=True, slots=True)
class ViewRequest:
    """Immutable description of one navigation result to render.

    Every field but `view_state` defaults, so the common call is
    `ViewRequest(view_state=...)`. `title_image_file` is a one-shot input
    consumed by a single `render()`; it is not carried into `current_request()`.
    """

    view_state: ViewStates
    category: str = ""
    year_range: str = ""
    cs_year_range: str = ""
    us_year_range: str = ""
    tag_group: TagGroups | None = None
    tag: Tags | None = None
    title_str: str = ""
    fun_image_themes: set[ImageThemes] | None = None
    title_image_file: PanelPath | None = None
    preserve_top_view: bool = False
