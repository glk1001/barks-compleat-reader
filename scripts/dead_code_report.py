#!/usr/bin/env python3
"""List the functions, methods and classes nothing names and nothing ran: likely dead code.

Vulture gates at 80% confidence (pre-commit, CI, full-lint), and it never rates an
unused function, method or class above 60%: Python can call any of them by a name
built at run time, and Kivy does, for a ``.kv`` file's handlers and properties. At
60% it lists hundreds, nearly all of them used that way. Coverage tells them apart:
code the whole suite and the GUI tests ran is used, whatever vulture saw. What is
left - named nowhere, run never - is worth a look. On 2026-10-05 that found three
methods nothing in this repo or its siblings called.

So this runs vulture at 60%, keeps the unused functions, methods, classes and
properties whose bodies have statements and none of them ran in the coverage data
given, and drops any named in a ``.kv`` file, in ``scripts/`` or ``main.py`` (not in
vulture's paths), or in the sibling repos that use barks-fantagraphics and
comic-utils. A file the data does not measure is left out: there it cannot say. A
class is judged by its methods' bodies, since its own body runs at import.

Its limits: code that only a test calls ran, so it is not listed; and a name found
anywhere in the places searched counts as used, so a common name can hide one. A
false positive is silenced in ``vulture_whitelist.py``, as for the gate.

Usage: dead_code_report.py COVERAGE_DATA [--siblings DIR...]
The overnight run's ``dead-code`` stage gives it the run's combined coverage
(``run_overnight.sh``). Exits 1 when it lists anything (the stage's WARNED), 0 when
it does not, 2 when vulture could not run.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import coverage

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIBLINGS = (REPO_ROOT.parent / "barks-comic-building", REPO_ROOT.parent / "barks-ocr")
MIN_CONFIDENCE = 60
# Vulture's exit status when it ran and found something (0 when it found nothing).
_VULTURE_FOUND = 3
# Copies of the code, not uses of it. A build/ only at a repo's top: a sibling has a
# source package of that name.
_SKIP_DIRS = {".venv", "mutants", "__pycache__", ".git"}

_FINDING = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+): unused (?P<kind>function|method|class|property)"
    r" '(?P<name>\w+)'"
)


@dataclass(frozen=True)
class Finding:
    """One of vulture's unused names: where it is defined, and what it is."""

    path: str
    line: int
    kind: str
    name: str

    def __str__(self) -> str:
        """Return ``path:line: kind name``, as the report lists it."""
        return f"{self.path}:{self.line}: {self.kind} {self.name}"


def parse_vulture(output: str) -> list[Finding]:
    """Return the unused functions, methods, classes and properties in vulture's output.

    Args:
        output: Vulture's report, a line per finding.

    Returns:
        The findings of those kinds; variables, attributes and imports are left out.

    """
    found = []
    for line in output.splitlines():
        match = _FINDING.match(line)
        if match:
            found.append(Finding(match["path"], int(match["line"]), match["kind"], match["name"]))
    return found


