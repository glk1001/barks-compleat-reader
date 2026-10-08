#!/usr/bin/env python3
"""Sort a mutmut run's survivors into known equivalents, the untriaged backlog and new ones.

mutmut exits the same whether every survivor is a known equivalent or ten are new,
and it renumbers a function's mutants on any edit, so neither its exit status nor
its names say what changed since last night. This identifies each survivor by what
it is: its module, its function, and the change it makes (the lines it takes out
and puts in), which edits elsewhere in the file leave alone. Then each is one of:

- **equivalent**: listed under ``[[equivalent]]`` in ``docs/mutation-equivalents.toml``
  with the reason no test can tell it apart, or a change only to the arguments of a
  ``logger`` call that does not use ``log_markers`` (log wording; a marker's text is
  what the GUI tests wait on, so a change to one is never let through);
- **untriaged**: listed under ``[[untriaged]]``, the backlog recorded on 2026-10-08,
  each to be killed with a test or moved to ``[[equivalent]]`` with its reason;
- **new**: neither. These are the ones to look at, and the only ones it warns on.

A listed entry the run mutated but that no longer survives is reported too, to be
taken out of the file (a test now kills it, or its code changed).

Run in the mutated package's folder, where ``mutmut.sh`` left its ``mutants/``:
    (cd src/barks-reader && uv run python ../../scripts/mutation_survivors.py)
``--baseline`` adds every survivor that is neither listed nor log wording to
``[[untriaged]]`` and rewrites the file (its entries, in order; comments outside the
header are not kept). Modules below a ``testing`` package are left out: they are
test helpers, not the code under test.

Exits 1 when there is a new survivor, 0 otherwise.
"""

# cspell:ignore lineterm mutatable

from __future__ import annotations

import argparse
import ast
import difflib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
EQUIVALENTS_FILE = REPO_ROOT / "docs" / "mutation-equivalents.toml"
_SHOWN = 30  # the most new or gone entries listed before counting the rest


@dataclass(frozen=True)
class Survivor:
    """A surviving mutant, by what it is rather than by mutmut's number for it."""

    module: str
    function: str
    change: str

    @property
    def key(self) -> tuple[str, str, str]:
        """Return what identifies it: module, function and change."""
        return (self.module, self.function, self.change)


def split_name(mutant_name: str) -> tuple[str, str]:
    """Return a mutant's module and function: ``Class.method`` for a method.

    mutmut names one ``<module>.x_<func>__mutmut_N``, or ``<module>.xǁ<Class>ǁ<method>
    __mutmut_N`` for a method.
    """
    name = mutant_name.rsplit("__mutmut_", 1)[0]
    if ".xǁ" in name:
        module, rest = name.split(".xǁ", 1)
        return module, rest.replace("ǁ", ".")
    module, function = name.rsplit(".x_", 1)
    return module, function


def change_of(original: str, mutant: str) -> str:
    """Return the lines a mutant takes out (``- ``) and puts in (``+ ``), stripped."""
    return "\n".join(
        f"{line[0]} {line[1:].strip()}"
        for line in difflib.unified_diff(original.splitlines(), mutant.splitlines(), lineterm="")
        if line[:1] in "-+" and not line.startswith(("---", "+++"))
    )


