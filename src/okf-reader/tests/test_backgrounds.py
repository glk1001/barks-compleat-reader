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


class TestDirPerTitleImageProvider:
    def test_title_match_returns_only_that_directory(self, tmp_path: Path) -> None:
        """A matching frontmatter title yields that title's images, images only."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        images = provider.candidate_images({"title": "A Financial Fable"}, tmp_path / "p.md")
        assert [p.name for p in images] == ["094-1.png", "094-2.jpg"]

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
        quoted = provider.candidate_images({"title": 'Adventure "Down Under"'}, tmp_path / "p.md")
        assert [p.name for p in quoted] == ["panel.png"]
        question = provider.candidate_images({"title": "Want to Buy an Island?"}, tmp_path / "p.md")
        assert [p.name for p in question] == ["island.png"]

    def test_unmatched_title_falls_back_to_all_images(self, tmp_path: Path) -> None:
        """A page with no matching title directory gets the whole pool."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        images = provider.candidate_images({"title": "Donald Duck"}, tmp_path / "p.md")
        assert sorted(p.name for p in images) == ["094-1.png", "094-2.jpg", "square-eggs.png"]

    def test_missing_title_key_falls_back(self, tmp_path: Path) -> None:
        """No frontmatter title at all also gets the fallback pool."""
        provider = bg.DirPerTitleImageProvider(_make_favourites(tmp_path))
        images = provider.candidate_images({}, tmp_path / "p.md")
        assert sorted(p.name for p in images) == ["094-1.png", "094-2.jpg", "square-eggs.png"]

    def test_missing_root_returns_empty(self, tmp_path: Path) -> None:
        """A nonexistent root yields no candidates, not an error."""
        provider = bg.DirPerTitleImageProvider(tmp_path / "nowhere")
        assert provider.candidate_images({"title": "X"}, tmp_path / "p.md") == []

    def test_empty_title_directory_falls_back(self, tmp_path: Path) -> None:
        """A matching title directory with no images falls back to the pool."""
        root = _make_favourites(tmp_path)
        (root / "Empty Story").mkdir()
        provider = bg.DirPerTitleImageProvider(root)
        images = provider.candidate_images({"title": "Empty Story"}, tmp_path / "p.md")
        assert sorted(p.name for p in images) == ["094-1.png", "094-2.jpg", "square-eggs.png"]


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
