#!/usr/bin/env python
# ruff: noqa: T201

"""Generate the Reader's how-to pages from ``docs/how-to-use.md``.

Usage:
    uv run scripts/generate_how_to_pages.py
    uv run scripts/generate_how_to_pages.py --output-dir "/path/to/Reader Files/Various/documents/how-to"

The markdown is rendered (inline HTML, the icons, the screenshots and the tables
included) and paginated by height into fixed-size pages, 2120x3200 pixels as the
stylesheet's page size has it, so the count follows the content. Each page's text is
laid over its background art and written as ``page-1.jpg``, ``page-2.jpg``, ...: the
finished pages, with no image-editor step. Pages left in the output directory by an
earlier, longer run are removed.

The backgrounds are extra art in the Fantagraphics volumes' fixes directories, listed
in page order in ``scripts/how_to_backgrounds.py`` and stretched to the page size.
A how-to of more pages than there are backgrounds is an error: list another.
``--background``, once per page, uses other files instead.

The default output directory is ``docs/how-to-pages`` (gitignored); name the Reader's
``Various/documents/how-to`` directory to replace the pages the app shows. After
replacing them, ``uv run scripts/generated_files.py --record how-to`` and commit the
record: the corpus validator reports the pages as stale from the moment the markdown,
the stylesheet, a picture or a background changes until that is done.

All styling — page size, margins, fonts, colours, boxes, table look — lives in
``scripts/how-to-style.css``. Edit that file to taste; no code changes needed.
"""  # noqa: E501

# cspell:ignore fromarray rint srgb

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import numpy as np
import pypdfium2
import typer
from how_to_backgrounds import how_to_background_paths
from markdown_it import MarkdownIt
from PIL import Image
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MD = REPO_ROOT / "docs" / "how-to-use.md"
DEFAULT_CSS = REPO_ROOT / "scripts" / "how-to-style.css"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "how-to-pages"

# A CSS pixel is 1/96 inch and a PDF point 1/72, so this renders one image pixel per CSS
# pixel: the stylesheet's 2120x3200 px page comes out 2120x3200.
_PIXELS_PER_POINT = 96 / 72

_JPEG_QUALITY = 92
# Where the sRGB curve's straight toe meets its power curve, encoded and linear.
_SRGB_TOE = 0.04045
_LINEAR_TOE = 0.0031308
_PAGE_GLOBS = ("page-*.jpg", "page-*.png")  # the PNGs are an earlier version's text pages


class HowToPagesError(Exception):
    """The how-to cannot be made into its pages."""


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


def _to_linear(srgb: np.ndarray) -> np.ndarray:
    return np.where(srgb <= _SRGB_TOE, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def _to_srgb(linear: np.ndarray) -> np.ndarray:
    return np.where(linear <= _LINEAR_TOE, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def lay_text_over(background: Image.Image, text: Image.Image) -> Image.Image:
    """Lay a page's text over its background art, blending in linear light.

    The pages were first put together in GIMP, which blends layers in linear light,
    and the stylesheet's translucent sheet was chosen by eye there: blended in sRGB
    (as ``Image.alpha_composite`` does) the art shows through it darker.

    Args:
        background: The art, of the text's size.
        text: The page's text, transparent where there is none.

    Returns:
        The finished page, opaque, ready to be saved as a JPEG.

    """
    over = np.asarray(text.convert("RGBA"), dtype=np.float32) / 255
    under = np.asarray(background.convert("RGB"), dtype=np.float32) / 255
    alpha = over[..., 3:]
    blended = _to_linear(over[..., :3]) * alpha + _to_linear(under) * (1 - alpha)
    pixels = np.rint(_to_srgb(np.clip(blended, 0, 1)) * 255).astype(np.uint8)
    return Image.fromarray(pixels, "RGB")


def build_pages(
    md_path: Path, css_path: Path, backgrounds: list[Path], output_dir: Path
) -> list[Path]:
    """Render the markdown to one finished JPEG per paginated page.

    Args:
        md_path: Path to the how-to markdown source. Its directory is used as the
            base URL so the ``icon-*.png`` and screenshot references resolve.
        css_path: Path to the stylesheet controlling page size and typography.
        backgrounds: The art for each page, in page order; each is stretched to the
            page size. Ones past the last page are not used.
        output_dir: Directory to write the ``page-N.jpg`` files into (created if
            absent; its earlier page files are removed first).

    Returns:
        The written paths, in page order.

    Raises:
        HowToPagesError: If there are more pages than backgrounds, or a background a
            page needs is not there. Nothing is written or removed.

    """
    pages = render_page_images(md_path, css_path)
    if len(pages) > len(backgrounds):
        msg = (
            f"The how-to takes {len(pages)} pages and there are {len(backgrounds)}"
            " backgrounds: list another in scripts/how_to_backgrounds.py."
        )
        raise HowToPagesError(msg)
    used = backgrounds[: len(pages)]
    missing = [path for path in used if not path.is_file()]
    if missing:
        msg = "Background not found: " + ", ".join(f'"{path}"' for path in missing)
        raise HowToPagesError(msg)

    finished: list[Image.Image] = []
    for text, background_path in zip(pages, used, strict=True):
        with Image.open(background_path) as opened:
            art = opened.convert("RGB").resize(text.size, Image.Resampling.LANCZOS)
        finished.append(lay_text_over(art, text))

    output_dir.mkdir(parents=True, exist_ok=True)
    for glob in _PAGE_GLOBS:
        for stale in output_dir.glob(glob):
            stale.unlink()

    written: list[Path] = []
    for number, page in enumerate(finished, start=1):
        out_path = output_dir / f"page-{number}.jpg"
        page.save(out_path, quality=_JPEG_QUALITY)
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
        typer.Option(help="Directory to write the page-N.jpg files into."),
    ] = DEFAULT_OUTPUT_DIR,
    background: Annotated[
        list[Path] | None,
        typer.Option(help="The art for a page, once per page in order, in place of the listed."),
    ] = None,
) -> None:
    """Generate the how-to's pages: its markdown over each page's background, as JPEGs."""
    if not md.is_file():
        typer.echo(f"Markdown file not found: {md}", err=True)
        raise typer.Exit(1)
    if not css.is_file():
        typer.echo(f"CSS file not found: {css}", err=True)
        raise typer.Exit(1)

    try:
        written = build_pages(md, css, background or how_to_background_paths(), output_dir)
    except HowToPagesError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    print(f"Wrote {len(written)} page(s) to {output_dir}:")
    for path in written:
        print(f"  {path.name}")


if __name__ == "__main__":
    app()
