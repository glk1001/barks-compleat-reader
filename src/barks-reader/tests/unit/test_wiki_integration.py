"""Unit tests for the kivy-free wiki integration providers (barks_reader.core.wiki_integration).

These pin the CLAUDE.md wiki title convention as code: slug derivation, the
display-title -> canonical-title join, the story-page gate, the reverse join to
a wiki page path, and the table decoration from our own is_barks_title.
"""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_reader.core import wiki_integration
from barks_reader.core.reader_consts_and_types import (
    ACTION_BAR_BG_COLOR,
    ACTION_BAR_SEPARATOR_COLOR,
    RAW_ACTION_BAR_ICON_WIDTH,
    RAW_ACTION_BAR_SIZE_Y,
    RAW_QUIT_FENCE_WIDTH,
)
from barks_reader.core.reader_palette import color_to_markup_hex, theme
from barks_reader.core.wiki_integration import (
    BarksPanelsImageProvider,
    BarksTableRewriter,
    canonical_title,
    story_page_title,
    story_slug,
    title_can_have_wiki_page,
    tree_navigable_title,
    wiki_page_for_title,
    wiki_session_path,
    wiki_theme_spec,
    wiki_top_bar_spec,
)
from okf_reader.core.theme import ViewerThemeSpec
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path


class TestStorySlug:
    def test_apostrophes_dropped_not_hyphenated(self) -> None:
        """Map "You Can't Guess!" -> you-cant-guess (apostrophe removed, not a hyphen)."""
        assert story_slug("You Can't Guess!") == "you-cant-guess"

    def test_curly_apostrophe_dropped(self) -> None:
        """A typographic apostrophe (U+2019) behaves like a straight one."""
        title = f"Ten Cents{chr(0x2019)} Worth of Trouble"
        assert story_slug(title) == "ten-cents-worth-of-trouble"

    def test_non_alphanumerics_collapse_to_single_hyphen(self) -> None:
        """Quotes and spaces become one hyphen; leading/trailing hyphens stripped."""
        assert story_slug('Adventure "Down Under"') == "adventure-down-under"
        assert story_slug("Ten-Dollar Dither") == "ten-dollar-dither"


class TestCanonicalTitle:
    def test_exact_canonical_form(self) -> None:
        """A canonical title string maps straight to its enum."""
        assert canonical_title("Lost in the Andes!") == Titles.LOST_IN_THE_ANDES
        assert canonical_title("No Such Story Ever") is None

    def test_quoted_display_form_tolerated(self) -> None:
        """Straight or curly double quotes in a display form are stripped for the join."""
        canonical = ENUM_TO_STR_TITLE[Titles.ADVENTURE_DOWN_UNDER]
        quoted = canonical.replace("Down Under", '"Down Under"')
        assert canonical_title(quoted) == Titles.ADVENTURE_DOWN_UNDER
        curly = canonical.replace("Down Under", "“Down Under”")
        assert canonical_title(curly) == Titles.ADVENTURE_DOWN_UNDER


class TestStoryPageTitle:
    def test_story_page_maps_to_enum(self, tmp_path: Path) -> None:
        """A concept/stories page with a canonical frontmatter title is a story page."""
        page = tmp_path / "okf" / "concept" / "stories" / "comics-and-stories" / "x.md"
        fm = {"title": "Lost in the Andes!"}
        assert story_page_title(fm, page) == Titles.LOST_IN_THE_ANDES

    def test_non_story_location_is_none(self, tmp_path: Path) -> None:
        """The same frontmatter outside concept/stories/ is not a story page."""
        page = tmp_path / "okf" / "reference" / "x.md"
        assert story_page_title({"title": "Lost in the Andes!"}, page) is None

    def test_unknown_or_missing_title_is_none(self, tmp_path: Path) -> None:
        """A non-canonical or absent frontmatter title never matches."""
        page = tmp_path / "okf" / "concept" / "stories" / "misc" / "x.md"
        assert story_page_title({"title": "Not a Barks Story"}, page) is None
        assert story_page_title({}, page) is None


class TestStoryPageTitleExtras:
    def test_extras_title_is_still_a_story_page(self, tmp_path: Path) -> None:
        """An Extras title (in ALL_FANTA_COMIC_BOOK_INFO) still passes the plain gate."""
        page = tmp_path / "okf" / "concept" / "stories" / "one-pagers" / "x.md"
        assert story_page_title({"title": "All One-Pagers"}, page) == Titles.ALL_ONE_PAGERS


class TestTreeNavigableTitle:
    def test_non_extras_title_is_navigable(self, tmp_path: Path) -> None:
        """A regular story title keeps its tree position, so it passes."""
        page = tmp_path / "okf" / "concept" / "stories" / "comics-and-stories" / "x.md"
        assert (
            tree_navigable_title({"title": "Lost in the Andes!"}, page) == Titles.LOST_IN_THE_ANDES
        )

    def test_extras_title_is_excluded(self, tmp_path: Path) -> None:
        """An Extras title has no chronological tree position, so it is gated out."""
        page = tmp_path / "okf" / "concept" / "stories" / "one-pagers" / "x.md"
        # story_page_title accepts it, tree_navigable_title must not.
        assert story_page_title({"title": "All One-Pagers"}, page) == Titles.ALL_ONE_PAGERS
        assert tree_navigable_title({"title": "All One-Pagers"}, page) is None

    def test_non_story_page_is_none(self, tmp_path: Path) -> None:
        """A page outside concept/stories/ is never tree-navigable."""
        page = tmp_path / "okf" / "reference" / "x.md"
        assert tree_navigable_title({"title": "Lost in the Andes!"}, page) is None


