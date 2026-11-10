"""Every kv file the app loads parses: its syntax, its expressions and its imports.

The unit tests build the screens bare, with Kivy's ``__init__`` patched out and mock
ids, so no kv file is read by them: a kv rule that could not load failed only in the
GUI suite, minutes later. This parses each one with Kivy's own parser, which compiles
every expression and runs every ``#:import``, but registers no rule, so the widgets
other tests build are left alone. It builds no screen: an id a rule and its Python no
longer agree on still waits for the GUI suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The app's module, for what its imports bring: a `#:import` of a module's attribute
# reads it from a module already imported, as it is by the time the app loads its kv.
from barks_reader.ui import barks_reader_app
from kivy.lang.parser import Parser

_KV_FILES = sorted(Path(barks_reader_app.__file__).parent.glob("*.kv"))


def test_the_kv_files_are_found() -> None:
    assert "main_screen.kv" in [kv.name for kv in _KV_FILES]


@pytest.mark.parametrize("kv_file", _KV_FILES, ids=lambda kv: kv.name)
def test_a_kv_file_parses(kv_file: Path) -> None:
    parsed = Parser(content=kv_file.read_text(encoding="utf-8"), filename=str(kv_file))

    assert parsed.rules, f"{kv_file.name} holds no rule"


def test_the_parser_does_catch_a_broken_expression_and_a_bad_import() -> None:
    """What the test above leans on, held to: a Kivy that stopped raising would pass it."""
    with pytest.raises(SyntaxError):
        Parser(content="<Widget>:\n    x: 1 +\n", filename="broken.kv")
    with pytest.raises(Exception, match="no_such_module"):
        Parser(content="#:import gone no_such_module.gone\n<Widget>:\n    x: 1\n")
