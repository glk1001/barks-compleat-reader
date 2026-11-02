"""The release scripts' shell constants and their pack size check.

The constants match the ones core/data_pack.py owns, and the size check holds a pack to
GitHub's limit on a release asset.
"""

# cspell:ignore pytestmark

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, PACK_MEMBER

_RELEASE_SH = Path(__file__).resolve().parent.parent / "_data_release.sh"


def _shell_value(name: str) -> str:
    match = re.search(rf'^{name}="([^"]*)"$', _RELEASE_SH.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None, f"{name} is not set in {_RELEASE_SH.name}"
    return match.group(1)


def test_the_pack_names_and_the_version_member_are_the_readers() -> None:
    assert (_shell_value("DATA1_ZIP"), _shell_value("DATA2_ZIP")) == DATA_PACK_FILE_NAMES
    assert _shell_value("PACK_MEMBER") == PACK_MEMBER


GIB = 1024**3

# A bare "bash" on the Windows runner is WSL with no distro installed.
needs_bash = pytest.mark.skipif(sys.platform == "win32", reason="needs a real bash")


def _run_sourced(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run `command` in a bash that has sourced _data_release.sh, with `args` as $1...."""
    return subprocess.run(  # noqa: S603
        ["bash", "-c", f'source "{_RELEASE_SH}" && {command}', "bash", *args],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@needs_bash
def test_the_limit_is_github_s_2_gib_and_the_warning_starts_at_90_percent() -> None:
    result = _run_sourced('echo "$ASSET_LIMIT_BYTES $ASSET_WARN_BYTES"')

    limit, warn = map(int, result.stdout.split())
    assert limit == 2 * GIB
    assert warn == pytest.approx(0.9 * limit, abs=10)


@needs_bash
@pytest.mark.parametrize(
    ("size", "passes", "says"),
    [
        (1024**2, True, ""),
        (round(1.21 * GIB), True, ""),  # pack 2 as data-v9 published it
        (round(0.9 * 2 * GIB) + 10, True, "WARNING"),
        (2 * GIB - 1, True, "WARNING"),
        (2 * GIB, False, "GitHub refuses"),
        (3 * GIB, False, "GitHub refuses"),
    ],
)
def test_a_pack_is_held_to_github_s_limit(
    tmp_path: Path, size: int, passes: bool, says: str
) -> None:
    pack = tmp_path / "barks-reader-data-2.barkspack"
    with pack.open("wb"):
        pass
    os.truncate(pack, size)  # sparse: no disk is written

    result = _run_sourced('check_pack_size "$1"', str(pack))

    assert (result.returncode == 0) is passes
    if says:
        assert says in result.stderr
    else:
        assert result.stderr == ""


@needs_bash
def test_a_missing_pack_fails_the_check(tmp_path: Path) -> None:
    assert _run_sourced('check_pack_size "$1"', str(tmp_path / "none")).returncode != 0
