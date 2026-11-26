"""The how-to and introduction generators: markdown to page images.

WeasyPrint needs system libraries (Pango) that a Windows or macOS machine may not
have, and pypdfium2 is installed on Linux alone (``pyproject.toml``), where the
documents are only ever generated: without either the module is skipped.
"""

# cspell:ignore getbbox getcolors maxcolors

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from PIL import Image

try:
    import generate_how_to_pages as how_to
    import generate_intro_page as intro
except (ImportError, OSError) as error:  # pypdfium2 absent, or WeasyPrint's libraries
    pytest.skip(f"The document generators cannot be imported: {error}", allow_module_level=True)

if TYPE_CHECKING:
    from pathlib import Path

PAGE_SIZE = (200, 300)
TRANSPARENT = (0, 0, 0, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
PAGE_CSS = (
    "@page { size: 200px 300px; margin: 20px; }\nbody { font-size: 12px; }\n"
    "h1 { break-before: page; }\n"
)


def _sources(tmp_path: Path, markdown: str) -> tuple[Path, Path]:
    md_path = tmp_path / "doc.md"
    md_path.write_text(markdown, encoding="utf-8")
    css_path = tmp_path / "style.css"
    css_path.write_text(PAGE_CSS, encoding="utf-8")
    return md_path, css_path


def _near(pixel: object, colour: tuple[int, int, int], within: int = 6) -> bool:
    """Whether a pixel of a JPEG is the colour it was saved as, give or take."""
    assert isinstance(pixel, tuple)
    return all(abs(got - want) <= within for got, want in zip(pixel, colour, strict=True))


def _background(tmp_path: Path, size: tuple[int, int] = PAGE_SIZE) -> Path:
    background = tmp_path / "background.png"
    Image.new("RGB", size, BLUE).save(background)
    return background


class TestHowToCommand:
    def test_it_says_what_it_wrote(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n")
        background = _background(tmp_path)

        how_to.main(md_path, css_path, tmp_path / "out", [background, background])

        out = capsys.readouterr().out.splitlines()
        assert out == [f"Wrote 2 page(s) to {tmp_path / 'out'}:", "  page-1.jpg", "  page-2.jpg"]

    def test_with_no_background_named_the_listed_ones_are_used(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")
        listed = [_background(tmp_path)]

        with (
            patch.object(how_to, "how_to_background_paths", return_value=listed),
            patch.object(how_to, "build_pages", return_value=[]) as build,
        ):
            how_to.main(md_path, css_path, tmp_path / "out")

        build.assert_called_once_with(md_path, css_path, listed, tmp_path / "out")

    @pytest.mark.parametrize(
        ("missing", "says"),
        [("doc.md", "Markdown file not found"), ("style.css", "CSS file not found")],
    )
    def test_a_missing_source_is_named_and_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], missing: str, says: str
    ) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")
        (tmp_path / missing).unlink()

        with pytest.raises(how_to.typer.Exit) as refused:
            how_to.main(md_path, css_path, tmp_path / "out", [_background(tmp_path)])

        assert refused.value.exit_code == 1
        assert f"{says}: {tmp_path / missing}" in capsys.readouterr().err
        assert not (tmp_path / "out").exists()

    def test_a_refusal_is_reported_and_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n")

        with pytest.raises(how_to.typer.Exit) as refused:
            how_to.main(md_path, css_path, tmp_path / "out", [_background(tmp_path)])

        assert refused.value.exit_code == 1
        assert "takes 2 pages and there are 1 backgrounds" in capsys.readouterr().err


class TestHowToPages:
    def test_each_page_is_its_text_over_its_background_stretched_to_the_page(
        self, tmp_path: Path
    ) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n\nMore.\n")
        blue = _background(tmp_path, (100, 100))
        red = tmp_path / "red.png"
        Image.new("RGB", PAGE_SIZE, RED).save(red)

        written = how_to.build_pages(md_path, css_path, [blue, red, blue], tmp_path / "out")

        assert [path.name for path in written] == ["page-1.jpg", "page-2.jpg"]
        for path, art in zip(written, (BLUE, RED), strict=True):
            with Image.open(path) as page:
                assert page.mode == "RGB"
                assert page.size == PAGE_SIZE
                for corner in ((2, 2), (197, 297)):  # the margins: the art alone
                    assert _near(page.getpixel(corner), art)
                assert len(page.getcolors(maxcolors=100_000) or [None, None]) > 1  # text too

    def test_a_shorter_run_removes_the_pages_a_longer_one_left(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "page-2.jpg").write_bytes(b"stale")
        (out_dir / "page-1.png").write_bytes(b"an earlier version's text page")
        (out_dir / "notes.txt").write_text("kept", encoding="utf-8")

        how_to.build_pages(md_path, css_path, [_background(tmp_path)], out_dir)

        assert sorted(path.name for path in out_dir.iterdir()) == ["notes.txt", "page-1.jpg"]

    def test_more_pages_than_backgrounds_is_refused_and_nothing_is_touched(
        self, tmp_path: Path
    ) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "page-1.jpg").write_bytes(b"the page shown now")

        with pytest.raises(how_to.HowToPagesError, match="takes 2 pages and there are 1"):
            how_to.build_pages(md_path, css_path, [_background(tmp_path)], out_dir)

        assert (out_dir / "page-1.jpg").read_bytes() == b"the page shown now"

    def test_a_background_that_is_not_there_is_named(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")

        with pytest.raises(how_to.HowToPagesError, match=r"Background not found: .*gone\.jpg"):
            how_to.build_pages(md_path, css_path, [tmp_path / "gone.jpg"], tmp_path / "out")

        assert not (tmp_path / "out").exists()

    def test_a_background_no_page_uses_need_not_be_there(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")
        backgrounds = [_background(tmp_path), tmp_path / "gone.jpg"]

        written = how_to.build_pages(md_path, css_path, backgrounds, tmp_path / "out")

        assert [path.name for path in written] == ["page-1.jpg"]


class TestLayTextOver:
    def test_opaque_text_hides_the_art_and_none_shows_it(self) -> None:
        text = Image.new("RGBA", (2, 1), TRANSPARENT)
        text.putpixel((0, 0), (*RED, 255))

        page = how_to.lay_text_over(Image.new("RGB", (2, 1), BLUE), text)

        assert page.mode == "RGB"
        assert [page.getpixel((0, 0)), page.getpixel((1, 0))] == [RED, BLUE]

    def test_a_translucent_sheet_is_blended_in_linear_light(self) -> None:
        """Half white over black is 188 in linear light; blended as encoded it is 128."""
        text = Image.new("RGBA", (1, 1), (255, 255, 255, 128))

        page = how_to.lay_text_over(Image.new("RGB", (1, 1), (0, 0, 0)), text)

        assert page.getpixel((0, 0)) == (188, 188, 188)


class TestIntroPage:
    def test_the_text_is_laid_over_the_background_as_one_jpeg(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = _background(tmp_path)

        written = intro.build_page(md_path, css_path, background, tmp_path / "out")

        assert written.name == "page-1.jpg"
        with Image.open(written) as page:
            assert page.mode == "RGB"
            assert page.size == PAGE_SIZE
            margin = page.crop((0, 0, 10, 10)).getcolors()  # a margin: the art alone
            assert margin is not None
            assert {color for _count, color in margin} <= {(0, 0, 254), BLUE, (1, 0, 255)}
            assert len(page.getcolors(maxcolors=100_000) or [None, None]) > 1  # text too

    def test_text_that_takes_a_second_page_is_refused(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n")
        background = _background(tmp_path)

        with pytest.raises(intro.IntroPageError, match="takes 2"):
            intro.build_page(md_path, css_path, background, tmp_path / "out")

        assert not (tmp_path / "out").exists()

    def test_a_background_of_another_size_is_refused(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = _background(tmp_path, (100, 100))

        with pytest.raises(intro.IntroPageError, match="100x100 and the page 200x300"):
            intro.build_page(md_path, css_path, background, tmp_path / "out")

    def test_the_command_reports_a_refusal_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = _background(tmp_path)

        with (
            patch.object(intro, "build_page", side_effect=intro.IntroPageError("too long")),
            pytest.raises(intro.typer.Exit) as refused,
        ):
            intro.main(md_path, css_path, background, tmp_path / "out")

        assert refused.value.exit_code == 1
        assert "too long" in capsys.readouterr().err

    def test_the_command_names_a_missing_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")

        with pytest.raises(intro.typer.Exit) as refused:
            intro.main(md_path, css_path, tmp_path / "no-such.png", tmp_path / "out")

        assert refused.value.exit_code == 1
        assert "no-such.png" in capsys.readouterr().err
