"""pull_sibling.py: a sibling repo is brought up to its upstream only where that is safe.

Each test builds a real upstream and a clone of it in a temporary directory. Run
from a git hook (pre-push runs the suite), git's GIT_DIR and the like are set and
beat -C, so they are cleared, and the throwaway repos run no hooks.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pull_sibling
import pytest
from script_test_helpers import git

if TYPE_CHECKING:
    from collections.abc import Callable

    Pull = Callable[..., "Done"]

SCRIPT = Path(__file__).resolve().parent.parent / "pull_sibling.py"


@pytest.fixture(autouse=True)
def _no_outer_git(no_outer_git: None) -> None:
    """Every test here makes its own repositories."""


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", name)


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """Return an upstream with one commit, and a clone of it tracking its branch."""
    upstream, sibling = tmp_path / "upstream", tmp_path / "barks-sibling"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    _commit(upstream, "a.txt", "a\n")
    subprocess.run(  # noqa: S603 (cloning the throwaway upstream)
        ["git", "clone", "-q", str(upstream), str(sibling)],  # noqa: S607
        check=True,
        capture_output=True,
    )
    return upstream, sibling


class Done(NamedTuple):
    """What a run of the script left: its exit status and what it printed."""

    returncode: int
    stdout: str


@pytest.fixture
def pull(capsys: pytest.CaptureFixture[str]) -> Callable[..., Done]:
    """Run the script's main on a sibling, in this process: its git calls are real."""

    def _pull(sibling: Path, *args: str) -> Done:
        status = pull_sibling.main([str(sibling), *args])
        return Done(status, capsys.readouterr().out)

    return _pull


def test_up_to_date_is_left_alone(repos: tuple[Path, Path], pull: Pull) -> None:
    _, sibling = repos
    done = pull(sibling)
    assert done.returncode == 0
    assert done.stdout.strip() == "siblings: barks-sibling: up to date"


def test_behind_and_clean_is_fast_forwarded(repos: tuple[Path, Path], pull: Pull) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    _commit(upstream, "c.txt", "c\n")

    done = pull(sibling)

    assert done.returncode == 0
    assert "pulled 2 commit(s), now at" in done.stdout
    assert git(sibling, "rev-parse", "HEAD") == git(upstream, "rev-parse", "HEAD")


def test_uncommitted_changes_are_never_pulled_over(repos: tuple[Path, Path], pull: Pull) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    (sibling / "a.txt").write_text("being edited\n", encoding="utf-8")
    before = git(sibling, "rev-parse", "HEAD")

    done = pull(sibling)

    assert done.returncode == 1
    assert "1 commit(s) behind, with uncommitted changes; not pulled" in done.stdout
    assert git(sibling, "rev-parse", "HEAD") == before
    assert (sibling / "a.txt").read_text(encoding="utf-8") == "being edited\n"


def test_an_untracked_file_does_not_stop_a_pull(repos: tuple[Path, Path], pull: Pull) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    (sibling / "notes.txt").write_text("mine\n", encoding="utf-8")

    assert pull(sibling).returncode == 0
    assert (sibling / "b.txt").is_file()
    assert (sibling / "notes.txt").is_file()


def test_a_diverged_branch_is_left_as_it_is(repos: tuple[Path, Path], pull: Pull) -> None:
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    _commit(sibling, "local.txt", "local\n")
    before = git(sibling, "rev-parse", "HEAD")

    done = pull(sibling)

    assert done.returncode == 1
    assert "1 commit(s) behind and 1 ahead of its upstream (diverged)" in done.stdout
    assert git(sibling, "rev-parse", "HEAD") == before


def test_ahead_only_is_up_to_date(repos: tuple[Path, Path], pull: Pull) -> None:
    """Local commits not yet pushed: nothing to pull, nothing to warn about."""
    _, sibling = repos
    _commit(sibling, "local.txt", "local\n")
    done = pull(sibling)
    assert done.returncode == 0
    assert "up to date" in done.stdout


def test_a_branch_with_no_upstream_is_tested_as_it_is(repos: tuple[Path, Path], pull: Pull) -> None:
    _, sibling = repos
    git(sibling, "checkout", "-q", "-b", "experiment")
    done = pull(sibling)
    assert done.returncode == 1
    assert "its branch has no upstream" in done.stdout


def test_an_upstream_that_cannot_be_reached_is_said(repos: tuple[Path, Path], pull: Pull) -> None:
    upstream, sibling = repos
    upstream.rename(upstream.with_name("gone"))
    done = pull(sibling)
    assert done.returncode == 1
    assert "could not fetch" in done.stdout


def test_the_stage_names_the_message(repos: tuple[Path, Path], pull: Pull) -> None:
    """The desktop runner's wiki-copy stage pulls barks-wiki under its own name."""
    _, sibling = repos

    done = pull(sibling, "--stage", "wiki-copy")

    assert done.stdout.strip() == "wiki-copy: barks-sibling: up to date"


def test_a_fast_forward_git_refuses_is_said(repos: tuple[Path, Path], pull: Pull) -> None:
    """An untracked file the upstream now adds: clean by git's count, yet not mergeable."""
    upstream, sibling = repos
    _commit(upstream, "b.txt", "theirs\n")
    (sibling / "b.txt").write_text("mine\n", encoding="utf-8")
    before = git(sibling, "rev-parse", "HEAD")

    done = pull(sibling)

    assert done.returncode == 1
    assert "1 commit(s) behind, but the fast-forward failed; used as it is" in done.stdout
    assert git(sibling, "rev-parse", "HEAD") == before
    assert (sibling / "b.txt").read_text(encoding="utf-8") == "mine\n"


def test_the_script_runs_as_a_program(repos: tuple[Path, Path]) -> None:
    """As the overnight stage runs it: its status is the exit code, its line on stdout."""
    upstream, sibling = repos
    _commit(upstream, "b.txt", "b\n")
    _commit(sibling, "local.txt", "local\n")

    done = subprocess.run(  # noqa: S603 (the script under test)
        [sys.executable, str(SCRIPT), str(sibling)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert done.returncode == 1
    assert done.stdout.strip().startswith("siblings: barks-sibling: 1 commit(s) behind and 1 ahead")
