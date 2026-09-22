# ruff: noqa: T201 - a console check script prints its report by design.
# cspell:ignore orelse elts Mult
"""Check that the GUI tests press only the remote's six keys.

The Barks Reader is driven from a 4K TV by a six-button remote: Escape, Enter
(X11 ``Return``), Up, Down, Left and Right. Every screen must be reachable with
those alone, and the GUI tests are the record of how. A test that reaches
something with Tab, Home or Delete proves nothing about the remote, so this
check reads the GUI tests, the driver they share and the demo recorder, and
fails on any other key name handed to a key-pressing method (``key``,
``key_then_wait``, ``move_focus``).

Two things are outside the rule. Typed text (``type_slowly``) is not a key.
And a desktop-only key may be pressed on purpose, where the call says so on one
of its lines: ``# desktop key: <why>``. The waiver keeps each extra visible in
the test that needs it rather than in a list here.

A key that is not a literal at the call is traced: through the assignments to
that name in the enclosing function and through the module's constants, and
every string found on the way is checked. A key nothing can be found for is an
error, since the check cannot say what the test presses.

Run directly (``uv run scripts/check_gui_keys.py [paths]``) or via
``full-lint.sh`` and the pre-commit hook.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

REMOTE_KEYS: frozenset[str] = frozenset({"Escape", "Return", "Up", "Down", "Left", "Right"})
# A method that presses keys, and the index of its first key argument (the
# arguments before it are a log pattern).
KEY_METHODS: dict[str, int] = {"key": 0, "key_then_wait": 1, "move_focus": 0}
WAIVER_RE = re.compile(r"#\s*desktop key:\s*\S")

if TYPE_CHECKING:
    from collections.abc import Iterable

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATHS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "barks-reader" / "tests" / "gui",
    _REPO_ROOT / "scripts" / "gui_driver.py",
    _REPO_ROOT / "scripts" / "record_demo.py",
)

_REMOTE_KEYS_TEXT = ", ".join(sorted(REMOTE_KEYS))


@dataclass(frozen=True)
class Press:
    """One key argument of one key-pressing call."""

    line: int
    keys: frozenset[str]  # every key the argument can be; empty when nothing was found
    waived: bool

    def problem(self) -> str | None:
        """Return why this press fails the check, or None when it passes."""
        if not self.keys:
            return (
                "cannot tell which key this presses: press a literal, or assign the key "
                "from literals or a module constant"
            )
        extras = sorted(self.keys - REMOTE_KEYS)
        if extras and not self.waived:
            listed = ", ".join(repr(k) for k in extras)
            return (
                f"{listed} is not a remote key ({_REMOTE_KEYS_TEXT}); press one of those, "
                "or waive it on the call with '# desktop key: <why>'"
            )
        return None


class _Scope:
    """The names a key argument can be traced through: local assignments, then constants."""

    def __init__(self, module: ast.Module, function: ast.AST | None) -> None:
        self._constants = _assignments_in(module.body)
        self._locals = _assignments_in(ast.walk(function)) if function is not None else {}

    def strings_in(self, expr: ast.AST) -> frozenset[str]:
        """Return every string the expression can be, tracing names as far as they go."""
        return frozenset(self._collect(expr, seen=set()))

    def _collect(self, expr: ast.AST, seen: set[str]) -> set[str]:  # noqa: PLR0911 - one branch per shape
        """Collect the strings an expression can stand for, by its shape.

        Only the parts of an expression that can be the key are followed: the
        branches of a conditional, the members of a tuple or list, the
        arguments of a call (``rng.choice(KEYS)``), a repeated list
        (``["Down"] * n``) - not a call's receiver, a condition or an f-string,
        which gathered the seed and the boot nodes when everything was walked.
        """
        match expr:
            case ast.Constant(value=str(value)):
                return {value}
            case ast.Name(id=name):
                if name in seen:
                    return set()
                seen.add(name)
                found: set[str] = set()
                for source in self._locals.get(name) or self._constants.get(name, []):
                    found |= self._collect(source, seen)
                return found
            case ast.IfExp(body=body, orelse=orelse):
                return self._collect(body, seen) | self._collect(orelse, seen)
            case ast.Tuple(elts=elts) | ast.List(elts=elts) | ast.Set(elts=elts):
                return set().union(*(self._collect(e, seen) for e in elts))
            case ast.Starred(value=value) | ast.Subscript(value=value):
                return self._collect(value, seen)
            case ast.Call(args=args):
                return set().union(*(self._collect(a, seen) for a in args))
            case ast.BinOp(left=left, op=ast.Mult(), right=right):  # ["Down"] * n
                return self._collect(left, seen) | self._collect(right, seen)
            case _:
                return set()


def _assignments_in(nodes: Iterable[ast.AST]) -> dict[str, list[ast.AST]]:
    """Return the expressions assigned to each name among the nodes, loops included.

    A tuple target is paired with a tuple value element by element (through a
    conditional over two tuples too), so ``step, n = ("Right", f) if c else
    ("Left", b)`` gives ``step`` the two strings and not the counts.
    """
    sources: dict[str, list[ast.AST]] = {}
    for node in nodes:
        for name, value in _targets_of(node):
            sources.setdefault(name, []).append(value)
    return sources


def _targets_of(node: ast.AST) -> list[tuple[str, ast.AST]]:
    match node:
        case ast.Assign(targets=[target], value=value) | ast.AnnAssign(target=target, value=value):
            if value is not None:
                return _pair(target, value)
        case ast.For(target=target, iter=value):
            return _pair(target, value)
    return []


def _pair(target: ast.AST, value: ast.AST) -> list[tuple[str, ast.AST]]:
    if isinstance(target, ast.Name):
        return [(target.id, value)]
    if not isinstance(target, ast.Tuple):
        return []
    values = value.elts if isinstance(value, ast.Tuple) else None
    if isinstance(value, ast.IfExp) and all(
        isinstance(v, ast.Tuple) and len(v.elts) == len(target.elts)
        for v in (value.body, value.orelse)
    ):
        body, orelse = value.body, value.orelse
        assert isinstance(body, ast.Tuple) and isinstance(orelse, ast.Tuple)  # noqa: PT018
        return [
            (t.id, ast.IfExp(value.test, b, o))
            for t, b, o in zip(target.elts, body.elts, orelse.elts, strict=True)
            if isinstance(t, ast.Name)
        ]
    if values is not None and len(values) == len(target.elts):
        return [
            (t.id, v) for t, v in zip(target.elts, values, strict=True) if isinstance(t, ast.Name)
        ]
    return [(t.id, value) for t in target.elts if isinstance(t, ast.Name)]


def _key_method(call: ast.Call) -> int | None:
    """Return the index of the call's first key argument, or None if it presses no keys."""
    if isinstance(call.func, ast.Attribute):
        return KEY_METHODS.get(call.func.attr)
    return None


