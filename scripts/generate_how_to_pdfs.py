#!/usr/bin/env python
# ruff: noqa: T201

"""Generate text-only PDF pages from ``docs/how-to-use.md`` for the GIMP how-to flow.

Usage:
    uv run scripts/generate_how_to_pdfs.py
    uv run scripts/generate_how_to_pdfs.py --output-dir "/path/to/gimp/import/dir"

The markdown is rendered (inline HTML, the action-bar icons, and the Settings
table included) and paginated by height into fixed-size pages. Each page is
written as a separate transparent-background PDF (``page-1.pdf``, ``page-2.pdf``,
...), so the count follows the content, matching how the pages flow across the
GIMP background layers.

Workflow: import the PDFs into the GIMP how-to project as the text layer over the
Barks backgrounds, then export the composited ``page-N.png`` files to the Reader's
``Various/documents/how-to`` directory.

All styling — page size, margins, serif fonts, table look — lives in
``scripts/how-to-style.css``. Edit that file to taste; no code changes needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from markdown_it import MarkdownIt
from weasyprint import CSS, HTML

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MD = REPO_ROOT / "docs" / "how-to-use.md"
DEFAULT_CSS = REPO_ROOT / "scripts" / "how-to-style.css"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "how-to-pdfs"

_HTML_TEMPLATE = (
    '<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head>\n<body>\n{body}\n</body></html>\n'
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


def build_pdfs(md_path: Path, css_path: Path, output_dir: Path) -> list[Path]:
    """Render the markdown to one transparent-background PDF per paginated page.

    Args:
        md_path: Path to the how-to markdown source. Its directory is used as the
            base URL so the ``icon-*.png`` references resolve.
        css_path: Path to the stylesheet controlling page size and typography.
        output_dir: Directory to write the ``page-N.pdf`` files into (created if
            absent).

    Returns:
        The written PDF paths, in page order.

    """
    html_doc = _HTML_TEMPLATE.format(body=render_markdown(md_path.read_text(encoding="utf-8")))

    document = HTML(string=html_doc, base_url=str(md_path.parent)).render(
        stylesheets=[CSS(filename=str(css_path))],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, page in enumerate(document.pages, start=1):
        out_path = output_dir / f"page-{index}.pdf"
        document.copy([page]).write_pdf(str(out_path))
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
        typer.Option(help="Directory to write the page-N.pdf files into."),
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    """Generate text-only PDF pages from the how-to markdown."""
    if not md.is_file():
        typer.echo(f"Markdown file not found: {md}", err=True)
        raise typer.Exit(1)
    if not css.is_file():
        typer.echo(f"CSS file not found: {css}", err=True)
        raise typer.Exit(1)

    written = build_pdfs(md, css, output_dir)
    print(f"Wrote {len(written)} page(s) to {output_dir}:")
    for path in written:
        print(f"  {path.name}")


if __name__ == "__main__":
    app()
