"""Immutable input to the view-rendering pipeline.

`ViewRequest` bundles the navigation context (category, year ranges, tag, tag
group, playlist, current title), the fun-image theme policy, the target view state,
the one-shot provided title-image file, and the flags that keep the top and fun
images into a single immutable value. `NavigationModel.view_state_for()` builds one from a
`Destination`; `ui.view_renderer.ViewRenderer` layers on the renderer-owned
fields and passes it to `ViewPipeline.render()`.

`ImageThemes` lives here (rather than in the much larger `view_pipeline`) so that
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
    playlist_id: str = ""
    month: int = 0  # 1 to 12 on a '<Month> in Barks' node; 0 elsewhere.
    title_str: str = ""
    fun_image_themes: set[ImageThemes] | None = None
    title_image_file: PanelPath | None = None
    preserve_top_view: bool = False
    preserve_fun_view: bool = False


class ImageThemesToUse(Enum):
    """Whether to use all themes or the user's custom selection."""

    ALL = auto()
    CUSTOM = auto()


class ImageThemesChange(Enum):
    """Mutation kinds for the custom fun-image-theme set."""

    ADD = auto()
    DISCARD = auto()


class FunImageThemeChoice:
    """Which themes the fun view's pictures are drawn from: all, or the user's own set.

    The user's set starts as every theme and is kept while all are in use, so going
    back to it finds it as it was left.
    """

    def __init__(self) -> None:
        self._use_custom = False
        self._custom: set[ImageThemes] = set(ImageThemes)

    def use(self, themes_to_use: ImageThemesToUse) -> None:
        """Switch between all the themes and the user's own set.

        Args:
            themes_to_use: Which of the two to draw from.

        Raises:
            ValueError: For a choice that is neither.

        """
        if themes_to_use not in (ImageThemesToUse.ALL, ImageThemesToUse.CUSTOM):
            msg = f'Unimplemented ImageThemesToUse: "{themes_to_use}"'
            raise ValueError(msg)
        self._use_custom = themes_to_use == ImageThemesToUse.CUSTOM

    def alter(self, image_theme: ImageThemes, alteration: ImageThemesChange) -> None:
        """Add a theme to the user's own set, or take it out.

        Args:
            image_theme: The theme.
            alteration: Whether it is added or discarded.

        """
        if alteration == ImageThemesChange.ADD:
            self._custom.add(image_theme)
        else:
            self._custom.discard(image_theme)

    @property
    def themes(self) -> set[ImageThemes] | None:
        """The themes to draw from as a view request names them: None for all of them."""
        return set(self._custom) if self._use_custom else None
