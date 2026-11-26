#!/usr/bin/env python3
"""Render the Reader's icons from their SVG sources, into Reader Files and the how-to.

Every icon the app loads is drawn as an SVG in ``assets/reader-icon-sources``: a white
glyph on a transparent ground, which the app tints, or a picture in its own colours.
The PNGs the app reads are in Reader Files, which is data and not in the repo, and the
how-to (``docs/how-to-use.md``) shows the same icons in black beside its text. Both are
rendered from the one source here, with Inkscape:

  uv run scripts/render_reader_icons.py             # render them all, into both places
  uv run scripts/render_reader_icons.py --list      # say where each source goes

After rendering, ``uv run scripts/generated_files.py --record icons`` and commit the
record with the how-to's PNGs: the corpus validator reports the installed icons as
stale from the moment an SVG changes until that is done. The how-to's pages show the
icons too, so they are regenerated after (``generate_how_to_pages.py``).

A new icon is a new SVG and a line in ``ICONS``. A test holds the table to the app's
own list of the icons it needs (``core/system_file_paths.py``).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "assets" / "reader-icon-sources"
HOW_TO_DIR = REPO_ROOT / "docs"

SIZE = 512
WHITE = "#ffffff"
BLACK = "#000000"

_ACTION_BAR = "Reader Icons/ActionBar Icons"
_VARIOUS = "Various"


class IconRenderError(Exception):
    """An icon cannot be rendered."""


@dataclass(frozen=True, slots=True)
class Icon:
    """One SVG source and the PNGs made from it.

    Attributes:
        svg: The source's file name in ``assets/reader-icon-sources``.
        installed: The app's PNG, from the Reader Files folder; None for an icon the
            app draws itself, which only the how-to needs as a picture.
        how_to: The how-to's PNG in ``docs``, its white glyph turned black; None for
            an icon the how-to does not show.

    """

    svg: str
    installed: str | None = None
    how_to: str | None = None


ICONS: tuple[Icon, ...] = (
    Icon("icon-back-arrow.svg", f"{_ACTION_BAR}/icon-back-arrow.png", "icon-back-arrow.png"),
    Icon("icon-close.svg", f"{_ACTION_BAR}/icon-close.png", "icon-close.png"),
    Icon("icon-collapse.svg", f"{_ACTION_BAR}/icon-collapse.png", "icon-collapse.png"),
    Icon("icon-contrast-off.svg", f"{_ACTION_BAR}/icon-contrast-off.png"),
    Icon("icon-contrast-on.svg", f"{_ACTION_BAR}/icon-contrast-on.png"),
    Icon("icon-double-page.svg", f"{_ACTION_BAR}/icon-double-page.png", "icon-double-page.png"),
    Icon("icon-fullscreen-exit.svg", f"{_ACTION_BAR}/icon-fullscreen-exit.png"),
    Icon("icon-fullscreen.svg", f"{_ACTION_BAR}/icon-fullscreen.png", "icon-fullscreen.png"),
    Icon("icon-goto-end.svg", f"{_ACTION_BAR}/icon-goto-end.png", "icon-goto-end.png"),
    Icon("icon-goto-start.svg", f"{_ACTION_BAR}/icon-goto-start.png", "icon-goto-start.png"),
    Icon("icon-goto-title.svg", f"{_ACTION_BAR}/icon-goto-title.png"),
    Icon("icon-goto.svg", f"{_ACTION_BAR}/icon-goto.png", "icon-goto.png"),
    Icon("icon-menu-dots.svg", f"{_ACTION_BAR}/icon-menu-dots.png", "icon-menu-dots.png"),
    Icon("icon-power.svg", f"{_ACTION_BAR}/icon-power.png", "icon-power.png"),
    Icon(
        "icon-refresh-arrow.svg",
        f"{_ACTION_BAR}/icon-refresh-arrow.png",
        "icon-refresh-arrow.png",
    ),
    Icon("icon-search.svg", f"{_ACTION_BAR}/icon-search.png", "icon-search.png"),
    Icon("icon-single-page.svg", f"{_ACTION_BAR}/icon-single-page.png"),
    Icon("menu-hamburger-icon.svg", f"{_ACTION_BAR}/menu-hamburger-icon.png"),
    Icon(
        "goto-title-button.svg", f"{_VARIOUS}/goto-title-button.png", "icon-goto-title-button.png"
    ),
    Icon("icon-eye-off.svg", f"{_VARIOUS}/icon-eye-off.png"),
    Icon("icon-eye-open.svg", f"{_VARIOUS}/icon-eye-open.png", "icon-eye-open.png"),
    Icon("speech-bubble-icon.svg", f"{_VARIOUS}/speech-bubble-icon.png", "icon-speech-bubble.png"),
    # Drawn by the app itself, so only the how-to needs a picture of them.
    Icon("how-to-filter-button.svg", how_to="icon-filter-button.png"),
    Icon("how-to-read-dot-full.svg", how_to="icon-read-dot-full.png"),
    Icon("how-to-read-dot-half.svg", how_to="icon-read-dot-half.png"),
)


def source_paths(icons: tuple[Icon, ...] = ICONS) -> list[Path]:
    """Return every icon's SVG source."""
    return [SOURCES_DIR / icon.svg for icon in icons]


