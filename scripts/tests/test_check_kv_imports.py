"""Tests for the check that every ``.kv`` ``#: import`` directive resolves.

The check's own logic is exercised in-process, but whether a ``ui`` module target breaks
the targets after it can only be seen in a fresh interpreter: ``config_info``'s guard
against Kivy being loaded first stands down under pytest. So the last test runs the
check as the pre-commit hook does, over this repo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import check_kv_imports
from check_kv_imports import _APP_FIRST_IMPORT, _kv_files, main

_SCRIPT = Path(check_kv_imports.__file__)
_REPO_ROOT = _SCRIPT.parent.parent


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_mutation_copy_of_the_tree_is_left_out(tmp_path: Path) -> None:
    kept = _write(tmp_path / "barks-reader" / "src" / "barks_reader" / "ui" / "a.kv")
    _write(tmp_path / "barks-reader" / "mutants" / "src" / "barks_reader" / "ui" / "a.kv")

    assert _kv_files(tmp_path) == [kept]


def test_the_app_s_first_import_comes_before_any_kv_target(tmp_path: Path) -> None:
    _write(tmp_path / "x.kv", "#: import Thing some.module.Thing\n")

    with (
        patch.object(check_kv_imports, "_KV_SEARCH_ROOT", tmp_path),
        patch.object(check_kv_imports, "_REPO_ROOT", tmp_path),
        patch.object(check_kv_imports.importlib, "import_module") as import_module,
    ):
        assert main() == 0

    assert import_module.call_args_list[0].args == (_APP_FIRST_IMPORT,)
    assert import_module.call_args_list[1].args == ("some.module.Thing",)


def test_the_repo_s_kv_imports_resolve_in_a_fresh_interpreter() -> None:
    result = subprocess.run(  # noqa: S603 - this interpreter, running the repo's own script
        [sys.executable, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