class TestTitleCanHaveWikiPage:
    def test_true_for_series_with_story_dir(self) -> None:
        """A title whose series has a story directory can have a wiki page location."""
        assert title_can_have_wiki_page(Titles.LOST_IN_THE_ANDES) is True

    def test_false_for_extras_series(self) -> None:
        """An Extras title has no story directory, so no page location can exist."""
        assert title_can_have_wiki_page(Titles.ALL_ONE_PAGERS) is False


class TestWikiPageForTitle:
    def test_reverse_join_finds_written_page(self, tmp_path: Path) -> None:
        """A written story page is found via series dir + canonical slug."""
        slug_dir = tmp_path / "concept" / "stories" / "donald-duck-adventures"
        slug_dir.mkdir(parents=True)
        page = slug_dir / "lost-in-the-andes.md"
        page.write_text("---\ntype: story\n---\nX", encoding="utf-8")
        assert wiki_page_for_title(tmp_path, Titles.LOST_IN_THE_ANDES) == page

    def test_unwritten_page_is_none(self, tmp_path: Path) -> None:
        """A known title whose wiki page does not exist yet yields None."""
        assert wiki_page_for_title(tmp_path, Titles.LOST_IN_THE_ANDES) is None

    def test_gyro_title_found_in_fallback_misc_dir(self, tmp_path: Path) -> None:
        """A Gyro title filed under the second candidate dir ("misc") is still found."""
        # Gyro Gearloose story dirs are ("gyro-gearloose-stories", "misc"); the
        # page lives only in the fallback dir, so the first candidate misses.
        slug = story_slug(ENUM_TO_STR_TITLE[Titles.TRAPPED_LIGHTNING])
        fallback_dir = tmp_path / "concept" / "stories" / "misc"
        fallback_dir.mkdir(parents=True)
        page = fallback_dir / f"{slug}.md"
        page.write_text("X", encoding="utf-8")
        assert wiki_page_for_title(tmp_path, Titles.TRAPPED_LIGHTNING) == page


class TestWikiSessionPath:
    def test_name_is_keyed_by_bundle_digest(self, tmp_path: Path) -> None:
        """The session filename embeds a stable digest of the resolved bundle path."""
        app_data = tmp_path / "app"
        bundle = tmp_path / "okf-bundle"
        session = wiki_session_path(app_data, bundle)
        assert session.parent == app_data
        assert session.name.startswith("okf-reader-session-")
        assert session.suffix == ".json"
        # Stable across calls for the same bundle.
        assert wiki_session_path(app_data, bundle) == session

    def test_different_bundles_get_different_session_files(self, tmp_path: Path) -> None:
        """Opening a different bundle can never clobber another bundle's resume point."""
        app_data = tmp_path / "app"
        one = wiki_session_path(app_data, tmp_path / "bundle-a")
        two = wiki_session_path(app_data, tmp_path / "bundle-b")
        assert one != two


class TestBarksTableRewriter:
    def test_non_barks_title_parenthesized(self) -> None:
        """A non-Barks title in a Title column gains parentheses; Barks titles don't."""
        rewriter = BarksTableRewriter()
        non_barks = next(iter(rewriter._non_barks_titles))  # noqa: SLF001
        header, body = rewriter.rewrite(
            ["Title", "Date"], [[non_barks, "1944-06"], ["Lost in the Andes!", "1948-12"]]
        )
        assert header == ["Title", "Date"]
        assert body[0][0] == f"({non_barks})"
        assert body[1][0] == "Lost in the Andes!"

    def test_barks_flag_column_dropped_and_header_renamed(self) -> None:
        """The redundant "Barks?" column is dropped; "Issue date" renames to "Date"."""
        rewriter = BarksTableRewriter()
        header, body = rewriter.rewrite(
            ["Title", "Barks?", "Issue date"], [["Story A", "yes", "1944-06"]]
        )
        assert header == ["Title", "Date"]
        assert body == [["Story A", "1944-06"]]

    def test_wrap_widths_align_with_header(self) -> None:
        """Per-column wrap overrides align positionally; unknown columns get None."""
        rewriter = BarksTableRewriter()
        assert rewriter.wrap_widths(["Tag", "Story", "Title"]) == [20, 24, None]