def _calls_with_scope(module: ast.Module) -> list[tuple[ast.Call, ast.AST | None]]:
    """Return every call in the module with its enclosing function, outermost first.

    Calls inside the definition of a key method itself (the driver's own
    ``key_then_wait`` passing its keys on to ``key``) are left out: they press
    whatever their caller asked for, and the caller is where it is checked.
    """
    found: list[tuple[ast.Call, ast.AST | None]] = []

    def visit(node: ast.AST, function: ast.AST | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                if child.name not in KEY_METHODS:
                    visit(child, child)
                continue
            if isinstance(child, ast.Call):
                found.append((child, function))
            visit(child, function)

    visit(module, None)
    return found


def presses_in(source: str) -> list[Press]:
    """Return every key argument of every key-pressing call in the source text.

    Args:
        source: The Python source of one file.

    Returns:
        The presses, in source order.

    """
    module = ast.parse(source)
    lines = source.splitlines()
    presses: list[Press] = []
    for call, function in _calls_with_scope(module):
        first_key = _key_method(call)
        if first_key is None:
            continue
        scope = _Scope(module, function)
        end = call.end_lineno or call.lineno
        waived = any(WAIVER_RE.search(lines[i - 1]) for i in range(call.lineno, end + 1))
        for arg in call.args[first_key:]:
            expr = arg.value if isinstance(arg, ast.Starred) else arg
            presses.append(Press(arg.lineno, scope.strings_in(expr), waived))
    return presses


def python_files(paths: list[Path]) -> list[Path]:
    """Return the ``.py`` files under the paths (a file as itself), sorted."""
    files: set[Path] = set()
    for path in paths:
        if path.is_dir():
            files.update(path.rglob("*.py"))
        else:
            files.add(path)
    return sorted(files)


def main(argv: list[str] | None = None) -> int:
    """Check the GUI tests (or the paths given); return a process exit code."""
    args = [Path(a) for a in (sys.argv[1:] if argv is None else argv)]
    files = python_files(args or list(DEFAULT_PATHS))
    problems: list[str] = []
    checked = 0
    waived = 0
    for path in files:
        presses = presses_in(path.read_text(encoding="utf-8"))
        checked += len(presses)
        waived += sum(1 for p in presses if p.waived and p.keys - REMOTE_KEYS)
        shown = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
        problems.extend(
            f"{shown}:{p.line}: {problem}" for p in presses if (problem := p.problem()) is not None
        )

    if problems:
        print(f"FAILED: keys the remote does not have ({_REMOTE_KEYS_TEXT}):\n")
        for problem in problems:
            print(f"  {problem}")
        print(f"\n{len(problems)} of {checked} key press(es) in {len(files)} file(s).")
        return 1

    print(
        f"All {checked} key press(es) across {len(files)} file(s) are remote keys"
        f" ({waived} waived as desktop keys)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
