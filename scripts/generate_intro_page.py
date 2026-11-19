#!/usr/bin/env python
# ruff: noqa: T201

"""Generate the Reader's introduction page from ``docs/intro-to-barks-reader.md``.

Usage:
    uv run scripts/generate_intro_page.py
    uv run scripts/generate_intro_page.py --output-dir "/path/to/Reader Files/Various/documents/intro-to-barks-reader"

The markdown is laid out as the how-to's pages are (``generate_how_to_pages.py``,
whose renderer this uses), drawn over the background art and written as
``page-1.jpg``, 2120x3200 pixels: the finished page, with no image-editor step. The
default output directory is ``docs/intro-pages`` (gitignored); name the Reader's
``Various/documents/intro-to-barks-reader`` directory to replace the page the app shows.

The text must fit one page: a second is an error, not a second file. All styling —
margins, fonts, the drop cap, the sheet behind the text — lives in
``scripts/intro-style.css``.
"""  # noqa: E501

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from generate_how_to_pages import render_page_images
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MD = REPO_ROOT / "docs" / "intro-to-barks-reader.md"
DEFAULT_CSS = REPO_ROOT / "scripts" / "intro-style.css"
DEFAULT_BACKGROUND = REPO_ROOT / "docs" / "intro-to-barks-reader-bgnd.png"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "intro-pages"

PAGE_NAME = "page-1.jpg"
_JPEG_QUALITY = 92


class IntroPageError(Exception):
    """The introduction cannot be made into its one page."""


def build_page(md_path: Path, css_path: Path, background_path: Path, output_dir: Path) -> Path:
    """Render the markdown over the background art and write it as one JPEG.

    Args:
        md_path: Path to the introduction's markdown source.
        css_path: Path to the stylesheet controlling page size and typography.
        background_path: The art the text is laid over, of the stylesheet's page size.
        output_dir: Directory to write ``page-1.jpg`` into (created if absent).

    Returns:
        The path of the written page.

    Raises:
        IntroPageError: If the text does not fit one page, or the page and the
            background differ in size.

    """
    pages = render_page_images(md_path, css_path)
    if len(pages) != 1:
        msg = f"The introduction must fit one page, and it takes {len(pages)}."
        raise IntroPageError(msg)
    text = pages[0]

    with Image.open(background_path) as opened:
        background = opened.convert("RGBA")
    if background.size != text.size:
        msg = (
            f"The background is {background.size[0]}x{background.size[1]} and the page"
            f" {text.size[0]}x{text.size[1]}: they must be the same size."
        )
        raise IntroPageError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / PAGE_NAME
    Image.alpha_composite(background, text).convert("RGB").save(out_path, quality=_JPEG_QUALITY)
    return out_path


app = typer.Typer(add_completion=False)


@app.command()
def main(
    md: Annotated[Path, typer.Option(help="Markdown source file.")] = DEFAULT_MD,
    css: Annotated[
        Path, typer.Option(help="Stylesheet controlling page size and fonts.")
    ] = DEFAULT_CSS,
    background: Annotated[
        Path, typer.Option(help="The art the text is laid over.")
    ] = DEFAULT_BACKGROUND,
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory to write page-1.jpg into."),
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    """Generate the introduction page: its markdown over its background, as a JPEG."""
    for path in (md, css, background):
        if not path.is_file():
            typer.echo(f"File not found: {path}", err=True)
            raise typer.Exit(1)

    try:
        written = build_page(md, css, background, output_dir)
    except IntroPageError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    print(f"Wrote {written}")


if __name__ == "__main__":
    app()
