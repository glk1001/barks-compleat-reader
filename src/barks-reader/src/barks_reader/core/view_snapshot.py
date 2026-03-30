"""Immutable snapshot of the desired UI state.

These dataclasses flow from BackgroundViews → SnapshotApplicator, making the
data path explicit and testable without any Kivy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barks_reader.core.image_selector import ImageInfo
    from barks_reader.core.reader_colors import Color


@dataclass(frozen=True, slots=True)
class TopViewSnapshot:
    """Desired state for the top (tree-view background) image."""

    image_info: ImageInfo
    image_opacity: float
    image_color: Color


@dataclass(frozen=True, slots=True)
class FunViewSnapshot:
    """Desired state for the bottom fun-image view."""

    is_visible: bool
    image_info: ImageInfo | None = None
    image_color: Color = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class TitleViewSnapshot:
    """Desired state for the bottom title-image view."""

    is_visible: bool
    image_info: ImageInfo | None = None
    image_color: Color = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True, slots=True)
class SearchViewSnapshot:
    """Desired state for the search screen."""

    is_visible: bool
    mode: str = ""
    image_info: ImageInfo | None = None


@dataclass(frozen=True, slots=True)
class ScreenVisibility:
    """Visibility flags for index and statistics screens."""

    main_index: bool = False
    speech_index: bool = False
    names_index: bool = False
    locations_index: bool = False
    statistics: bool = False


@dataclass(frozen=True, slots=True)
class ViewSnapshot:
    """Complete snapshot of the desired UI view state.

    Produced by ``BackgroundViews.compute_snapshot()`` and consumed by
    ``SnapshotApplicator.apply()`` to drive all screen-widget updates.
    """

    view_state: int  # ViewStates IntEnum value — kept as int to avoid ui import
    top_view: TopViewSnapshot
    fun_view: FunViewSnapshot
    title_view: TitleViewSnapshot
    screen_visibility: ScreenVisibility
    search_view: SearchViewSnapshot
