#!/usr/bin/env python
# ruff: noqa: T201

"""Generate the how-to's text pages from ``docs/how-to-use.md`` for the GIMP how-to flow.

Usage:
    uv run scripts/generate_how_to_pages.py
    uv run scripts/generate_how_to_pages.py --output-dir "/path/to/gimp/import/dir"

The markdown is rendered (inline HTML, the icons, the screenshots and the tables
included) and paginated by height into fixed-size pages. Each page is written as
a separate transparent-background PNG (``page-1.png``, ``page-2.png``, ...), 2120x3200
pixels as the stylesheet's page size has it, so the count follows the content,
matching how the pages flow across the GIMP background layers. Pages left in the
output directory by an earlier, longer run are removed.

Workflow: open the PNGs in the GIMP how-to project as the text layer over the
Barks backgrounds, then export the composited ``page-N.png`` files to the Reader's
``Various/documents/how-to`` directory.
Then ``uv run scripts/generated_files.py --record how-to`` and commit
the record: the corpus validator reports the pages as stale from the moment the
markdown, the stylesheet or a picture changes until that is done.

All styling — page size, margins, fonts, colours, boxes, table look — lives in
``scripts/how-to-style.css``. Edit that file to taste; no code changes needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import pypdfium2
import typer
from markdown_it import MarkdownIt
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

if TYPE_CHECKING:
    from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MD = REPO_ROOT / "docs" / "how-to-use.md"
DEFAULT_CSS = REPO_ROOT / "scripts" / "how-to-style.css"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "how-to-pages"

# A CSS pixel is 1/96 inch and a PDF point 1/72, so this renders one image pixel per CSS
# pixel: the stylesheet's 2120x3200 px page comes out 2120x3200.
_PIXELS_PER_POINT = 96 / 72

# The language is for a stylesheet that hyphenates (`hyphens: auto` needs one to go by).
_HTML_TEMPLATE = (
    '<!DOCTYPE html>\n<html lang="en-GB"><head><meta charset="utf-8"></head>\n'
    "<body>\n{body}\n</body></html>\n"
)


def render_markdown(md_text: str) -> str:
    """Render the how-to markdown to an HTML body fragment.

    Uses the ``gfm-like`` preset for the GFM Settings table and passes inline
    HTML (the styled ``<h1>`` and the action-bar ``<img>`` icons) straight
    through. ``linkify`` is disabled because ``linkify-it-py`` is not a
    dependency and the document has no bare URLs.

    Args:
        md_text: The raw markdown source.

    Returns:
        The rendered HTML fragment (body content only).

    """
    parser = MarkdownIt("gfm-like", {"html": True}).disable("linkify")
    return parser.render(md_text)


def render_page_images(md_path: Path, css_path: Path) -> list[Image.Image]:
    """Lay the markdown out in pages and draw each as a transparent-background image.

    Args:
        md_path: Path to the markdown source. Its directory is used as the base URL
            so the image references in it resolve.
        css_path: Path to the stylesheet controlling page size and typography.

    Returns:
        The pages in order, each an RGBA image of the stylesheet's page size in pixels.

    """
    html_doc = _HTML_TEMPLATE.format(body=render_markdown(md_path.read_text(encoding="utf-8")))

    # The stylesheet's @font-face rules load only through a shared font configuration.
    font_config = FontConfiguration()
    pdf_bytes = HTML(string=html_doc, base_url=str(md_path.parent)).write_pdf(
        stylesheets=[CSS(filename=str(css_path), font_config=font_config)],
        font_config=font_config,
    )
    assert pdf_bytes is not None  # write_pdf returns the bytes when given no target

    pdf = pypdfium2.PdfDocument(pdf_bytes)
    try:
        return [
            pdf[index]
            .render(scale=_PIXELS_PER_POINT, fill_color=(0, 0, 0, 0), maybe_alpha=True)
            .to_pil()
            .convert("RGBA")
            for index in range(len(pdf))
        ]
    finally:
        pdf.close()


def build_pages(md_path: Path, css_path: Path, output_dir: Path) -> list[Path]:
    """Render the markdown to one transparent-background PNG per paginated page.

    Args:
        md_path: Path to the how-to markdown source. Its directory is used as the
            base URL so the ``icon-*.png`` and screenshot references resolve.
        css_path: Path to the stylesheet controlling page size and typography.
        output_dir: Directory to write the ``page-N.png`` files into (created if
            absent; its earlier ``page-N.png`` files are removed first).

    Returns:
        The written PNG paths, in page order.

    """
    pages = render_page_images(md_path, css_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("page-*.png"):
        stale.unlink()

    written: list[Path] = []
    for number, page in enumerate(pages, start=1):
        out_path = output_dir / f"page-{number}.png"
        page.save(out_path)
        written.append(out_path)
    return written


app = typer.Typer(add_completion=False)


@app.command()
def main(
    md: Annotated[Path, typer.Option(help="Markdown source file.")] = DEFAULT_MD,
    css: Annotated[
        Path, typer.Option(help="Stylesheet controlling page size and fonts.")
    ] = DEFAULT_CSS,
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory to write the page-N.png files into."),
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    """Generate the how-to's transparent PNG text pages from its markdown."""
    if not md.is_file():
        typer.echo(f"Markdown file not found: {md}", err=True)
        raise typer.Exit(1)
    if not css.is_file():
        typer.echo(f"CSS file not found: {css}", err=True)
        raise typer.Exit(1)

    written = build_pages(md, css, output_dir)
    print(f"Wrote {len(written)} page(s) to {output_dir}:")
    for path in written:
        print(f"  {path.name}")


if __name__ == "__main__":
    app()
