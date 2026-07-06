"""Tests for the kivy-free background-image selection (okf_reader.core.backgrounds)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from okf_reader.core import backgrounds as bg

if TYPE_CHECKING:
    from pathlib import Path


def _make_favourites(tmp_path: Path) -> Path:
    """Two title directories plus a stray non-image file."""
    root = tmp_path / "Favourites"
    fable = root / "A Financial Fable"
    fable.mkdir(parents=True)
    (fable / "094-1.png").touch()
    (fable / "094-2.jpg").touch()
    (fable / "notes.txt").touch()  # not an image
    andes = root / "Lost in the Andes!"
    andes.mkdir()
    (andes / "square-eggs.png").touch()
    return root


def _background_name(provider: bg.DirPerTitleImageProvider, frontmatter: dict, page: Path) -> str:
    background = provider.background_for(frontmatter, page)
    assert background is not None
    assert background.path is not None
    assert background.data is None
    assert background.ext == background.path.suffix
    return background.path.name


class TestDirPerTitleImageProvider:
    def test_title_match_returns_only_that_directory(self, tmp_path: Path) -> None:
        """A matching frontmatter title yields one of that title's images, images only."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        for _ in range(20):
            name = _background_name(provider, {"title": "A Financial Fable"}, tmp_path / "p.md")
            assert name in ("094-1.png", "094-2.jpg")

    def test_title_with_filesystem_unsafe_chars_matches_stripped_dir(self, tmp_path: Path) -> None:
        """Quotes/question marks absent from directory names still match.

        The Barks panels tree drops them: 'Adventure "Down Under"' lives in
        "Adventure Down Under", "Want to Buy an Island?" loses its "?".
        """
        root = tmp_path / "Favourites"
        (root / "Adventure Down Under").mkdir(parents=True)
        (root / "Adventure Down Under" / "panel.png").touch()
        (root / "Want to Buy an Island").mkdir()
        (root / "Want to Buy an Island" / "island.png").touch()
        provider = bg.DirPerTitleImageProvider(root)
        quoted = _background_name(provider, {"title": 'Adventure "Down Under"'}, tmp_path / "p.md")
        assert quoted == "panel.png"
        question = _background_name(
            provider, {"title": "Want to Buy an Island?"}, tmp_path / "p.md"
        )
        assert question == "island.png"

    def test_unmatched_title_falls_back_to_all_images(self, tmp_path: Path) -> None:
        """A page with no matching title directory draws from the whole pool."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        seen = {
            _background_name(provider, {"title": "Donald Duck"}, tmp_path / "p.md")
            for _ in range(50)
        }
        assert seen <= {"094-1.png", "094-2.jpg", "square-eggs.png"}
        assert "square-eggs.png" in seen  # pool, not just one title's directory

    def test_missing_title_key_falls_back(self, tmp_path: Path) -> None:
        """No frontmatter title at all also draws from the fallback pool."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        name = _background_name(provider, {}, tmp_path / "p.md")
        assert name in ("094-1.png", "094-2.jpg", "square-eggs.png")

    def test_missing_root_returns_none(self, tmp_path: Path) -> None:
        """A nonexistent root yields no background, not an error."""
        provider = bg.DirPerTitleImageProvider(tmp_path / "nowhere")
        assert provider.background_for({"title": "X"}, tmp_path / "p.md") is None

    def test_empty_title_directory_falls_back(self, tmp_path: Path) -> None:
        """A matching title directory with no images falls back to the pool."""
        root = _make_favourites(tmp_path)
        (root / "Empty Story").mkdir()
        provider = bg.DirPerTitleImageProvider(root)
        name = _background_name(provider, {"title": "Empty Story"}, tmp_path / "p.md")
        assert name in ("094-1.png", "094-2.jpg", "square-eggs.png")

    def test_avoids_immediate_repeat(self, tmp_path: Path) -> None:
        """Consecutive calls never return the same image while alternatives exist."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        page = tmp_path / "p.md"
        frontmatter = {"title": "A Financial Fable"}  # two candidate images
        last = _background_name(provider, frontmatter, page)
        for _ in range(20):
            name = _background_name(provider, frontmatter, page)
            assert name != last
            last = name


class TestChooseImage:
    def test_empty_candidates_gives_none(self) -> None:
        """No candidates, no image."""
        assert bg.choose_image([], None) is None

    def test_avoids_last_when_alternatives_exist(self, tmp_path: Path) -> None:
        """The previous image is not repeated while other candidates remain."""
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        for _ in range(20):
            assert bg.choose_image([a, b], last=a) == b

    def test_single_candidate_returned_even_if_last(self, tmp_path: Path) -> None:
        """With only one candidate, repeating it beats showing nothing."""
        a = tmp_path / "a.png"
        assert bg.choose_image([a], last=a) == a
