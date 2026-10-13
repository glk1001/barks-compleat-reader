"""Tests for the docs reference check.

Each case is a way a doc has actually rotted here: a line number in the
walkthrough, a renamed module in a mocking example, a screenshot that became a
jpg, a flag a plan proposed and the script never grew, an env var the overnight
runner stopped reading, and a script the README named by its old name.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from check_docs_refs import RULES, Repo, check_docs, looks_like_path, main

if TYPE_CHECKING:
    from pathlib import Path


def _repo(root: Path, files: dict[str, str]) -> Repo:
    """Lay ``files`` (relative path to text) under ``root`` and return the Repo over them."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Repo(root, frozenset(files))


def _doc(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text), encoding="utf-8")
    return path


def _messages(repo: Repo, doc: Path, rules: tuple[str, ...] = RULES) -> list[str]:
    return [f"{f.rule}: {f.message}" for f in check_docs(repo, [doc], rules).findings]


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    # Nested, so a test that makes a sibling checkout beside the root has that parent to itself.
    return _repo(
        tmp_path / "repo",
        {
            "scripts/run_thing.sh": "# Usage: run_thing.sh [--headless] [--only NAME]\n",
            "scripts/check_it.py": 'add_argument("--quiet")\nenviron["BARKS_THING_SCOPE"]\n',
            "src/barks-reader/src/barks_reader/core/image_selector.py": "class ImageSelector:\n",
            "src/barks-reader/src/barks_reader/core/navigation/__init__.py": "",
            "website/shot.jpg": "",
            "docs/icon.png": "",
        },
    )


