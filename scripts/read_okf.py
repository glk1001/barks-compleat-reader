# ruff: noqa: T201
"""CLI entry point that opens an OKF bundle in the standalone OKF reader.

Mirrors scripts/read_comic.py: a thin typer command over a workspace package —
here ``okf_reader`` (its own package) — that builds and runs the Kivy app.

Run:  uv run scripts/read_okf.py ../barks-wiki/okf
"""

from pathlib import Path
from typing import Annotated

import typer
from okf_reader.ui.viewer import run

app = typer.Typer()


@app.command(help="Open an OKF knowledge bundle in the standalone reader.")
def main(
    bundle: Annotated[Path, typer.Argument(help="Path to the OKF bundle directory.")],
) -> None:
    if not bundle.is_dir():
        print(f"error: bundle {bundle} not found")
        raise typer.Exit(code=2)
    run(bundle)


if __name__ == "__main__":
    app()
