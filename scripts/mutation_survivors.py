#!/usr/bin/env python3
"""Compare a mutmut run's survivors, module by module, with the last run of those modules.

The overnight run mutates one seventh of ``core/`` a night (``run_overnight.sh``'s
mutation stage), and mutmut exits the same whether a module has none of its
recorded equivalents or ten new survivors. This is what makes a new one visible: it
reads ``mutmut results`` on stdin, counts the survivors of each module the run
mutated, and compares each count with the one recorded the last time that module
was mutated, in ``.benchmarks/mutation-survivors.json`` (gitignored, machine-local,
like the other baselines there).

Counts, not mutant names: mutmut numbers a function's mutants in source order, so
any edit renames them. A module whose count rose is reported with the names of its
survivors, to triage against ``docs/mutation-testing.md``'s known equivalents. The
record is then updated either way, so a rise is reported once, on the night it
appears.

Usage, with the modules mutated (dotted below ``barks_reader.core``) as arguments:
    (cd src/barks-reader && uv run mutmut results) | python scripts/mutation_survivors.py MODULE...

Exits 1 when any module's count rose, 0 otherwise (including the first run, which
only records).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_FILE = REPO_ROOT / ".benchmarks" / "mutation-survivors.json"

# mutmut names a mutant <module>.x_<func>__mutmut_N for a plain function and
# <module>.xǁ<Class>ǁ<method>__mutmut_N for a method (as mutmut.sh's summary).
_SURVIVOR = re.compile(r"^\s*barks_reader\.core\.(?P<module>.+?)\.(?:x_|xǁ).*: survived\s*$")


def survivors_by_module(results: str, modules: list[str]) -> dict[str, list[str]]:
    """Return each mutated module's surviving mutant names (a module with none gets []).

    Args:
        results: ``mutmut results`` output.
        modules: The modules this run mutated, dotted below ``barks_reader.core``.

    Returns:
        Survivor names, by module, for exactly `modules`.

    """
    found: dict[str, list[str]] = {module: [] for module in modules}
    for line in results.splitlines():
        match = _SURVIVOR.match(line)
        if match and match["module"] in found:
            found[match["module"]].append(line.strip().removesuffix(": survived"))
    return found


def rises(found: dict[str, list[str]], record: dict[str, int]) -> list[str]:
    """Return a report line per module with more survivors than recorded, names below it."""
    lines = []
    for module, names in sorted(found.items()):
        before = record.get(module)
        if before is not None and len(names) > before:
            lines.append(f"{module}: {before} -> {len(names)} survivors")
            lines.extend(f"    {name}" for name in names)
    return lines


def read_record(path: Path) -> dict[str, int]:
    """Return the recorded survivor count of each module; empty when there is none yet."""
    try:
        return {str(k): int(v) for k, v in json.loads(path.read_text())["survivors"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def write_record(path: Path, record: dict[str, int], found: dict[str, list[str]]) -> None:
    """Record tonight's counts for the modules mutated, keeping every other module's."""
    merged = record | {module: len(names) for module, names in found.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": dt.datetime.now(tz=dt.UTC).date().isoformat(), "survivors": merged}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main(modules: list[str], results: str, record_file: Path = RECORD_FILE) -> int:
    """Compare, report and record; return 1 when a module's survivors rose."""
    found = survivors_by_module(results, modules)
    record = read_record(record_file)
    report = rises(found, record)
    new = [module for module in modules if module not in record]
    write_record(record_file, record, found)
    if new:
        print(f"mutation survivors: first record for {', '.join(new)}")  # noqa: T201
    if not report:
        print("mutation survivors: no module has more than last time")  # noqa: T201
        return 0
    print("mutation survivors rose - triage against docs/mutation-testing.md:")  # noqa: T201
    for line in report:
        print(f"  {line}")  # noqa: T201
    return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:  # noqa: PLR2004
        print(__doc__)  # noqa: T201
        sys.exit(2)
    sys.exit(main(sys.argv[1:], sys.stdin.read()))
