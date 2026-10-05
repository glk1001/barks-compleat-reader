"""pull_sibling.sh: a sibling repo is brought up to its upstream only where that is safe.

Each test builds a real upstream and a clone of it in a temporary directory. Run
from a git hook (pre-push runs the suite), git's GIT_DIR and the like are set and
beat -C, so they are cleared, and the throwaway repos run no hooks.
"""

# cspell:ignore NOSYSTEM gpgsign pytestmark

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "pull_sibling.sh"

# The script runs only in the Linux overnight runner's siblings stage. On Windows
# "bash" can be WSL's launcher, which fails with no distribution installed (CI's).
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="pull_sibling.sh runs in the Linux overnight runner only"
)


@pytest.fixture(autouse=True)
def _no_outer_git(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 (git on a throwaway repo, fixed arguments)
        [
            *("git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"),
            *("-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", name)


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """Return an upstream with one commit, and a clone of it tracking its branch."""
    upstream, sibling = tmp_path / "upstream", tmp_path / "barks-sibling"
    upstream.mkdir()
    _git(upstream, "init", "-q", "-b", "main")
    _commit(upstream, "a.txt", "a\n")
    subprocess.run(  # noqa: S603 (cloning the throwaway upstream)
        ["git", "clone", "-q", str(upstream), str(sibling)],  # noqa: S607
        check=True,
        capture_output=True,
    )
    return upstream, sibling


def _pull(sibling: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (the script under test)
        ["bash", str(SCRIPT), str(sibling)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def test_up_to_date_is_left_alone(repos: tuple[Path, Path]) -> None:
    _, sibling = repos
    done = _pull(sibling)
    assert done.returncode == 0
    assert done.stdout.strip() == "siblings: barks-sibling: up to date"


def test_behind_and_clean_is_fast_forwarded(repos: tuple[Path, Path]) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    _commit(upstream, "c.txt", "c\n")

    done = _pull(sibling)

    assert done.returncode == 0
    assert "pulled 2 commit(s), now at" in done.stdout
    assert _git(sibling, "rev-parse", "HEAD") == _git(upstream, "rev-parse", "HEAD")


def test_uncommitted_changes_are_never_pulled_over(repos: tuple[Path, Path]) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    (sibling / "a.txt").write_text("being edited\n", encoding="utf-8")
    before = _git(sibling, "rev-parse", "HEAD")

    done = _pull(sibling)

    assert done.returncode == 1
    assert "1 commit(s) behind, with uncommitted changes; not pulled" in done.stdout
    assert _git(sibling, "rev-parse", "HEAD") == before
    assert (sibling / "a.txt").read_text(encoding="utf-8") == "being edited\n"


def test_an_untracked_file_does_not_stop_a_pull(repos: tuple[Path, Path]) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    (sibling / "notes.txt").write_text("mine\n", encoding="utf-8")

    assert _pull(sibling).returncode == 0
    assert (sibling / "b.txt").is_file()
    assert (sibling / "notes.txt").is_file()


def test_a_diverged_branch_is_left_as_it_is(repos: tuple[Path, Path]) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    _commit(sibling, "local.txt", "local\n")
    before = _git(sibling, "rev-parse", "HEAD")

    done = _pull(sibling)

    assert done.returncode == 1
    assert "1 commit(s) behind and 1 ahead of its upstream (diverged)" in done.stdout
    assert _git(sibling, "rev-parse", "HEAD") == before


def test_ahead_only_is_up_to_date(repos: tuple[Path, Path]) -> None:
    """Local commits not yet pushed: nothing to pull, nothing to warn about."""
    _, sibling = repos
    _commit(sibling, "local.txt", "local\n")
    done = _pull(sibling)
    assert done.returncode == 0
    assert "up to date" in done.stdout


def test_a_branch_with_no_upstream_is_tested_as_it_is(repos: tuple[Path, Path]) -> None:
    _, sibling = repos
    _git(sibling, "checkout", "-q", "-b", "experiment")
    done = _pull(sibling)
    assert done.returncode == 1
    assert "its branch has no upstream" in done.stdout


def test_an_upstream_that_cannot_be_reached_is_said(repos: tuple[Path, Path]) -> None:
    upstream, sibling = repos
    upstream.rename(upstream.with_name("gone"))
    done = _pull(sibling)
    assert done.returncode == 1
    assert "could not fetch" in done.stdout
