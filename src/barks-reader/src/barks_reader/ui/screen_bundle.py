"""ScreenBundle: frozen dataclass grouping the 10 screen widgets that compose the main screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bottom_title_view_screen import BottomTitleViewScreen
    from .entity_index_screen import EntityIndexScreen
    from .fun_image_view_screen import FunImageViewScreen
    from .history_screen import HistoryScreen
    from .index_screen import IndexScreen
    from .main_index_screen import MainIndexScreen
    from .search_screen import SearchScreen
    from .speech_index_screen import SpeechIndexScreen
    from .statistics_screen import StatisticsScreen
    from .tree_view_screen import TreeViewScreen


@dataclass(frozen=True, slots=True)
class ScreenBundle:
    """All screen widgets that compose the main screen's content areas.

    Passed as a single argument to collaborators instead of 9 individual screen parameters.
    """

    tree_view: TreeViewScreen
    bottom_title_view: BottomTitleViewScreen
    fun_image_view: FunImageViewScreen
    main_index: MainIndexScreen
    speech_index: SpeechIndexScreen
    names_index: EntityIndexScreen
    locations_index: EntityIndexScreen
    statistics: StatisticsScreen
    history: HistoryScreen
    search: SearchScreen

    @property
    def bottom_screens(
        self,
    ) -> tuple[
        BottomTitleViewScreen,
        FunImageViewScreen,
        MainIndexScreen,
        SpeechIndexScreen,
        EntityIndexScreen,
        EntityIndexScreen,
        StatisticsScreen,
        HistoryScreen,
        SearchScreen,
    ]:
        """All screens that live in the bottom pane."""
        return (
            self.bottom_title_view,
            self.fun_image_view,
            self.main_index,
            self.speech_index,
            self.names_index,
            self.locations_index,
            self.statistics,
            self.history,
            self.search,
        )

    @property
    def index_screens(
        self,
    ) -> tuple[MainIndexScreen, SpeechIndexScreen, EntityIndexScreen, EntityIndexScreen]:
        """Index screens that share on_goto_title / on_goto_background_title_func callbacks."""
        return (
            self.main_index,
            self.speech_index,
            self.names_index,
            self.locations_index,
        )

    def any_bottom_visible(self) -> bool:
        """Return True if any bottom screen is currently visible."""
        return any(s.is_visible for s in self.bottom_screens)

    def get_active_nav_screen(
        self,
    ) -> HistoryScreen | IndexScreen | StatisticsScreen | SearchScreen | None:
        """Return the first visible bottom screen that supports keyboard navigation."""
        nav_screens: list[HistoryScreen | IndexScreen | StatisticsScreen | SearchScreen] = [
            self.main_index,
            self.speech_index,
            self.names_index,
            self.locations_index,
            self.statistics,
            self.history,
            self.search,
        ]
        return next((s for s in nav_screens if s.is_visible), None)