class TestLineNumbers:
    def test_a_line_number_in_an_evergreen_doc_is_flagged(self, repo: Repo) -> None:
        doc = _doc(
            repo.root, "README.md", "See `core/image_selector.py:118` and `main.py:92-96`.\n"
        )
        messages = _messages(repo, doc, ("line-number",))
        assert len(messages) == 2  # noqa: PLR2004
        assert "name the symbol, not the line" in messages[0]

    def test_a_dated_note_may_keep_them(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/plans/thing.md", "Fixed at `core/image_selector.py:118`.\n")
        assert _messages(repo, doc, ("line-number",)) == []

    def test_an_x_display_number_is_not_a_line_number(self, repo: Repo) -> None:
        doc = _doc(repo.root, "README.md", "Workers run on displays `:2` to `:5`.\n")
        assert _messages(repo, doc) == []


class TestPaths:
    def test_a_missing_script_is_flagged_and_an_existing_one_is_not(self, repo: Repo) -> None:
        doc = _doc(repo.root, "README.md", "Run `scripts/run_thing.sh` or `scripts/gone.sh`.\n")
        assert _messages(repo, doc, ("path",)) == ["path: `scripts/gone.sh` does not exist"]

    def test_a_bare_script_name_resolves_by_suffix(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "`run_thing.sh` runs it; `run_other.sh` is gone.\n")
        assert _messages(repo, doc, ("path",)) == ["path: `run_other.sh` does not exist"]

    def test_a_package_relative_path_resolves_through_the_workspace(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "See `barks_reader/core/image_selector.py`.\n")
        assert _messages(repo, doc, ("path",)) == []

    def test_a_two_segment_directory_is_checked_and_a_bare_one_is_shorthand(
        self, repo: Repo
    ) -> None:
        doc = _doc(repo.root, "docs/x.md", "Tests: `scripts/tests/`; see `scripts/`, `core/`.\n")
        assert _messages(repo, doc, ("path",)) == ["path: `scripts/tests/` does not exist"]

    def test_a_package_folder_resolves_one_level_down(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "The model is `core/navigation/`; see `core/gone/`.\n")
        assert _messages(repo, doc, ("path",)) == ["path: `core/gone/` does not exist"]

    def test_a_dated_note_is_judged_only_on_paths_from_a_repo_top_folder(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "docs/plans/x.md",
            "Proposed `screens/title_view.py`, `tools/whoosh_find.py` and `gui_probe_win.py`; "
            "the probe `scripts/gui_probe_win.py` with `--gone`; `BARKS_NOPE`; `main.py:12`.\n",
        )
        assert _messages(repo, doc) == ["path: `scripts/gui_probe_win.py` does not exist"]

    def test_a_sibling_checkout_satisfies_a_path(self, repo: Repo) -> None:
        wiki = repo.root.parent / "barks-wiki"
        (wiki / "okf" / "reference").mkdir(parents=True)
        (wiki / "okf" / "reference" / "chronology.md").write_text("", encoding="utf-8")
        (wiki / "scripts").mkdir()
        (wiki / "scripts" / "export_reader_wiki.py").write_text("", encoding="utf-8")
        doc = _doc(
            repo.root,
            "docs/x.md",
            "`okf/reference/chronology.md`, `chronology.md`, `export_reader_wiki.py`, "
            "`okf/no.md`\n",
        )
        assert _messages(repo, doc, ("path",)) == ["path: `okf/no.md` does not exist"]

    def test_code_blocks_are_read_as_command_lines(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "docs/x.md",
            """
            ```bash
            bash scripts/run_thing.sh --headless
            uv run scripts/old_name.py
            ```
            """,
        )
        assert _messages(repo, doc, ("path",)) == ["path: `scripts/old_name.py` does not exist"]

    def test_a_runtime_file_name_on_its_own_is_left_alone(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "Settings are in `barks-reader.json` and `app.ini`.\n")
        assert _messages(repo, doc, ("path",)) == []

    def test_a_sibling_repo_path_is_judged_only_when_the_sibling_exists(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "The wiki's `../barks-wiki/okf/index.md`.\n")
        assert _messages(repo, doc, ("path",)) == []
        (repo.root.parent / "barks-wiki").mkdir()
        assert _messages(repo, doc, ("path",)) == [
            "path: `../barks-wiki/okf/index.md` does not exist"
        ]

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("scripts/run_thing.sh", True),
            ("run_thing.sh", True),
            ("docs/plans/", True),
            ("build/overnight/<stamp>/summary.txt", False),
            ("~/opt/barks-reader/config", False),
            ("C:/Users/me/nightly-job/test.ps1", False),
            ("barks-fantagraphics/.../title_search.py", False),
            ("config/barks-reader.ini", False),
            ("website/shot.png", True),
            ("core/config_info.py", True),
            ("core/", False),
            ("../barks-wiki/okf/index.md", True),
            ("https://example.org/a.py", False),
            ("--headless", False),
            ("barks-reader.json", False),
            (".py", False),
            ("$HOME/x.py", False),
        ],
    )
    def test_what_looks_like_a_path(self, token: str, *, expected: bool) -> None:
        assert looks_like_path(token) is expected


class TestModules:
    def test_a_module_and_a_symbol_in_it_resolve(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "docs/x.md",
            "`barks_reader.core.image_selector.ImageSelector`, `barks_reader.core.navigation`.\n",
        )
        assert _messages(repo, doc, ("module",)) == []

    def test_a_renamed_module_is_flagged_where_it_stopped(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "AGENTS.md",
            "Use `patch.object` not `barks_reader.core.image_file_getter.TitleImageFileGetter`.\n",
        )
        (message,) = _messages(repo, doc, ("module",))
        assert message == (
            "module: `barks_reader.core.image_file_getter.TitleImageFileGetter` does not resolve"
            " (stopped at `image_file_getter.TitleImageFileGetter`)"
        )

    def test_a_missing_symbol_is_flagged(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "`barks_reader.core.image_selector.OldSelector`\n")
        assert len(_messages(repo, doc, ("module",))) == 1

    def test_a_package_outside_the_workspace_is_not_judged(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "`kivy.uix.widget.Widget` and `okf_reader.ui.viewer`.\n")
        assert _messages(repo, doc, ("module",)) == []


