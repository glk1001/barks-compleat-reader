"""The CLI helpers the sibling repos' entry points share (barks-ocr's tools use them).

Nothing in this repo runs them, so these hold their contract: the logging setup
fills the log-setup module before loading the config, and the shared options parse
under their own names.
"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import patch

import typer
from comic_utils import cli_setup
from comic_utils.common_typer_options import (  # noqa: TC002 (typer reads them at run time)
    LogLevelArg,
    PagesArg,
    TitleArg,
    VolumesArg,
)
from typer.testing import CliRunner


def test_init_logging_fills_the_log_setup_module_then_loads_the_config() -> None:
    log_setup = types.ModuleType("log_setup")
    seen: dict[str, object] = {}

    def load(config: Path) -> None:
        # The config reads these as it loads, so they must be set first.
        seen.update(vars(log_setup), config=config)

    with patch.object(cli_setup.LoguruConfig, "load", side_effect=load):
        cli_setup.init_logging(log_setup, Path("log.yaml"), "barks-ocr", "ocr.log", "DEBUG")
    assert seen["log_level"] == "DEBUG"
    assert seen["log_filename"] == "ocr.log"
    assert seen["APP_LOGGING_NAME"] == "barks-ocr"
    assert seen["config"] == Path("log.yaml")


def test_the_shared_options_parse_under_their_names() -> None:
    app = typer.Typer()
    got: dict[str, str] = {}

    @app.command()
    def main(log_level: LogLevelArg, page: PagesArg, title: TitleArg, volume: VolumesArg) -> None:
        got.update(log_level=log_level, page=page, title=title, volume=volume)

    args = ["--log-level", "INFO", "--page", "3-5", "--title", "Lost in the Andes!"]
    result = CliRunner().invoke(app, [*args, "--volume", "7"])
    assert result.exit_code == 0, result.output
    assert got == {"log_level": "INFO", "page": "3-5", "title": "Lost in the Andes!", "volume": "7"}
