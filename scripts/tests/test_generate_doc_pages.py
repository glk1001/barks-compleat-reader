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


class TestHowToPages:
    def test_each_page_is_a_transparent_image_of_the_page_size(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n\n# Two\n\nMore.\n")
        out_dir = tmp_path / "out"

        written = how_to.build_pages(md_path, css_path, out_dir)

        assert [path.name for path in written] == ["page-1.png", "page-2.png"]
        for path in written:
            with Image.open(path) as page:
                assert page.mode == "RGBA"
                assert page.size == PAGE_SIZE
                assert page.getpixel((2, 2)) == TRANSPARENT
                assert page.getbbox() is not None  # the text is drawn

    def test_a_shorter_run_removes_the_pages_a_longer_one_left(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "One.\n")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "page-2.png").write_bytes(b"stale")
        (out_dir / "notes.txt").write_text("kept", encoding="utf-8")

        how_to.build_pages(md_path, css_path, out_dir)

        assert sorted(path.name for path in out_dir.iterdir()) == ["notes.txt", "page-1.png"]


class TestIntroPage:
    def test_the_text_is_laid_over_the_background_as_one_jpeg(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = tmp_path / "background.png"
        Image.new("RGB", PAGE_SIZE, BLUE).save(background)

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
        background = tmp_path / "background.png"
        Image.new("RGB", PAGE_SIZE, BLUE).save(background)

        with pytest.raises(intro.IntroPageError, match="takes 2"):
            intro.build_page(md_path, css_path, background, tmp_path / "out")

        assert not (tmp_path / "out").exists()

    def test_a_background_of_another_size_is_refused(self, tmp_path: Path) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = tmp_path / "background.png"
        Image.new("RGB", (100, 100), BLUE).save(background)

        with pytest.raises(intro.IntroPageError, match="100x100 and the page 200x300"):
            intro.build_page(md_path, css_path, background, tmp_path / "out")

    def test_the_command_reports_a_refusal_and_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")
        background = tmp_path / "background.png"
        Image.new("RGB", PAGE_SIZE, BLUE).save(background)

        with (
            patch.object(intro, "build_page", side_effect=intro.IntroPageError("too long")),
            pytest.raises(intro.typer.Exit),
        ):
            intro.main(md_path, css_path, background, tmp_path / "out")

        assert "too long" in capsys.readouterr().err

    def test_the_command_names_a_missing_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md_path, css_path = _sources(tmp_path, "Welcome.\n")

        with pytest.raises(intro.typer.Exit):
            intro.main(md_path, css_path, tmp_path / "no-such.png", tmp_path / "out")

        assert "no-such.png" in capsys.readouterr().err
