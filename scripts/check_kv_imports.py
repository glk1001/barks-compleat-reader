# ruff: noqa: T201 - a console check script prints its report by design.
"""Validate that every Kivy ``.kv`` ``#: import`` directive still resolves.

Kivy ``.kv`` files reference Python via ``#: import <alias> <dotted.path>``
directives that ``Builder`` resolves at app-boot time - invisible to ruff, ty,
pyrefly, and pytest. A rename or move of the referenced symbol leaves the
directive dangling and only crashes when the screen is first built. This check
imports each dotted path (as a module, or as an attribute of its parent module)
and fails on anything that no longer resolves.

Run directly (``uv run scripts/check_kv_imports.py``) or via ``full-lint.sh``.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

# Kivy accepts both "#: import" and "#:import" (optional spaces after the colon).
_KV_IMPORT_RE = re.compile(r"^\s*#:\s*import\s+(\S+)\s+(\S+)\s*$")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_KV_SEARCH_ROOT = _REPO_ROOT / "src"


def _resolve_dotted_path(dotted: str) -> str | None:  # noqa: PLR0911 - flat error branches
    """Return an error message if *dotted* cannot be resolved, else ``None``.

    Tries *dotted* as a module first, then as ``<module>.<attribute>``.
    """
    try:
        importlib.import_module(dotted)
    except ModuleNotFoundError:
        pass  # Not a module - fall through and try it as <module>.<attribute>.
    except Exception as exc:  # noqa: BLE001 - surface import-time failures too
        return f"error importing module '{dotted}': {exc!r}"
    else:
        return None

    module_path, _, attribute = dotted.rpartition(".")
    if not module_path:
        return f"cannot import '{dotted}'"
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        return f"cannot import '{dotted}': {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"error importing '{module_path}': {exc!r}"

    if not hasattr(module, attribute):
        return f"'{module_path}' has no attribute '{attribute}'"
    return None


def _iter_kv_imports(kv_file: Path) -> list[tuple[int, str]]:
    """Return ``(line_number, dotted_path)`` for each import directive in *kv_file*."""
    imports: list[tuple[int, str]] = []
    lines = kv_file.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, start=1):
        match = _KV_IMPORT_RE.match(line)
        if match:
            imports.append((line_no, match.group(2)))
    return imports


def main() -> int:
    """Check every ``.kv`` import directive; return a process exit code."""
    os.environ.setdefault("KIVY_NO_ARGS", "1")  # Keep Kivy quiet if a target imports it.

    kv_files = sorted(_KV_SEARCH_ROOT.rglob("*.kv"))
    errors: list[str] = []
    checked = 0

    for kv_file in kv_files:
        rel = kv_file.relative_to(_REPO_ROOT)
        for line_no, dotted in _iter_kv_imports(kv_file):
            checked += 1
            problem = _resolve_dotted_path(dotted)
            if problem is not None:
                errors.append(f"{rel}:{line_no}: {problem}")

    if errors:
        print("FAILED: unresolved .kv '#: import' directives:\n")
        for err in errors:
            print(f"  {err}")
        print(f"\n{len(errors)} unresolved of {checked} import(s) in {len(kv_files)} .kv file(s).")
        return 1

    print(f"All {checked} .kv '#: import' directive(s) across {len(kv_files)} file(s) resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
