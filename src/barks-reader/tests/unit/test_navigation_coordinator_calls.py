# ruff: noqa: SLF001
"""What the navigation coordinator hands its collaborators: the values, not just the calls.

The tests in ``test_navigation_coordinator.py`` say which collaborator is called on each
path. These say with what: a title, a page or a view state swapped for another, or for
nothing, passed every one of those (the mutation run of 2026-11-23).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS
from barks_fantagraphics.comics_database import TitleNotFoundError
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core import log_markers
from barks_reader.core.goto_page import GotoPageOffer, goto_page_after_reading
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.navigation import NavigationCoordinator, TitleTarget
from barks_reader.core.navigation import navigation_coordinator as coordinator_module
from barks_reader.core.navigation.title_position import title_year_range
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.ports import TitleViewChoices
from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

if TYPE_CHECKING:
    from collections.abc import Iterator

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

ANDES = Titles.LOST_IN_THE_ANDES
ANDES_INFO = ALL_FANTA_COMIC_BOOK_INFO[ANDES]
ANDES_STR = ENUM_TO_STR_TITLE[ANDES]
ARTICLE = Titles.DON_AULT___LIFE_AMONG_THE_DUCKS
COLORING_ARTICLE = Titles.RICH_TOMMASO___ON_COLORING_BARKS
ONE_PAGER = Titles.IF_THE_HAT_FITS
COVER = next(iter(COVERS_SET))


def _last_read(nav_coord_deps: dict[str, MagicMock], page: str | None) -> None:
    saved = None if page is None else MagicMock(display_page_num=page)
    nav_coord_deps["comic_reader_manager"].get_last_read_page.return_value = saved


def _overrides_in_use(nav_coord_deps: dict[str, MagicMock], *, in_use: bool) -> None:
    nav_coord_deps["bottom_title_view_screen"].choices.return_value = TitleViewChoices(
        goto_page_active=False, goto_page_num="", tagged_pages=(), use_overrides_active=in_use
    )


def _fanta_info_of(title: Titles) -> MagicMock:
    info = MagicMock()
    info.comic_book_info.title = title
    info.comic_book_info.get_title_str.return_value = ENUM_TO_STR_TITLE[title]
    return info


class TestACoordinatorJustBuilt:
    """Before a title is picked or a tree is set, it has nothing and puts nothing back."""

    @pytest.fixture
    def bare(self, nav_coord_deps: dict[str, MagicMock]) -> NavigationCoordinator:
        return NavigationCoordinator(**nav_coord_deps)

    def test_it_has_no_title(self, bare: NavigationCoordinator) -> None:
        assert bare.current_fanta_info is None

    def test_a_reader_closing_renders_no_view_and_offers_no_page(
        self, bare: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        bare.on_comic_closed()
        bare.on_document_closed()
        nav_coord_deps["renderer"].render_state.assert_not_called()
        nav_coord_deps["comic_reader_manager"].comic_closed.assert_not_called()

    def test_with_no_year_nodes_set_a_title_has_no_node(self, bare: NavigationCoordinator) -> None:
        with pytest.raises(RuntimeError, match="No year node found"):
            bare.navigate_to_chrono_title(ImageInfo(from_title=ANDES))


class TestSelectingATitle:
    def test_the_rows_own_image_is_the_one_rendered(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        image = Path("insets/andes.png")
        nav_coord.select_title(TitleTarget(fanta_info=ANDES_INFO, title_image_file=image))
        nav_coord_deps["renderer"].render_title.assert_called_once_with(
            ANDES_INFO, title_image_file=image, preserve_top_view=False
        )

    def test_with_no_tag_the_page_last_read_is_the_one_offer(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        _last_read(nav_coord_deps, "12")
        nav_coord.select_title(TitleTarget(fanta_info=ANDES_INFO))
        nav_coord_deps["comic_reader_manager"].get_last_read_page.assert_called_once_with(ANDES_STR)
        assert nav_coord_deps["bottom_title_view_screen"].show_goto_page.call_args_list == [
            call(goto_page_after_reading("12"))
        ]

    def test_with_nothing_read_no_page_is_offered(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        _last_read(nav_coord_deps, None)
        nav_coord.select_title(TitleTarget(fanta_info=ANDES_INFO))
        assert nav_coord_deps["bottom_title_view_screen"].show_goto_page.call_args_list == [
            call(goto_page_after_reading(""))
        ]
        assert goto_page_after_reading("") == GotoPageOffer()

    def test_under_a_tag_with_pages_the_tags_offer_is_the_only_one(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        """Not the page last read first and the tag's after it: one offer, one logged."""
        _last_read(nav_coord_deps, "25")
        tag = next(iter(coordinator_module.Tags))
        with patch.object(coordinator_module, "get_tagged_pages", return_value=["19", "26"]):
            nav_coord.select_title(TitleTarget(fanta_info=ANDES_INFO, tag=tag))
        assert nav_coord_deps["bottom_title_view_screen"].show_goto_page.call_args_list == [
            call(GotoPageOffer.make("19", active=True, tagged_pages=["19", "26"], kept_page="25"))
        ]


