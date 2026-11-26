#!/usr/bin/env python3
"""Smooth the jagged edges of the panel PNGs, in place, keeping every original.

The panel PNGs under ``Barks Panels Pngs`` have stair-stepped ink lines. This runs
G'MIC's "Smooth [Antialias]" filter over them: an edge-directed smoothing that leaves
flat colour alone. The pipeline is written out here rather than called by its GUI name
(``fx_smooth_antialias``), which only exists once the G'MIC GUI has downloaded its
filter updates. At amplitude 2 the outlines lose their steps and lettering, eye rings
and hatching keep theirs; at 5, the GUI's default, marks a pixel or two wide smear.

Without ``--apply`` it only says what it would do. With it, each original is copied to
``--backup-dir`` under the same relative path before its filtered copy takes its place.
That copy is also the record that a file is done: a file with a backup is skipped, so a
second run never smooths a file twice. Delete the backup folder and that record goes
with it. ``--restore`` puts every backed-up original back and removes its backup.

Skipped, and said so: anything not a PNG (a JPEG would be compressed a second time), a
PNG with any transparent pixel (the filter softens the alpha edge and bleeds the hidden
colour under it into the visible edge), a file an ``--exclude`` matches, and a file
already done.

``--include`` names top-level folders (default: all of them). ``--exclude`` is a glob
against the path relative to the root, where ``*`` also matches ``/``: ``AI/*`` is
everything under AI, ``*-flipped.png`` every flipped panel.

Needs ``gmic`` on the PATH (``sudo apt install gmic``).

Usage: antialias_panels.py --root DIR --backup-dir DIR [--include NAME]...
[--exclude GLOB]... [--amplitude N] [--apply | --restore]. Exits 1 when a file failed
or the arguments cannot be used, 0 otherwise.
"""

# cspell:ignore antialias antialiased diffusiontensors fnmatch fnmatchcase gmic

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

AMPLITUDE = 2.0
EDGE_THRESHOLD = 10.0  # the GUI filter's default, per cent
SMOOTHNESS = 0.8  # the GUI filter's default
TEMP_SUFFIX = ".antialias-tmp"

EXCLUDED = "excluded"
NOT_PNG = "not a PNG"
DONE = "already done (has a backup)"
TRANSPARENT = "has transparent pixels"

type Filter = Callable[[Path, Path], None]


def _say(text: str) -> None:
    print(text)  # noqa: T201


def gmic_args(amplitude: float) -> list[str]:
    """Return the G'MIC pipeline that ``fx_smooth_antialias`` runs, for one amplitude.

    The GUI filter divides its amplitude by three before smoothing (its ``{$1^1/3}``
    is ``($1^1)/3``), so that is kept here for the numbers to mean what they do there.
    """
    pipeline = (
        f"foreach {{ +diffusiontensors 0,1,1,{SMOOTHNESS:g},{SMOOTHNESS:g} "
        f"+gradient_norm.. >=. {EDGE_THRESHOLD:g}% *[-2,-1] "
        f"smooth.. .,{{{amplitude:g}/3}},0.5,120,2,1 rm. }} c 0,255"
    )
    return pipeline.split()


def gmic_filter(amplitude: float) -> Filter:
    """Return a filter that writes the antialiased copy of one PNG with ``gmic``.

    G'MIC reads options out of a file name (after a comma), so it is only ever given
    names this script chose.
    """

    def run(source: Path, target: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="antialias-") as scratch:
            plain_in, plain_out = Path(scratch) / "in.png", Path(scratch) / "out.png"
            shutil.copyfile(source, plain_in)
            subprocess.run(  # noqa: S603
                ["gmic", "-v", "0", str(plain_in), *gmic_args(amplitude), "o", str(plain_out)],  # noqa: S607
                check=True,
                capture_output=True,
            )
            shutil.copyfile(plain_out, target)

    return run


def has_transparency(png: Path) -> bool:
    """Return whether any pixel of the image is less than fully opaque."""
    with Image.open(png) as image:
        if "A" not in image.mode and "transparency" not in image.info:
            return False
        histogram = image.convert("RGBA").getchannel("A").histogram()
    return any(histogram[:-1])


def _shape(png: Path) -> tuple[tuple[int, int], str]:
    with Image.open(png) as image:
        return image.size, image.mode


@dataclass
class Plan:
    """The files a run would smooth, and the ones it leaves, by reason."""

    process: list[Path] = field(default_factory=list)
    skipped: dict[str, list[Path]] = field(default_factory=dict)

    def skip(self, why: str, relative: Path) -> None:
        """Record one file left alone, and why."""
        self.skipped.setdefault(why, []).append(relative)


