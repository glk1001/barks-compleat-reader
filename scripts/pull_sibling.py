#!/usr/bin/env python3
"""Bring a sibling repo up to its upstream, as the main repo is pulled before a run.

Nothing else pulls the sibling repos on an overnight machine, and one left behind
fails the siblings stage on a name this repo has since changed: on 2026-10-05 the
Linux overnight machine's barks-comic-building was six days old and its type checks
failed on two title-search methods this repo had dropped and the sibling had stopped
calling that morning. barks-wiki, left behind, makes the wiki copy look current
against a checkout days old (the Windows laptop's, 2026-10-09: eight days).

Only a repo that is behind its upstream, has not diverged from it and has no
uncommitted changes to tracked files is moved, by a fast-forward; anything else is
left as it is and said, so a session working in the sibling never has its work
pulled from under it. Nothing is committed or written there but the fast-forward.

Python rather than bash so the Windows and macOS overnight runner can import it
(run_overnight_desktop.py); run_overnight.sh runs it as a script.

Usage: pull_sibling.py REPO [--stage NAME]
  --stage  the overnight stage its messages start with (default: siblings)
Exit: 0 up to date or fast-forwarded; 1 left as it is (the reason on stdout).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (git on a sibling repo, fixed arguments)
        ["git", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _count(repo: Path, revisions: str) -> int:
    return int(_git(repo, "rev-list", "--count", revisions).stdout.strip() or 0)


def _refusal(repo: Path, behind: int, ahead: int) -> str | None:
    """Return why a repo behind its upstream may not be fast-forwarded, or None."""
    if ahead > 0:
        return f"{behind} commit(s) behind and {ahead} ahead of its upstream (diverged)"
    if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return f"{behind} commit(s) behind, with uncommitted changes"
    return None


def pull(repo: Path, stage: str = "siblings") -> tuple[bool, str]:
    """Fast-forward a sibling repo to its upstream where that is safe.

    Args:
        repo: The sibling's checkout.
        stage: The overnight stage the message starts with.

    Returns:
        Whether it is now up to date, and a line saying what was done or why not.

    """
    say = f"{stage}: {repo.name}:"
    if _git(repo, "fetch", "--quiet").returncode != 0:
        return False, f"{say} could not fetch; used as it is"
    upstream = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        return False, f"{say} its branch has no upstream; used as it is"
    behind = _count(repo, "HEAD..@{u}")
    ahead = _count(repo, "@{u}..HEAD")
    if behind == 0:
        return True, f"{say} up to date"
    refusal = _refusal(repo, behind, ahead)
    if refusal is not None:
        return False, f"{say} {refusal}; not pulled, used as it is"
    if _git(repo, "merge", "--ff-only", "--quiet", "@{u}").returncode != 0:
        return False, f"{say} {behind} commit(s) behind, but the fast-forward failed; used as it is"
    head = _git(repo, "log", "-1", "--format=%h %s").stdout.strip()
    return True, f"{say} pulled {behind} commit(s), now at {head}"


def main(argv: list[str] | None = None) -> int:
    """Pull the named sibling, print what was done, and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("--stage", default="siblings")
    args = parser.parse_args(argv)
    ok, message = pull(args.repo, args.stage)
    print(message)  # noqa: T201 (the overnight stage's log)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