class TestBarksPanelsImageProvider:
    @staticmethod
    def _make_provider(*, encrypted: bool) -> tuple[BarksPanelsImageProvider, MagicMock]:
        settings = MagicMock()
        settings.file_paths.barks_panels_are_encrypted = encrypted
        selector = MagicMock()
        return BarksPanelsImageProvider(settings, selector), selector

    def test_zip_panel_decoded_via_allow_listed_loader(self, tmp_path: Path) -> None:
        """A zip-member panel is decrypted through load_panel_pil and re-encoded to PNG.

        The decrypt must go through panel_image_loader (the compiled decryptor's
        caller allow-list), with the encrypted flag taken from the file paths.
        """
        zip_file = tmp_path / "panels.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("Favourites/x.jpg", b"encrypted-bytes")
        panel = zipfile.Path(zip_file, "Favourites/x.jpg")

        provider, selector = self._make_provider(encrypted=True)
        selector.get_random_image.return_value.filename = panel

        page = tmp_path / "okf" / "reference" / "x.md"
        pil = Image.new("RGB", (1, 1))
        with patch.object(wiki_integration, "load_panel_pil", return_value=pil) as mock_load:
            bg = provider.background_for({}, page)

        mock_load.assert_called_once_with(panel, encrypted_zip=True)
        assert bg is not None
        assert bg.ext == ".png"
        assert bg.path is None
        assert bg.data is not None
        assert bg.data.startswith(b"\x89PNG")

    def test_filesystem_panel_passed_through_by_path(self, tmp_path: Path) -> None:
        """A plain filesystem panel is handed to kivy by path, never decoded here."""
        panel = tmp_path / "panel.jpg"
        provider, selector = self._make_provider(encrypted=False)
        selector.get_random_image.return_value.filename = panel

        with patch.object(wiki_integration, "load_panel_pil") as mock_load:
            bg = provider.background_for({}, tmp_path / "okf" / "reference" / "x.md")

        mock_load.assert_not_called()
        assert bg is not None
        assert bg.path == panel
        assert bg.ext == ".jpg"
        assert bg.data is None

    def test_story_page_selects_title_specific_panel(self, tmp_path: Path) -> None:
        """A story page draws from that title's own panels."""
        panel = tmp_path / "panel.png"
        provider, selector = self._make_provider(encrypted=False)
        selector.get_random_image_for_title.return_value = panel

        page = tmp_path / "okf" / "concept" / "stories" / "donald-duck-adventures" / "x.md"
        bg = provider.background_for({"title": "Lost in the Andes!"}, page)

        selector.get_random_image_for_title.assert_called_once()
        selector.get_random_image.assert_not_called()
        assert bg is not None
        assert bg.path == panel

    def test_no_panel_found_is_none(self, tmp_path: Path) -> None:
        provider, selector = self._make_provider(encrypted=True)
        selector.get_random_image.return_value.filename = None

        assert provider.background_for({}, tmp_path / "okf" / "reference" / "x.md") is None


class TestWikiTopBarSpec:
    def test_routes_shared_action_bar_style(self, mock_font_manager: MagicMock) -> None:
        """The wiki bar's style single-sources from reader_consts_and_types.

        This is the anti-drift guard: the okf viewer renders whatever the spec
        carries, so these fields must be exactly the shared kv-bar constants.
        """
        spec = wiki_top_bar_spec(mock_font_manager, MagicMock())
        assert spec.title_color == theme().app_title
        assert spec.bg_color == ACTION_BAR_BG_COLOR
        assert spec.separator_color == ACTION_BAR_SEPARATOR_COLOR
        assert spec.icon_width == RAW_ACTION_BAR_ICON_WIDTH
        assert spec.quit_fence_width == RAW_QUIT_FENCE_WIDTH
        assert spec.height == RAW_ACTION_BAR_SIZE_Y


class TestWikiThemeSpec:
    def test_maps_active_palette_roles_onto_the_viewer(self) -> None:
        """The viewer spec single-sources from the app's active ReaderTheme.

        Anti-drift guard: the okf viewer renders whatever the spec carries, so
        these must be the reader_palette roles (not hardcoded okf defaults).
        """
        spec = wiki_theme_spec()
        title_hex = color_to_markup_hex(theme().text_title).lstrip("#")
        assert spec.selection == theme().accent_selection
        assert spec.title_text == theme().text_title
        assert spec.secondary_text == theme().text_secondary
        assert spec.row_stripe_even == theme().row_stripe_even
        assert spec.row_stripe_odd == theme().row_stripe_odd
        assert spec.focus_ring == theme().focus_ring
        assert spec.heading_hex == title_hex
        assert spec.title_hex == title_hex
        assert spec.crumb_hex == color_to_markup_hex(theme().text_secondary).lstrip("#")

    def test_links_and_dir_text_stay_the_viewer_defaults(self) -> None:
        """Hyperlinks keep the recognizable blue; directory rows stay white."""
        default = ViewerThemeSpec()
        spec = wiki_theme_spec()
        assert spec.link_hex == default.link_hex
        assert spec.dir_text == default.dir_text

    def test_hex_fields_carry_no_leading_hash(self) -> None:
        """render_page bakes hex straight into markup with no leading '#'."""
        spec = wiki_theme_spec()
        assert not spec.heading_hex.startswith("#")
        assert not spec.title_hex.startswith("#")
        assert not spec.crumb_hex.startswith("#")