class _DropLogArguments(ast.NodeTransformer):
    """Empty the arguments of every ``logger`` call that does not use ``log_markers``."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if _calls_logger(node.func) and not _uses_log_markers(node):
            node.args, node.keywords = [], []
        return node


def _calls_logger(func: ast.expr) -> bool:
    while isinstance(func, ast.Attribute | ast.Call):
        func = func.value if isinstance(func, ast.Attribute) else func.func
    return isinstance(func, ast.Name) and func.id == "logger"


def _uses_log_markers(node: ast.Call) -> bool:
    return any(
        isinstance(sub, ast.Name) and sub.id in {"log_markers", "markers"}
        for arg in [*node.args, *(k.value for k in node.keywords)]
        for sub in ast.walk(arg)
    )


def is_log_wording(original: str, mutant: str) -> bool:
    """Return whether a mutant changes only what a ``logger`` call is given to log.

    Args:
        original: The original function's source.
        mutant: The mutated function's source.

    Returns:
        False too when either does not parse, or the call uses ``log_markers``.

    """
    try:
        trees = [ast.parse(original), ast.parse(mutant)]
    except SyntaxError:
        return False
    if ast.dump(trees[0]) == ast.dump(trees[1]):
        return False
    original_tree, mutant_tree = (_DropLogArguments().visit(tree) for tree in trees)
    return ast.dump(original_tree) == ast.dump(mutant_tree)


@dataclass
class Listed:
    """The entries of the equivalents file."""

    equivalent: dict[tuple[str, str, str], str]  # survivor key -> reason
    untriaged: list[tuple[str, str, str]]


def read_listed(path: Path) -> Listed:
    """Return the entries of `path`; none when it does not exist yet."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Listed({}, [])

    def key(entry: dict[str, str]) -> tuple[str, str, str]:
        return (entry["module"], entry["function"], entry["change"].removesuffix("\n"))

    return Listed(
        equivalent={key(e): e["reason"] for e in data.get("equivalent", [])},
        untriaged=[key(e) for e in data.get("untriaged", [])],
    )


_HEADER = """\
# Surviving mutants of the overnight mutation stage, by what they are: module, function
# and the change (the lines the mutant takes out, "- ", and puts in, "+ ").
# scripts/mutation_survivors.py reads this; see docs/mutation-testing.md.
#
# [[equivalent]]: no test can tell the mutant from the code; the reason says why.
# [[untriaged]]:  the backlog, recorded on 2026-10-08. Kill one with a test (then take
#                 it out), or move it to [[equivalent]] and give it a reason.
# A change only to what a logger call is given is equivalent without being listed,
# unless the call uses log_markers.
"""


def _toml_string(text: str) -> str:
    if "\n" not in text:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    # The closing quotes on a line of their own, so a change that ends in a quote stays
    # readable; read_listed takes that last newline off again.
    return '"""\n' + text.replace("\\", "\\\\").replace('"""', '""\\"') + '\n"""'


def write_listed(path: Path, listed: Listed) -> None:
    """Write `listed` to `path`: the header, then the equivalents, then the backlog."""
    out = [_HEADER]
    for (module, function, change), reason in listed.equivalent.items():
        out += [
            "",
            "[[equivalent]]",
            f"module = {_toml_string(module)}",
            f"function = {_toml_string(function)}",
            f"change = {_toml_string(change)}",
            f"reason = {_toml_string(reason)}",
        ]
    for module, function, change in listed.untriaged:
        out += [
            "",
            "[[untriaged]]",
            f"module = {_toml_string(module)}",
            f"function = {_toml_string(function)}",
            f"change = {_toml_string(change)}",
        ]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


@dataclass
class Sorted:
    """A run's survivors, by class, and the listed entries it no longer has."""

    equivalent: list[Survivor]
    log_wording: list[Survivor]
    untriaged: list[Survivor]
    new: list[Survivor]
    gone: list[tuple[str, str, str]]


def sort_survivors(
    survivors: Iterable[tuple[Survivor, bool]], listed: Listed, mutated: set[str]
) -> Sorted:
    """Sort each survivor, with whether it is log wording, against the listed entries.

    Args:
        survivors: Each survivor and whether it only changes a logger call's message.
        listed: The equivalents file's entries.
        mutated: The modules the run mutated: a listed entry of another is not gone.

    Returns:
        The survivors by class, and the listed entries of `mutated` that did not survive.

    """
    result = Sorted([], [], [], [], [])
    backlog = set(listed.untriaged)
    seen = set()
    for survivor, log_wording in survivors:
        seen.add(survivor.key)
        if survivor.key in listed.equivalent:
            result.equivalent.append(survivor)
        elif log_wording:
            result.log_wording.append(survivor)
        elif survivor.key in backlog:
            result.untriaged.append(survivor)
        else:
            result.new.append(survivor)
    for key in [*listed.equivalent, *listed.untriaged]:
        if key[0] in mutated and key not in seen:
            result.gone.append(key)
    return result


