"""Small builders that more than one script test file needs.

Reached as ``script_test_helpers``: the conftest puts this directory on ``sys.path``.
"""

# cspell:ignore gpgsign

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

# A bare "bash" on the Windows runner is WSL with no distro installed.
needs_bash = pytest.mark.skipif(sys.platform == "win32", reason="needs a real bash")


def write_tree(root: Path, files: Mapping[str, str | bytes]) -> Path:
    """Lay `files` (relative path to its text or bytes) under `root`; return `root`.

    Text is written as UTF-8 whatever the platform: the scripts read it so.
    """
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return root


def git(repo: Path, *args: str) -> str:
    """Run git in a throwaway `repo` with no hooks, signing or identity of the machine's.

    The ``no_outer_git`` fixture is its other half: it clears the ``GIT_*`` variables
    a hook sets, which beat ``-C``, and the machine's own configuration.
    """
    done = subprocess.run(  # noqa: S603 (git on a throwaway repo, fixed arguments)
        [
            *("git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"),
            *("-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout.strip()