class TestTheOverridesRow:
    """Shown ticked and fixed, or with the title's own choice and what it changes."""

    def _select(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        *,
        prebuilt: bool,
        optional: bool,
    ) -> MagicMock:
        nav_coord_deps["reader_settings"].use_prebuilt_archives = prebuilt
        overrides = nav_coord_deps["special_fanta_overrides"]
        overrides.is_title_where_overrides_are_optional.return_value = optional
        nav_coord.select_title(TitleTarget(fanta_info=ANDES_INFO))
        return nav_coord_deps["bottom_title_view_screen"].set_overrides_state

    @pytest.mark.parametrize(
        ("prebuilt", "optional"), [(True, True), (True, False), (False, False)]
    )
    def test_prebuilt_comics_or_a_title_with_no_choice_have_them_on(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        prebuilt: bool,
        optional: bool,
    ) -> None:
        shown = self._select(nav_coord, nav_coord_deps, prebuilt=prebuilt, optional=optional)
        assert shown.call_args_list == [call(active=True)]

    def test_a_title_with_a_choice_shows_its_setting_and_what_it_changes(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        overrides = nav_coord_deps["special_fanta_overrides"]
        overrides.get_description.return_value = "The censored panel."
        overrides.get_overrides_setting.return_value = False

        shown = self._select(nav_coord, nav_coord_deps, prebuilt=False, optional=True)

        overrides.is_title_where_overrides_are_optional.assert_called_once_with(ANDES)
        overrides.get_description.assert_called_once_with(ANDES)
        overrides.get_overrides_setting.assert_called_once_with(ANDES)
        assert shown.call_args_list == [call(description="The censored panel.", active=False)]


class TestGoingToATitlesRow:
    """From a background image: the tree opens at the title's row, and its view shows."""

    @pytest.fixture
    def year_node(self, nav_coord: NavigationCoordinator) -> MagicMock:
        node = MagicMock()
        nav_coord.set_year_range_nodes({title_year_range(ANDES, ANDES_INFO): node})
        return node

    def _go(
        self, nav_coord: NavigationCoordinator, image_info: ImageInfo, **kwargs: bool
    ) -> tuple[bool, MagicMock, MagicMock]:
        with (
            patch.object(
                coordinator_module, "get_fanta_info", return_value=ANDES_INFO
            ) as fanta_info,
            patch.object(coordinator_module, "find_tree_view_title_node") as find_row,
        ):
            went_there = nav_coord.navigate_to_chrono_title(image_info, **kwargs)
        return went_there, fanta_info, find_row

    def test_the_title_is_looked_up_and_its_row_found_among_its_years_rows(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        year_node: MagicMock,
        loguru_sink: list[str],
    ) -> None:
        image = Path("splash/andes.png")
        _last_read(nav_coord_deps, "7")

        went_there, fanta_info, find_row = self._go(
            nav_coord, ImageInfo(from_title=ANDES, filename=image)
        )

        assert went_there is True
        fanta_info.assert_called_once_with(ANDES)
        find_row.assert_called_once_with(year_node.nodes, ANDES)
        assert (
            log_markers.GOTO_TITLE.format(name="LOST_IN_THE_ANDES", filename=image) in loguru_sink
        )
        nav_coord_deps["renderer"].render_title.assert_called_once_with(
            ANDES_INFO, title_image_file=image
        )
        # Unless told not to, the page last read is offered.
        assert nav_coord_deps["bottom_title_view_screen"].show_goto_page.call_args_list == [
            call(goto_page_after_reading("7"))
        ]

    def test_a_caller_with_a_page_of_its_own_has_none_offered_here(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        year_node: MagicMock,  # noqa: ARG002
    ) -> None:
        went_there, _, _ = self._go(nav_coord, ImageInfo(from_title=ANDES), offer_page=False)
        assert went_there is True
        nav_coord_deps["bottom_title_view_screen"].show_goto_page.assert_not_called()
        nav_coord_deps["bottom_title_view_screen"].set_overrides_state.assert_called_once()

    def test_an_article_is_read_from_its_first_page_and_was_not_gone_to(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        assert nav_coord.navigate_to_chrono_title(ImageInfo(from_title=ARTICLE)) is False
        read_article = nav_coord_deps["comic_reader_manager"].read_article_as_comic_book
        read_article.assert_called_once_with(ARTICLE, "1")

    def test_a_title_in_no_volume_is_looked_up_by_itself(self) -> None:
        with (
            patch.object(coordinator_module, "get_fanta_info", return_value=None) as fanta_info,
            pytest.raises(coordinator_module.TitleNotInFantaInfoError),
        ):
            NavigationCoordinator._get_fanta_info(ANDES)
        fanta_info.assert_called_once_with(ANDES)


class TestReadingAnArticle:
    @pytest.mark.parametrize(("article", "first_page"), [(ARTICLE, "1"), (COLORING_ARTICLE, "i")])
    def test_it_opens_at_its_first_page_which_one_article_numbers_in_roman(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        article: Titles,
        first_page: str,
    ) -> None:
        nav_coord.read_article(article, None)
        read_article = nav_coord_deps["comic_reader_manager"].read_article_as_comic_book
        read_article.assert_called_once_with(article, first_page)

    def test_closed_it_shows_the_view_it_was_given(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock]
    ) -> None:
        nav_coord.read_article(ARTICLE, ViewStates.ON_APPENDIX_NODE)
        nav_coord.on_comic_closed()
        nav_coord_deps["renderer"].render_state.assert_called_once_with(ViewStates.ON_APPENDIX_NODE)

    def test_one_not_found_is_reported_as_it_was_raised(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        manager = nav_coord_deps["comic_reader_manager"]
        manager.read_article_as_comic_book.side_effect = TitleNotFoundError(
            "volume 3 is not there", ENUM_TO_STR_TITLE[ARTICLE]
        )
        nav_coord.read_article(ARTICLE, None)
        assert any("volume 3 is not there" in line for line in loguru_sink)
        nav_coord_deps["user_error_handler"].handle_error.assert_called_once_with(
            ErrorTypes.ArchiveVolumeNotAvailable, ErrorInfo(file_volume=-1, title=ARTICLE)
        )


class TestReadingAComic:
    def _select(self, nav_coord: NavigationCoordinator, info: FantaComicBookInfo) -> None:
        nav_coord._current_fanta_info = info

    @pytest.mark.parametrize("in_use", [True, False])
    def test_a_story_is_fetched_by_its_title_with_its_inset_for_the_overrides_choice(
        self, nav_coord: NavigationCoordinator, nav_coord_deps: dict[str, MagicMock], in_use: bool
    ) -> None:
        self._select(nav_coord, ANDES_INFO)
        _overrides_in_use(nav_coord_deps, in_use=in_use)
        overrides = nav_coord_deps["special_fanta_overrides"]
        overrides.get_inset_file.return_value = Path("insets/andes-fixed.png")

        assert nav_coord.read_comic() is True

        overrides.get_inset_file.assert_called_once_with(ANDES, in_use)
        nav_coord_deps["comics_database"].get_comic_book.assert_called_once_with(
            ANDES_STR, Path("insets/andes-fixed.png")
        )

    def test_a_story_not_found_is_reported_as_it_was_raised(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        self._select(nav_coord, ANDES_INFO)
        nav_coord_deps["comics_database"].get_comic_book.side_effect = TitleNotFoundError(
            "volume 7 is not there", ANDES_STR
        )
        assert nav_coord.read_comic() is False
        assert any("volume 7 is not there" in line for line in loguru_sink)
        nav_coord_deps["user_error_handler"].handle_error.assert_called_once_with(
            ErrorTypes.ArchiveVolumeNotAvailable, ErrorInfo(file_volume=-1, title=ANDES)
        )

    @pytest.mark.parametrize(
        ("member", "collection", "page_lookup"),
        [
            (ONE_PAGER, Titles.ALL_ONE_PAGERS, "get_one_pager_collection_page_num"),
            (COVER, Titles.ALL_COVERS, "get_cover_collection_page_num"),
        ],
    )
    @pytest.mark.parametrize("in_use", [True, False])
    def test_a_one_pager_or_cover_opens_its_collection_at_the_members_own_page(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        member: Titles,
        collection: Titles,
        page_lookup: str,
        in_use: bool,
    ) -> None:
        assert (member in ONE_PAGERS) != (member in COVERS_SET)
        self._select(nav_coord, _fanta_info_of(member))
        _overrides_in_use(nav_coord_deps, in_use=in_use)
        collection_info = MagicMock()
        with (
            patch.object(coordinator_module, page_lookup, return_value=3) as page_of,
            patch.object(
                coordinator_module, "get_fanta_info", return_value=collection_info
            ) as fanta_info,
        ):
            assert nav_coord.read_comic() is True

        page_of.assert_called_once_with(member)
        fanta_info.assert_called_once_with(collection)
        database = nav_coord_deps["comics_database"]
        database.get_comic_book.assert_called_once_with(ENUM_TO_STR_TITLE[collection])
        read = nav_coord_deps["comic_reader_manager"].read_barks_comic_book
        assert read.call_args.args == (
            collection_info,
            database.get_comic_book.return_value,
            "3",
            in_use,
        )

    def test_a_collection_not_found_is_reported_as_it_was_raised(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        loguru_sink: list[str],
    ) -> None:
        self._select(nav_coord, _fanta_info_of(ONE_PAGER))
        collection = ENUM_TO_STR_TITLE[Titles.ALL_ONE_PAGERS]
        nav_coord_deps["comics_database"].get_comic_book.side_effect = TitleNotFoundError(
            "no one-pagers here", collection
        )
        with (
            patch.object(coordinator_module, "get_one_pager_collection_page_num", return_value=3),
            patch.object(coordinator_module, "get_fanta_info", return_value=MagicMock()),
        ):
            assert nav_coord.read_comic() is False
        assert any("no one-pagers here" in line for line in loguru_sink)
        nav_coord_deps["user_error_handler"].handle_error.assert_called_once_with(
            ErrorTypes.ArchiveVolumeNotAvailable,
            ErrorInfo(file_volume=-1, title=Titles.ALL_ONE_PAGERS),
        )


class TestOpeningADocument:
    @pytest.fixture
    def doc_dir(self, tmp_path: Path) -> Iterator[Path]:
        with patch.object(coordinator_module, "list_document_pages", return_value=[Path("1.png")]):
            yield tmp_path

    def test_unless_asked_it_opens_at_its_first_page_in_pairs(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        doc_dir: Path,
    ) -> None:
        nav_coord.open_document(doc_dir, "How To")
        switch = nav_coord_deps["screen_switchers"].switch_to_document_reader
        switch.assert_called_once_with(doc_dir, "How To", resume=False, single_page=False)

    def test_closed_it_shows_the_view_it_was_given(
        self,
        nav_coord: NavigationCoordinator,
        nav_coord_deps: dict[str, MagicMock],
        doc_dir: Path,
    ) -> None:
        nav_coord.open_document(doc_dir, "How To", ViewStates.ON_INTRO_NODE)
        nav_coord.on_document_closed()
        nav_coord_deps["renderer"].render_state.assert_called_once_with(ViewStates.ON_INTRO_NODE)