def report(result: Sorted, package_label: str) -> list[str]:
    """Return the lines that say how the run's survivors sorted."""
    total = sum(
        len(group)
        for group in (result.equivalent, result.log_wording, result.untriaged, result.new)
    )
    lines = [
        (
            f"mutation survivors ({package_label}): {total} ="
            f" {len(result.equivalent) + len(result.log_wording)} equivalent"
            f" ({len(result.equivalent)} listed, {len(result.log_wording)} log wording)"
            f" + {len(result.untriaged)} untriaged + {len(result.new)} new"
        )
    ]
    if result.new:
        lines.append(
            "NEW survivors: kill each with a test, or add it to docs/mutation-equivalents.toml:"
        )
        for survivor in result.new[:_SHOWN]:
            lines.append(f"  {survivor.module} {survivor.function}")
            lines.extend(f"      {line}" for line in survivor.change.splitlines())
        if len(result.new) > _SHOWN:
            lines.append(f"  ... and {len(result.new) - _SHOWN} more")
    if result.gone:
        lines.append(
            f"{len(result.gone)} listed no longer survive: take them out of"
            " docs/mutation-equivalents.toml"
        )
        for module, function, change in result.gone[:_SHOWN]:
            lines.append(f"  {module} {function}: {change.splitlines()[0] if change else ''}")
    return lines


def collect(package_dir: Path) -> tuple[list[tuple[Survivor, bool]], set[str]]:
    """Return the survivors of the run in `package_dir`, and the modules it mutated.

    Read through mutmut itself: the mutated sources it left in ``mutants/`` hold each
    mutant beside its original, and its result files say which survived.
    """
    import os  # noqa: PLC0415

    import libcst as cst  # noqa: PLC0415
    from mutmut import __main__ as mm  # noqa: PLC0415

    os.chdir(package_dir)
    mm.Config.ensure_loaded()
    survivors: list[tuple[Survivor, bool]] = []
    mutated: set[str] = set()
    for path in mm.walk_mutatable_files():
        data = mm.SourceFileMutationData(path=path)
        data.load()
        names = [n for n in data.exit_code_by_key if ".testing." not in n]
        mutated.update(split_name(n)[0] for n in names)
        surviving = [
            n for n in names if mm.status_by_exit_code[data.exit_code_by_key[n]] == "survived"
        ]
        if not surviving:
            continue
        module = mm.read_mutants_module(path)
        for name in surviving:
            original = cst.Module([mm.read_original_function(module, name)]).code.strip()
            mutant = cst.Module([mm.read_mutant_function(module, name)]).code.strip()
            module_name, function = split_name(name)
            survivor = Survivor(module_name, function, change_of(original, mutant))
            survivors.append((survivor, is_log_wording(original, mutant)))
    return survivors, mutated


def main(argv: list[str] | None = None, equivalents_file: Path = EQUIVALENTS_FILE) -> int:
    """Sort, report, and with ``--baseline`` record; see the module docstring."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", action="store_true", help="add the unlisted to the backlog")
    parser.add_argument("--package-dir", type=Path, default=Path.cwd(), help="where mutants/ is")
    args = parser.parse_args(argv)

    survivors, mutated = collect(args.package_dir.resolve())
    listed = read_listed(equivalents_file)
    result = sort_survivors(survivors, listed, mutated)
    for line in report(result, args.package_dir.name):
        print(line)  # noqa: T201
    if args.baseline and result.new:
        listed.untriaged += _unique(s.key for s in result.new)
        write_listed(equivalents_file, listed)
        print(f"mutation survivors: {len(result.new)} added to the backlog")  # noqa: T201
        return 0
    return 1 if result.new else 0


def _unique(keys: Iterable[tuple[str, str, str]]) -> Iterator[tuple[str, str, str]]:
    seen = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            yield key


if __name__ == "__main__":
    sys.exit(main())