def make_plan(
    root: Path, backup_dir: Path, includes: Sequence[str], excludes: Sequence[str]
) -> Plan:
    """Sort every file under the included folders into smooth or skip.

    Args:
        root: The panels folder.
        backup_dir: Where the originals of files already done are.
        includes: Top-level folder names; empty means every one.
        excludes: Globs against each file's path relative to ``root``.

    Returns:
        The plan, its paths relative to ``root`` and in sorted order.

    """
    plan = Plan()
    tops = sorted(includes) if includes else sorted(p.name for p in root.iterdir() if p.is_dir())
    for top in tops:
        for path in sorted((root / top).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(fnmatchcase(relative.as_posix(), glob) for glob in excludes):
                plan.skip(EXCLUDED, relative)
            elif path.suffix.lower() != ".png":
                plan.skip(NOT_PNG, relative)
            elif (backup_dir / relative).exists():
                plan.skip(DONE, relative)
            elif has_transparency(path):
                plan.skip(TRANSPARENT, relative)
            else:
                plan.process.append(relative)
    return plan


def smooth_one(root: Path, backup_dir: Path, relative: Path, run_filter: Filter) -> None:
    """Replace one PNG with its smoothed copy, its original kept in the backup folder.

    The filtered copy is written beside the original and checked before anything is
    touched, and the original is backed up before it is replaced, so a failure at any
    point leaves the original where it was.

    Raises:
        ValueError: The filtered copy has a different size or mode.

    """
    source = root / relative
    scratch = source.with_name(source.name + TEMP_SUFFIX)
    try:
        run_filter(source, scratch)
        if _shape(scratch) != _shape(source):
            msg = f"filtered copy is {_shape(scratch)}, the original {_shape(source)}"
            raise ValueError(msg)
        backup = backup_dir / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        scratch.replace(source)
    finally:
        scratch.unlink(missing_ok=True)


def report(plan: Plan, *, verbose: bool) -> None:
    """Say what the plan holds: counts by top-level folder, and every skip reason."""
    by_top: dict[str, int] = {}
    for relative in plan.process:
        by_top[relative.parts[0]] = by_top.get(relative.parts[0], 0) + 1
    _say(f"to smooth: {len(plan.process)}")
    for top, count in sorted(by_top.items()):
        _say(f"  {top}: {count}")
    for why, files in sorted(plan.skipped.items()):
        _say(f"skipped, {why}: {len(files)}")
        if verbose or why == TRANSPARENT:
            for relative in files:
                _say(f"  {relative}")


def apply(root: Path, backup_dir: Path, plan: Plan, run_filter: Filter) -> int:
    """Smooth every file of the plan; return 1 when any failed, else 0."""
    failed = 0
    for number, relative in enumerate(plan.process, start=1):
        try:
            smooth_one(root, backup_dir, relative, run_filter)
        except (OSError, ValueError, subprocess.CalledProcessError) as e:
            failed += 1
            _say(f"FAILED {relative}: {e}")
            continue
        if number % 100 == 0:
            _say(f"  {number} of {len(plan.process)}")
    _say(f"smoothed {len(plan.process) - failed}, failed {failed}")
    return 1 if failed else 0


def restore(root: Path, backup_dir: Path) -> int:
    """Put every backed-up original back and remove its backup; return the count."""
    count = 0
    for backup in sorted(p for p in backup_dir.rglob("*") if p.is_file()):
        target = root / backup.relative_to(backup_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
        backup.unlink()
        count += 1
    return count


def _refusal(given: Path, root: Path, backup_dir: Path, includes: Sequence[str]) -> str | None:
    """Return why the folders named cannot be used, or None when they can."""
    if not root.is_dir():
        return f"no such folder: {given}"
    if backup_dir == root or root in backup_dir.parents:
        return "the backup folder must be outside the panels folder"
    missing = [name for name in includes if not (root / name).is_dir()]
    if missing:
        return f"no such folder under {given}: {', '.join(missing)}"
    return None


def main(argv: list[str], run_filter: Filter | None = None) -> int:
    """Parse the arguments and plan, smooth or restore; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", type=Path, required=True, help="the panels folder")
    parser.add_argument("--backup-dir", type=Path, required=True, help="where originals go")
    parser.add_argument("--include", action="append", default=[], metavar="NAME")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    parser.add_argument("--amplitude", type=float, default=AMPLITUDE, help=f"default {AMPLITUDE:g}")
    parser.add_argument("--verbose", action="store_true", help="name every skipped file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="smooth the files; default: only say")
    mode.add_argument("--restore", action="store_true", help="put the originals back")
    args = parser.parse_args(argv)

    root, backup_dir = args.root.resolve(), args.backup_dir.resolve()
    refusal = _refusal(args.root, root, backup_dir, args.include)
    if refusal:
        _say(refusal)
        return 1

    if args.restore:
        _say(f"restored {restore(root, backup_dir)}")
        return 0
    plan = make_plan(root, backup_dir, args.include, args.exclude)
    report(plan, verbose=args.verbose)
    if not args.apply:
        _say("nothing changed: pass --apply to smooth them")
        return 0
    if run_filter is None:
        if shutil.which("gmic") is None:
            _say("gmic is not on the PATH: sudo apt install gmic")
            return 1
        run_filter = gmic_filter(args.amplitude)
    return apply(root, backup_dir, plan, run_filter)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
