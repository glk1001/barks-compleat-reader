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
import pytest
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


def _check(tmp_path: Path, kv_text: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Run the check over one kv file under `tmp_path`; return its status and what it printed."""
    _write(tmp_path / "ui" / "x.kv", kv_text)
    with (
        patch.object(check_kv_imports, "_KV_SEARCH_ROOT", tmp_path),
        patch.object(check_kv_imports, "_REPO_ROOT", tmp_path),
    ):
        status = main()
    return status, capsys.readouterr().out


class TestAnImportThatDoesNotResolve:
    """What the check is for: a renamed symbol in a kv file fails here, not at app boot."""

    def test_a_module_and_a_module_s_attribute_both_resolve(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        kv = "#: import json json\n#:import dumps json.dumps\n<Widget>:\n    text: 'x'\n"

        status, out = _check(tmp_path, kv, capsys)

        assert status == 0
        assert out == "All 2 .kv '#: import' directive(s) across 1 file(s) resolve.\n"

    @pytest.mark.parametrize(
        ("dotted", "says"),
        [
            pytest.param(
                "json.no_such_name", "'json' has no attribute 'no_such_name'", id="no attribute"
            ),
            pytest.param(
                "no_such_package_here.Thing",
                "cannot import 'no_such_package_here.Thing': No module named",
                id="no module",
            ),
            pytest.param("no_such_name_at_all", "cannot import 'no_such_name_at_all'", id="bare"),
        ],
    )
    def test_it_fails_naming_the_file_the_line_and_why(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], dotted: str, says: str
    ) -> None:
        kv = f"#: import json json\n<Widget>:\n#: import Thing {dotted}\n"

        status, out = _check(tmp_path, kv, capsys)

        assert status == 1
        assert f"  {Path('ui') / 'x.kv'}:3: {says}" in out
        assert "1 unresolved of 2 import(s) in 1 .kv file(s)." in out

    @pytest.mark.parametrize(
        ("dotted", "says"),
        [
            pytest.param("breaks_on_import", "error importing module 'breaks_on_import'", id="it"),
            pytest.param(
                "breaks_on_import.Thing",
                "error importing module 'breaks_on_import.Thing'",
                id="its parent",
            ),
        ],
    )
    def test_a_module_that_raises_as_it_is_imported_fails_too(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        dotted: str,
        says: str,
    ) -> None:
        _write(tmp_path / "lib" / "breaks_on_import.py", "raise RuntimeError('no display')\n")
        monkeypatch.syspath_prepend(str(tmp_path / "lib"))

        status, out = _check(tmp_path, f"#: import Thing {dotted}\n", capsys)

        assert status == 1
        assert f"{says}: RuntimeError('no display')" in out


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
