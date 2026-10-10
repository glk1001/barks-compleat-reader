# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import barks_reader.ui.navigation_coordinator
import pytest
from barks_fantagraphics.barks_tags import Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import NON_COMIC_TITLES
from barks_fantagraphics.comics_database import TitleNotFoundError
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, SERIES_EXTRAS
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.user_error_types import ErrorTypes, TitleNotInFantaInfoError
from barks_reader.ui.navigation_coordinator import NavigationCoordinator, TitleTarget


@pytest.fixture
def mock_deps() -> dict[str, MagicMock]:
    return {
        "reader_settings": MagicMock(),
        "comics_database": MagicMock(),
        "renderer": MagicMock(),
        "comic_reader_manager": MagicMock(),
        "bottom_title_view_screen": MagicMock(),
        "tree_view_screen": MagicMock(),
        "screen_switchers": MagicMock(),
        "special_fanta_overrides": MagicMock(),
        "user_error_handler": MagicMock(),
        "on_active_changed": MagicMock(),
    }


@pytest.fixture
def nav_coord(mock_deps: dict[str, MagicMock]) -> NavigationCoordinator:
    coord = NavigationCoordinator(**mock_deps)
    coord.set_tree_view_manager(MagicMock())
    return coord


class TestNavigationCoordinator:
    def test_select_title_sets_current_fanta_info(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"

        target = TitleTarget(fanta_info=mock_fanta_info)
        nav_coord.select_title(target)

        assert nav_coord.current_fanta_info == mock_fanta_info
        mock_deps["renderer"].render_title.assert_called_with(
            mock_fanta_info, title_image_file=None, preserve_top_view=False
        )

    def test_navigate_to_chrono_title(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title Str"
        mock_fanta_info.comic_book_info.submitted_year = 1942

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_year_range_nodes({(1942, 1946): mock_year_node})

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

            assert nav_coord.current_fanta_info == mock_fanta_info
            mock_deps["renderer"].render_title.assert_called_with(
                mock_fanta_info, title_image_file=image_info.filename
            )

    def test_navigate_to_chrono_title_one_pager_navigates_year_range_node(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        """One-pagers navigate to the year-range group under the One Pagers node."""
        tree_manager = MagicMock()
        nav_coord.set_tree_view_manager(tree_manager)
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.IF_THE_HAT_FITS)
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.submitted_year = 1948  # -> (1946, 1952) group

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_one_pager_year_range_nodes({(1946, 1952): mock_year_node})

        mock_title_node = MagicMock()
        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=mock_title_node,
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

        # Title view shown AND the correct year-range group is opened and navigated to.
        mock_deps["renderer"].render_title.assert_called_with(
            mock_fanta_info, title_image_file=image_info.filename
        )
        mock_year_node.ensure_populated.assert_called_once()
        tree_manager.open_node_and_parent_nodes.assert_called_once_with(mock_year_node)
        tree_manager.goto_node.assert_called_once_with(mock_title_node, scroll_to=True)

    def test_navigate_to_chrono_title_cover_navigates_year_range_node(
        self, nav_coord: NavigationCoordinator
    ) -> None:
        """Covers navigate to the year-range group under the Covers node."""
        tree_manager = MagicMock()
        nav_coord.set_tree_view_manager(tree_manager)
        image_info = ImageInfo(
            filename=Path("img.png"), from_title=Titles.COMICS_AND_STORIES_104_COVER
        )
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.submitted_year = 1953  # -> (1953, 1955) group

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_cover_year_range_nodes({(1953, 1955): mock_year_node})

        mock_title_node = MagicMock()
        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=mock_title_node,
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

        mock_year_node.ensure_populated.assert_called_once()
        tree_manager.open_node_and_parent_nodes.assert_called_once_with(mock_year_node)
        tree_manager.goto_node.assert_called_once_with(mock_title_node, scroll_to=True)

    def test_navigate_to_chrono_title_undated_cover_folds_into_final_group(
        self, nav_coord: NavigationCoordinator
    ) -> None:
        """An undated cover (submitted_year == -1) resolves to the final Covers group."""
        tree_manager = MagicMock()
        nav_coord.set_tree_view_manager(tree_manager)
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.UNCLE_SCROOGE_6_COVER)
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.submitted_year = -1  # undated -> final group

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_cover_year_range_nodes({(1960, 1965): mock_year_node})

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

        tree_manager.open_node_and_parent_nodes.assert_called_once_with(mock_year_node)

    def test_navigate_to_chrono_title_preserves_back_node(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(filename=Path("img.png"), from_title=Titles.ADVENTURE_DOWN_UNDER)

        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title Str"
        mock_fanta_info.comic_book_info.submitted_year = 1942

        mock_year_node = MagicMock()
        mock_year_node.nodes = []
        nav_coord.set_year_range_nodes({(1942, 1946): mock_year_node})

        mock_search_node = MagicMock()
        mock_deps["tree_view_screen"].get_selected_node.return_value = mock_search_node

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_fanta_info,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "find_tree_view_title_node",
                return_value=MagicMock(),
            ),
        ):
            nav_coord.navigate_to_chrono_title(image_info)

            mock_deps[
                "tree_view_screen"
            ].ids.reader_tree_view.set_back_node.assert_called_once_with(mock_search_node)

    def test_read_comic_calls_comic_reader(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.get_title_str.return_value = "Title"
        nav_coord._current_fanta_info = mock_fanta_info

        mock_deps["bottom_title_view_screen"].goto_page_active = True
        mock_deps["bottom_title_view_screen"].goto_page_num = "10"
        mock_deps["bottom_title_view_screen"].use_overrides_active = False
        mock_deps["bottom_title_view_screen"].tagged_pages = ["10", "11", "14"]
        mock_comic = MagicMock()
        mock_deps["comics_database"].get_comic_book.return_value = mock_comic

        result = nav_coord.read_comic()

        assert result is True
        mock_deps["on_active_changed"].assert_called_once()
        mock_deps["comic_reader_manager"].read_barks_comic_book.assert_called_once_with(
            mock_fanta_info,
            mock_comic,
            "10",
            False,  # noqa: FBT003 - use_overrides_active, passed positionally
            tagged_pages=["10", "11", "14"],
        )

    def test_read_comic_one_pager_opens_collection_at_its_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        """Selecting a one-pager opens the collection at the one-pager's page."""
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.title = Titles.IF_THE_HAT_FITS  # a one-pager
        nav_coord._current_fanta_info = mock_fanta_info
        mock_deps["bottom_title_view_screen"].use_overrides_active = False

        mock_collection_info = MagicMock()
        mock_comic = MagicMock()
        mock_deps["comics_database"].get_comic_book.return_value = mock_comic

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_one_pager_collection_page_num",
                return_value=7,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_collection_info,
            ),
        ):
            result = nav_coord.read_comic()

        assert result is True
        # Opens the collection comic with the collection's fanta_info, at page "7".
        manager = mock_deps["comic_reader_manager"]
        manager.read_barks_comic_book.assert_called_once()
        call = manager.read_barks_comic_book.call_args
        assert call.args[0] is mock_collection_info
        assert call.args[1] is mock_comic
        assert call.args[2] == "7"
        # Opens only page 7's year-range group (the first one-pager group).
        assert call.kwargs["collection_page_range"] == (1, 43)
        # History records the one-pager's own title, not the collection's.
        assert call.kwargs["history_title_str"] == ENUM_TO_STR_TITLE[Titles.IF_THE_HAT_FITS]

    def test_read_comic_cover_opens_collection_at_its_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        """Selecting a cover opens the All Covers collection at the cover's page."""
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.title = Titles.FOUR_COLOR_189_COVER  # a cover
        nav_coord._current_fanta_info = mock_fanta_info
        mock_deps["bottom_title_view_screen"].use_overrides_active = False

        mock_collection_info = MagicMock()
        mock_comic = MagicMock()
        mock_deps["comics_database"].get_comic_book.return_value = mock_comic

        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_cover_collection_page_num",
                return_value=3,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_fanta_info",
                return_value=mock_collection_info,
            ),
        ):
            result = nav_coord.read_comic()

        assert result is True
        manager = mock_deps["comic_reader_manager"]
        manager.read_barks_comic_book.assert_called_once()
        call = manager.read_barks_comic_book.call_args
        assert call.args[0] is mock_collection_info
        assert call.args[1] is mock_comic
        assert call.args[2] == "3"
        # Opens only page 3's year-range group (the first cover group). Derived from
        # BARKS_COVERS order - see TestGroupRanges in test_collection_page_groups.py
        # before editing this number.
        assert call.kwargs["collection_page_range"] == (1, 56)
        # History records the cover's own title, not the collection's.
        assert call.kwargs["history_title_str"] == ENUM_TO_STR_TITLE[Titles.FOUR_COLOR_189_COVER]

    def test_read_comic_unlocated_one_pager_returns_false(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        """A one-pager not present in the collection does not open anything."""
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.title = Titles.IF_THE_HAT_FITS
        nav_coord._current_fanta_info = mock_fanta_info

        with patch.object(
            barks_reader.ui.navigation_coordinator,
            "get_one_pager_collection_page_num",
            return_value=None,
        ):
            result = nav_coord.read_comic()

        assert result is False
        mock_deps["comic_reader_manager"].read_barks_comic_book.assert_not_called()

    def test_on_comic_closed_restores_view_state(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord._read_comic_view_state = ViewStates.ON_INDEX_NODE
        mock_fanta_info = MagicMock()
        nav_coord._current_fanta_info = mock_fanta_info

        mock_last_page = MagicMock()
        mock_last_page.display_page_num = "5"
        mock_deps["comic_reader_manager"].comic_closed.return_value = mock_last_page

        nav_coord.on_comic_closed()

        mock_deps["renderer"].render_state.assert_called_with(ViewStates.ON_INDEX_NODE)
        assert nav_coord._read_comic_view_state is None

    def test_on_document_closed_restores_view_state(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord._doc_reader_close_view_state = ViewStates.ON_INTRO_NODE

        nav_coord.on_document_closed()

        mock_deps["renderer"].render_state.assert_called_with(ViewStates.ON_INTRO_NODE)
        assert nav_coord._doc_reader_close_view_state is None

    def test_open_wiki_passes_no_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        bundle = Path("/bundle")
        mock_deps["reader_settings"].wiki_bundle_dir = bundle

        nav_coord.open_wiki()

        mock_deps["on_active_changed"].assert_called_with(False)  # noqa: FBT003
        mock_deps["screen_switchers"].switch_to_wiki_reader.assert_called_with(bundle, None)

    def test_open_wiki_page_for_title_no_bundle_is_noop(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_deps["reader_settings"].wiki_bundle_dir = None

        nav_coord.open_wiki_page_for_title(Titles.LOST_IN_THE_ANDES)

        mock_deps["on_active_changed"].assert_not_called()
        mock_deps["screen_switchers"].switch_to_wiki_reader.assert_not_called()

    def test_open_wiki_page_for_title_missing_page_is_noop(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_deps["reader_settings"].wiki_bundle_dir = Path("/bundle")

        with patch.object(
            barks_reader.ui.navigation_coordinator, "wiki_page_for_title", return_value=None
        ):
            nav_coord.open_wiki_page_for_title(Titles.LOST_IN_THE_ANDES)

        mock_deps["on_active_changed"].assert_not_called()
        mock_deps["screen_switchers"].switch_to_wiki_reader.assert_not_called()

    def test_open_wiki_page_for_title_opens_wiki_at_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        bundle = Path("/bundle")
        page = bundle / "concept" / "stories" / "donald-duck" / "lost-in-the-andes.md"
        mock_deps["reader_settings"].wiki_bundle_dir = bundle

        with patch.object(
            barks_reader.ui.navigation_coordinator, "wiki_page_for_title", return_value=page
        ) as wiki_page_mock:
            nav_coord.open_wiki_page_for_title(Titles.LOST_IN_THE_ANDES)

        wiki_page_mock.assert_called_with(bundle, Titles.LOST_IN_THE_ANDES)
        mock_deps["on_active_changed"].assert_called_with(False)  # noqa: FBT003
        mock_deps["screen_switchers"].switch_to_wiki_reader.assert_called_with(bundle, page)


class TestNavigateToSearchResult:
    """A title picked from tag-search results offers its tagged page, as the tree does."""

    TRAPPER = ENUM_TO_STR_TITLE[Titles.MIGHTY_TRAPPER_THE]

    def _navigate(self, nav_coord: NavigationCoordinator, tags: tuple[Tags, ...]) -> None:
        with patch.object(nav_coord, "navigate_to_chrono_title") as chrono:
            assert nav_coord.navigate_to_search_result(self.TRAPPER, tags)
        chrono.assert_called_once_with(ImageInfo(from_title=Titles.MIGHTY_TRAPPER_THE))

    def test_a_tag_with_a_page_in_the_title_sets_goto_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        self._navigate(nav_coord, (Tags.FIRST_DAISY,))
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_called_once_with(
            "2", active=True, tagged_pages=["2"]
        )

    def test_the_first_tag_with_a_page_in_the_title_is_used(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        self._navigate(nav_coord, (Tags.GYRO_GEARLOOSE, Tags.FIRST_DAISY))
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_called_once_with(
            "2", active=True, tagged_pages=["2"]
        )

    @pytest.mark.parametrize("tags", [(), (Tags.GYRO_GEARLOOSE,)], ids=["no-tags", "no-page"])
    def test_without_a_tagged_page_the_last_read_page_stands(
        self,
        nav_coord: NavigationCoordinator,
        mock_deps: dict[str, MagicMock],
        tags: tuple[Tags, ...],
    ) -> None:
        self._navigate(nav_coord, tags)
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_not_called()

    def test_an_unknown_title_is_not_navigated_to(self, nav_coord: NavigationCoordinator) -> None:
        with patch.object(nav_coord, "navigate_to_chrono_title") as chrono:
            assert not nav_coord.navigate_to_search_result("No Such Story", (Tags.FIRST_DAISY,))
        chrono.assert_not_called()


ANDES = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]


class TestUpdateTitle:
    """A tree label picked: the title view follows a configured story, else stays."""

    def test_a_configured_story_becomes_the_current_title(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        assert nav_coord.update_title(ANDES) is True
        info = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
        assert nav_coord.current_fanta_info is info
        mock_deps["renderer"].set_title_without_render.assert_called_once_with(info, None)

    def test_a_label_naming_no_title_changes_nothing(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        assert nav_coord.update_title("No Such Story") is False
        assert nav_coord.current_fanta_info is None
        mock_deps["renderer"].set_title_without_render.assert_not_called()

    def test_an_extras_title_is_not_shown(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        extra = next(
            t for t, info in ALL_FANTA_COMIC_BOOK_INFO.items() if info.series_name == SERIES_EXTRAS
        )
        assert nav_coord.update_title(ENUM_TO_STR_TITLE[extra]) is False
        mock_deps["renderer"].set_title_without_render.assert_not_called()


class TestAVolumeNotAvailable:
    """A comic whose volume is missing is reported to the user, not opened."""

    def _not_found(self, mock_deps: dict[str, MagicMock]) -> None:
        mock_deps["comics_database"].get_comic_book.side_effect = TitleNotFoundError("gone", ANDES)

    def _assert_reported(self, mock_deps: dict[str, MagicMock]) -> None:
        handle_error = mock_deps["user_error_handler"].handle_error
        error_type, error_info = handle_error.call_args.args
        assert error_type is ErrorTypes.ArchiveVolumeNotAvailable
        assert error_info.title is Titles.LOST_IN_THE_ANDES
        mock_deps["comic_reader_manager"].read_barks_comic_book.assert_not_called()
        mock_deps["on_active_changed"].assert_not_called()

    def test_reading_a_story(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord._current_fanta_info = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
        self._not_found(mock_deps)
        assert nav_coord.read_comic() is False
        self._assert_reported(mock_deps)

    def test_reading_a_page_of_a_collection(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        mock_fanta_info = MagicMock()
        mock_fanta_info.comic_book_info.title = Titles.IF_THE_HAT_FITS  # a one-pager
        nav_coord._current_fanta_info = mock_fanta_info
        self._not_found(mock_deps)
        with (
            patch.object(
                barks_reader.ui.navigation_coordinator,
                "get_one_pager_collection_page_num",
                return_value=7,
            ),
            patch.object(
                barks_reader.ui.navigation_coordinator, "get_fanta_info", return_value=MagicMock()
            ),
        ):
            assert nav_coord.read_comic() is False
        self._assert_reported(mock_deps)


class TestYearRangeParentNode:
    def test_a_title_with_no_year_range_is_an_error(self) -> None:
        info = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
        with pytest.raises(RuntimeError, match="No year range found"):
            NavigationCoordinator._year_range_parent_node(None, {}, info)

    def test_a_range_with_no_tree_node_is_an_error(self) -> None:
        info = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
        with pytest.raises(RuntimeError, match=r"No year node found for range '\(1947, 1950\)'"):
            NavigationCoordinator._year_range_parent_node((1947, 1950), {}, info)


class TestNavigateToTitleWithPage:
    """From an index screen: to the title, and its goto-page set to the page indexed."""

    def test_an_article_is_read_rather_than_navigated_to(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        article = next(iter(NON_COMIC_TITLES))
        with patch.object(nav_coord, "navigate_to_chrono_title") as navigated:
            nav_coord.navigate_to_title_with_page(ImageInfo(from_title=article), "3")
        navigated.assert_not_called()
        mock_deps["comic_reader_manager"].read_article_as_comic_book.assert_called_once()

    def test_a_story_goes_to_its_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(from_title=Titles.LOST_IN_THE_ANDES)
        with patch.object(nav_coord, "navigate_to_chrono_title") as navigated:
            nav_coord.navigate_to_title_with_page(image_info, "12")
        navigated.assert_called_once_with(image_info)
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_called_once_with(
            "12", active=True, tagged_pages=()
        )

    def test_a_title_under_a_tag_offers_all_its_tagged_pages(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        image_info = ImageInfo(from_title=Titles.ADVENTURE_DOWN_UNDER)
        with patch.object(nav_coord, "navigate_to_chrono_title"):
            nav_coord.navigate_to_title_with_page(image_info, "7", ("7", "13", "16", "17"))
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_called_once_with(
            "7", active=True, tagged_pages=("7", "13", "16", "17")
        )

    def test_a_one_pager_sets_no_page(
        self, nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
    ) -> None:
        """Reading one deep-links to its page in the collection; the index's page would mislead."""
        with patch.object(nav_coord, "navigate_to_chrono_title"):
            nav_coord.navigate_to_title_with_page(ImageInfo(from_title=Titles.IF_THE_HAT_FITS), "1")
        mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_not_called()


def test_the_wiki_without_a_bundle_opens_nothing(
    nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock]
) -> None:
    mock_deps["reader_settings"].wiki_bundle_dir = None
    nav_coord.open_wiki()
    mock_deps["screen_switchers"].switch_to_wiki_reader.assert_not_called()
    mock_deps["on_active_changed"].assert_not_called()


def test_a_tag_on_no_page_of_a_title_leaves_goto_page_alone(
    nav_coord: NavigationCoordinator, mock_deps: dict[str, MagicMock], loguru_sink: list[str]
) -> None:
    with patch.object(barks_reader.ui.navigation_coordinator, "BARKS_TAGGED_PAGES", {}):
        nav_coord._set_tag_goto_page_checkbox(Tags.ALASKA, "Back to the Klondike")
    mock_deps["bottom_title_view_screen"].set_goto_page_state.assert_not_called()
    assert 'No pages for (Alaska, "Back to the Klondike").' in loguru_sink


def test_a_title_with_no_fanta_info_is_refused() -> None:
    with (
        patch.object(barks_reader.ui.navigation_coordinator, "get_fanta_info", return_value=None),
        pytest.raises(TitleNotInFantaInfoError),
    ):
        NavigationCoordinator._get_fanta_info(Titles.BACK_TO_THE_KLONDIKE)