class TestFlags:
    def test_a_flag_the_script_has_passes_and_one_it_lacks_fails(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "docs/x.md",
            "`scripts/run_thing.sh --headless --soft-gl`, then `check_it.py --quiet --help`.\n",
        )
        assert _messages(repo, doc, ("flag",)) == [
            "flag: `scripts/run_thing.sh` has no `--soft-gl`"
        ]

    def test_a_flag_with_a_value_is_checked_by_name(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "`run_thing.sh --only=gui --app=PATH`\n")
        assert _messages(repo, doc, ("flag",)) == ["flag: `run_thing.sh` has no `--app`"]

    def test_a_flag_in_prose_with_no_script_beside_it_is_not_judged(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/x.md", "Pass `--soft-gl` to it.\n")
        assert _messages(repo, doc, ("flag",)) == []


class TestLinks:
    def test_a_missing_image_and_a_present_one(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "README.md",
            "![a](website/shot.png) ![b](website/shot.jpg) [c](docs/x.md#there) [d](https://x.y/)\n",
        )
        assert _messages(repo, doc, ("link",)) == [
            "link: link target `website/shot.png` is missing",
            "link: link target `docs/x.md#there` is missing",
        ]

    def test_an_img_tag_resolves_against_the_doc_folder(self, repo: Repo) -> None:
        doc = _doc(repo.root, "docs/how.md", '<img src="icon.png" width="15"> <img src="no.png">\n')
        assert _messages(repo, doc, ("link",)) == ["link: link target `no.png` is missing"]


class TestEnv:
    def test_a_variable_nothing_reads_is_flagged(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "README.md",
            "`BARKS_THING_SCOPE` picks the share; `BARKS_THING_DAY` used to. `BARKS_OVERNIGHT_*`\n",
        )
        assert _messages(repo, doc, ("env",)) == [
            "env: `BARKS_THING_DAY` is set or read nowhere in the repo"
        ]


class TestWaivers:
    def test_an_ok_mark_skips_the_line(self, repo: Repo) -> None:
        doc = _doc(
            repo.root,
            "README.md",
            "Not `scripts/gone.sh` <!-- docs-refs: ok -->\nBut `scripts/also_gone.sh`.\n",
        )
        assert _messages(repo, doc, ("path",)) == ["path: `scripts/also_gone.sh` does not exist"]

    def test_a_skip_mark_skips_the_doc(self, repo: Repo) -> None:
        doc = _doc(repo.root, "README.md", "<!-- docs-refs: skip -->\n`scripts/gone.sh`\n")
        assert _messages(repo, doc) == []


class TestMain:
    def test_exit_code_and_report(self, repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
        good = _doc(repo.root, "docs/good.md", "`scripts/run_thing.sh --headless`\n")
        bad = _doc(repo.root, "docs/bad.md", "`scripts/gone.sh`\n")
        assert main(["--root", str(repo.root), str(good)]) == 0
        assert "1 path" in capsys.readouterr().out
        assert main(["--root", str(repo.root), str(good), str(bad)]) == 1
        out = capsys.readouterr().out
        assert "docs/bad.md:1: [path] `scripts/gone.sh` does not exist" in out

    def test_only_narrows_the_rules(self, repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
        bad = _doc(repo.root, "docs/bad.md", "`scripts/gone.sh` `BARKS_NOPE`\n")
        assert main(["--root", str(repo.root), "--only", "env", str(bad)]) == 1
        out = capsys.readouterr().out
        assert "[env]" in out
        assert "[path]" not in out

    def test_quiet_prints_nothing_when_all_is_well(
        self, repo: Repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        good = _doc(repo.root, "docs/good.md", "`scripts/run_thing.sh`\n")
        assert main(["--root", str(repo.root), "--quiet", str(good)]) == 0
        assert capsys.readouterr().out == ""
