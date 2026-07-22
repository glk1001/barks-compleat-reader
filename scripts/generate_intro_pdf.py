#!/usr/bin/env python
# ruff: noqa: T201

"""Generate the intro PDF from ``docs/intro-to-barks-reader.fodt`` via LibreOffice.

Usage:
    uv run scripts/generate_intro_pdf.py
    uv run scripts/generate_intro_pdf.py --output-dir "/path/to/gimp/import/dir"

Drives LibreOffice headlessly — the same engine you use when exporting the PDF by
hand — so the layout is identical. The exported PDF has a transparent background
(only the text is drawn), matching the how-to pages: overlay it on the Barks
background in the GIMP intro project, then export the composited ``page-N.jpg`` to
the Reader's ``Various/documents/intro-to-barks-reader`` directory.

A private LibreOffice user profile is used for the run, so this works even while a
normal LibreOffice window is open.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import typer

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FODT = REPO_ROOT / "docs" / "intro-to-barks-reader.fodt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "intro-pdf"


def convert_to_pdf(fodt_path: Path, output_dir: Path, soffice: str) -> Path:
    """Convert a LibreOffice document to PDF with a headless LibreOffice run.

    Args:
        fodt_path: The source ``.fodt`` (or any LibreOffice-readable) document.
        output_dir: Directory to write the ``<stem>.pdf`` into (created if absent).
        soffice: The LibreOffice launcher to invoke (name on PATH or full path).

    Returns:
        The path to the written PDF.

    """
    launcher = shutil.which(soffice)
    if launcher is None:
        msg = f"LibreOffice launcher not found on PATH: {soffice!r}"
        raise FileNotFoundError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    # A throwaway user profile keeps this from clashing with a running LibreOffice.
    profile_dir = Path(tempfile.mkdtemp(prefix="barks-lo-profile-"))
    try:
        subprocess.run(  # noqa: S603  (arguments are fixed, not user-shell input)
            [
                launcher,
                "--headless",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(fodt_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    return output_dir / f"{fodt_path.stem}.pdf"


app = typer.Typer(add_completion=False)


@app.command()
def main(
    fodt: Annotated[Path, typer.Option(help="Source .fodt document.")] = DEFAULT_FODT,
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory to write the PDF into."),
    ] = DEFAULT_OUTPUT_DIR,
    soffice: Annotated[
        str,
        typer.Option(help="LibreOffice launcher (name on PATH or full path)."),
    ] = "soffice",
) -> None:
    """Export the intro .fodt to a transparent-background PDF via LibreOffice."""
    if not fodt.is_file():
        typer.echo(f"Document not found: {fodt}", err=True)
        raise typer.Exit(1)

    try:
        pdf_path = convert_to_pdf(fodt, output_dir, soffice)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except subprocess.CalledProcessError as exc:
        typer.echo(f"LibreOffice conversion failed:\n{exc.stderr}", err=True)
        raise typer.Exit(1) from exc

    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    app()