def body_lines(source: str, line: int) -> set[int] | None:
    """Return the lines that hold the body of the definition starting on `line`.

    A function's body, or for a class the bodies of its methods (a class body runs
    at import). The lines of a nested definition's header count, as they run with
    the body around them.

    Args:
        source: The module's source.
        line: The line vulture reports the definition on: its ``def`` or ``class``.

    Returns:
        The lines, or None when no definition starts on `line`.

    """
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if node.lineno != line:
            continue
        functions = (
            [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
            if isinstance(node, ast.ClassDef)
            else [node]
        )
        lines: set[int] = set()
        for function in functions:
            end = function.end_lineno or function.body[-1].lineno
            lines.update(range(function.body[0].lineno, end + 1))
        return lines
    return None


def never_ran(lines: set[int], statements: Iterable[int], executed: set[int]) -> bool:
    """Return whether the statements on `lines` are some, and none of them ran.

    Args:
        lines: The body's lines (``body_lines``).
        statements: The module's statement lines, as coverage counts them.
        executed: The statement lines that ran.

    Returns:
        False when the body has no statements: then the data cannot say.

    """
    body = {s for s in statements if s in lines}
    return bool(body) and not body & executed


def _python_and_kv_files(roots: Iterable[Path]) -> list[Path]:
    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            parts = path.relative_to(root).parts
            if (
                path.suffix in {".py", ".kv"}
                and not _SKIP_DIRS & set(parts)
                and parts[0] != "build"
            ):
                files.append(path)
    return files


def named_in(files: Iterable[Path], names: set[str]) -> set[str]:
    """Return those of `names` that appear as a whole word in any of `files`.

    Args:
        files: The files to search.
        names: The names to look for.

    Returns:
        The names found.

    """
    if not names:
        return set()
    word = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names))) + r")\b")
    found: set[str] = set()
    for path in files:
        try:
            found.update(word.findall(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return found


def run_vulture() -> str | None:
    """Return vulture's report at MIN_CONFIDENCE over pyproject's paths; None if it failed."""
    done = subprocess.run(  # noqa: S603 (vulture from this venv, fixed arguments)
        [sys.executable, "-m", "vulture", "--min-confidence", str(MIN_CONFIDENCE)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode not in (0, _VULTURE_FOUND):
        print(done.stdout + done.stderr, end="", file=sys.stderr)  # noqa: T201
        return None
    return done.stdout


@dataclass
class Report:
    """What was listed, and how many findings each filter left out."""

    dead: list[Finding]
    ran: int = 0
    unmeasured: int = 0
    named: int = 0


def report(
    findings: Sequence[Finding],
    data_file: Path,
    search: Sequence[Path],
    root: Path = REPO_ROOT,
) -> Report:
    """Sort vulture's findings into likely dead code and the ones each filter left out.

    Args:
        findings: Vulture's unused functions, methods, classes and properties.
        data_file: Coverage data of the code vulture read.
        search: Files and directories where a name counts as used.
        root: The directory vulture's paths are relative to.

    Returns:
        The findings never run and named nowhere, and the counts left out.

    """
    cov = coverage.Coverage(data_file=str(data_file))
    cov.load()
    measured = set(cov.get_data().measured_files())
    result = Report(dead=[])
    candidates = []
    for finding in findings:
        path = root / finding.path
        if str(path) not in measured:
            result.unmeasured += 1
            continue
        lines = body_lines(path.read_text(encoding="utf-8"), finding.line)
        _, statements, _, missing, _ = cov.analysis2(str(path))
        executed = set(statements) - set(missing)
        if lines is None or not never_ran(lines, statements, executed):
            result.ran += 1
            continue
        candidates.append(finding)
    used = named_in(_python_and_kv_files(search), {f.name for f in candidates})
    for finding in candidates:
        if finding.name in used:
            result.named += 1
        else:
            result.dead.append(finding)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Run the report; see the module docstring."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_file", type=Path, help="coverage data of the code vulture reads")
    parser.add_argument(
        "--siblings",
        nargs="*",
        type=Path,
        default=list(DEFAULT_SIBLINGS),
        help="repos whose use of a name counts (default: the two that use this one's)",
    )
    args = parser.parse_args(argv)

    output = run_vulture()
    if output is None:
        print("dead-code: vulture failed to run")  # noqa: T201
        return 2
    for sibling in args.siblings:
        if not sibling.is_dir():
            print(f"dead-code: {sibling}: not checked out; its uses are not counted")  # noqa: T201
    kv_files = sorted((REPO_ROOT / "src").rglob("*.kv"))
    search = [*kv_files, REPO_ROOT / "scripts", REPO_ROOT / "main.py", *args.siblings]
    result = report(parse_vulture(output), args.data_file, search, root=REPO_ROOT)

    print(  # noqa: T201
        f"dead-code: {len(result.dead)} unused and never run"
        f" (vulture at {MIN_CONFIDENCE}%, then this coverage data)"
    )
    for finding in result.dead:
        print(f"  {finding}")  # noqa: T201
    print(  # noqa: T201
        f"dead-code: left out: {result.ran} ran, {result.named} named in a .kv file,"
        f" scripts/ or a sibling, {result.unmeasured} in files the data does not measure"
    )
    return 1 if result.dead else 0


if __name__ == "__main__":
    sys.exit(main())