def installed_paths(reader_files_dir: Path, icons: tuple[Icon, ...] = ICONS) -> list[Path]:
    """Return the PNGs the app reads, in a Reader Files folder."""
    return [reader_files_dir / icon.installed for icon in icons if icon.installed is not None]


def black_glyph(svg_text: str, name: str) -> str:
    """Turn a source's white glyph black, for the how-to's pale page.

    Args:
        svg_text: The SVG source.
        name: The source's name, for the error.

    Returns:
        The SVG with its white drawn black. A picture with no white is returned as it is.

    Raises:
        IconRenderError: The source draws in black as well as white, so the two would
            run together.

    """
    if WHITE not in svg_text:
        return svg_text
    if BLACK in svg_text:
        msg = f"{name} draws in black as well as white: it cannot be shown black in the how-to."
        raise IconRenderError(msg)
    return svg_text.replace(WHITE, BLACK)


def render_png(svg_path: Path, png_path: Path) -> None:
    """Render one SVG to a square PNG with Inkscape.

    Args:
        svg_path: The SVG to render.
        png_path: The PNG to write (its folder must exist).

    Raises:
        IconRenderError: Inkscape failed, or wrote nothing.

    """
    done = subprocess.run(  # noqa: S603
        [
            _inkscape(),
            str(svg_path),
            "--export-type=png",
            f"--export-filename={png_path}",
            "-w",
            str(SIZE),
            "-h",
            str(SIZE),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0 or not png_path.is_file():
        msg = f"Inkscape could not render {svg_path.name}: {done.stderr.strip()}"
        raise IconRenderError(msg)


def _inkscape() -> str:
    found = shutil.which("inkscape")
    if found is None:
        msg = "Inkscape is not installed (sudo apt install inkscape)."
        raise IconRenderError(msg)
    return found


def render_all(
    reader_files_dir: Path,
    how_to_dir: Path = HOW_TO_DIR,
    sources_dir: Path = SOURCES_DIR,
    icons: tuple[Icon, ...] = ICONS,
) -> list[Path]:
    """Render every icon into Reader Files and the how-to's folder.

    Everything is rendered to a scratch folder first, so a source that fails leaves
    both places as they were.

    Args:
        reader_files_dir: The Reader Files folder the app reads.
        how_to_dir: The folder of the how-to's markdown and pictures.
        sources_dir: The folder of SVG sources.
        icons: The icons to render.

    Returns:
        The PNGs written, in the table's order, the app's before the how-to's.

    Raises:
        IconRenderError: A source is missing or cannot be rendered, or a folder an
            installed icon goes in is not there.

    """
    missing = [icon.svg for icon in icons if not (sources_dir / icon.svg).is_file()]
    if missing:
        msg = f"No such source in {sources_dir}: {', '.join(missing)}"
        raise IconRenderError(msg)
    targets = installed_paths(reader_files_dir, icons)
    absent = sorted({str(path.parent) for path in targets if not path.parent.is_dir()})
    if absent:
        msg = f"No such folder to install into: {', '.join(absent)}"
        raise IconRenderError(msg)

    rendered: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        for icon in icons:
            source = sources_dir / icon.svg
            if icon.installed is not None:
                made = scratch / f"app-{source.stem}.png"
                render_png(source, made)
                rendered.append((made, reader_files_dir / icon.installed))
            if icon.how_to is not None:
                recoloured = scratch / f"how-to-{icon.svg}"
                text = source.read_text(encoding="utf-8")
                recoloured.write_text(black_glyph(text, icon.svg), encoding="utf-8")
                made = scratch / f"how-to-{source.stem}.png"
                render_png(recoloured, made)
                rendered.append((made, how_to_dir / icon.how_to))
        for made, target in rendered:
            shutil.copyfile(made, target)
    return [target for _made, target in rendered]


def main(argv: list[str] | None = None) -> int:
    """Render the icons, or list them; return the exit status."""
    parser = argparse.ArgumentParser(description="Render the Reader's icons from their SVGs.")
    parser.add_argument("--list", action="store_true", help="say where each source goes and stop")
    parser.add_argument(
        "--reader-files-dir",
        type=Path,
        help="the Reader Files folder to install into (default: this machine's own)",
    )
    args = parser.parse_args(argv)

    if args.list:
        for icon in ICONS:
            places = [place for place in (icon.installed, icon.how_to) if place is not None]
            print(f"{icon.svg}: {', '.join(places)}")  # noqa: T201
        return 0

    reader_files_dir = args.reader_files_dir
    if reader_files_dir is None:
        from generated_files import reader_dirs  # noqa: PLC0415

        reader_files_dir = reader_dirs().reader_files
    try:
        written = render_all(reader_files_dir)
    except IconRenderError as error:
        print(error, file=sys.stderr)  # noqa: T201
        return 1
    print(f"Rendered {len(written)} icons into {reader_files_dir} and {HOW_TO_DIR}.")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
