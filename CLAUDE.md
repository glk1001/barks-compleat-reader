# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Compleat Barks Disney Reader is a Kivy-based Python desktop application for browsing and
reading the Fantagraphics Carl Barks comic library. It is packaged as a standalone executable
via Nuitka (`--mode=app`): a single-file onefile binary on Linux/Windows, a zipped `.app`
bundle on macOS.

## Commands

A clean machine's whole setup, in order (system packages, tools, sibling repos, hooks,
secrets, data, the one-off calibrations and the checks that say what is missing), is in
`docs/setup.md`; keep it current when a new tool or package becomes necessary.

**First-time setup (after cloning):**
```bash
uv run prek install
```
The hooks run on [prek](https://github.com/j178/prek), as in the two sibling repos; it comes from
the `dev` dependency group (`uv sync`) and reads `.pre-commit-config.yaml`. The cspell hooks also
need [bun](https://bun.sh) on the PATH (on Windows it also needs a `bunx.cmd`: `docs/setup.md`).
The pre-commit stage also runs [gitleaks](https://github.com/gitleaks/gitleaks) (secrets in what is
staged), the one hook not from the uv venv: prek builds its pinned release once per machine, about
30 s on the first commit, fetching Go itself.
`default_install_hook_types` in `.pre-commit-config.yaml` makes that one command write all three
hook types. Without it, only `.git/hooks/pre-commit` is written and the pre-push (full-suite
pytest) and commit-msg (cspell) gates are silently absent — the failure mode is a green commit and
a red CI. To verify, `.git/hooks/pre-push` should name `--hook-type=pre-push`. A clone made
while the repo used git-lfs (before 2026-10-03) has LFS hooks to retire: `docs/setup.md`, step 4.

A clone whose hooks pre-commit installed (before 2026-09-29) moves over with
`uv run pre-commit uninstall && uv run prek install`, run before syncing past that date: the
uninstall puts the LFS hook back, and prek chains it again. Once pre-commit has left the venv,
`uvx pre-commit uninstall` does the first half. Until then its hooks fail and block commits.

Then generate the two gitignored modules every workspace boot imports:
```bash
bash scripts/generate-panel-module.sh   # comic_utils/get_panel_bytes.py; needs BARKS_ZIPS_KEY in .env.runtime
bash scripts/build.sh                   # barks_reader/_version.py (its first step writes it)
```
Without them the app dies on an import at boot (so every GUI test fails at its boot timeout;
`run_gui_tests.sh` checks for both first), and ty, pyrefly and full-lint refuse to run. Running
the app does not create either.

**Run benchmarks** (excluded from the default test run; `--quiet` for just the tables):
```bash
bash scripts/run_benchmark.sh
```

**Run the whole repo overnight** (results in `build/overnight/<stamp>/summary.txt`; on Windows
or macOS, `uv run python scripts/run_overnight_desktop.py`). Setting up another machine, the
desktop runner, the nightly schedule, macOS permissions and cross-platform coverage: the
`overnight-runs` skill (`.claude/skills/overnight-runs/SKILL.md`).
```bash
bash scripts/run_overnight.sh
```

**Run every GUI test overnight** (the suite on each comic and panel source, the settings
matrix, a 1080p screen, touch, the soak; `--list`, `--only`, `--skip`, `--app PATH`):
```bash
bash scripts/run_gui_overnight.sh
```
Ctrl-C or `kill` of any GUI runner stops everything it started. After a `kill -9`
the next run clears the leftovers, or `bash scripts/gui-probe.sh cleanup` does (`--all`
also stops a display started by hand).

**Run the GUI path tests** (excluded from the default test run; boots the real app on
the nested Xephyr display via `scripts/gui-probe.sh`, driven by `scripts/gui_driver.py`):
```bash
bash scripts/run_gui_tests.sh
```

**Type-check (pyrefly):**
A second type checker gated alongside `ty` (CI, pre-commit, `full-lint.sh`) — faster and stricter on
nullability. Config + rationale in `pyrefly.toml`. Structural Kivy noise is suppressed via config; the
remaining residual is grandfathered in `pyrefly-baseline.json`, so the gate passes at **0 new** and
only regressions fail it. Refresh the baseline after intentionally changing that set.
```bash
bash scripts/pyrefly.sh                    # or: uv run pyrefly check
bash scripts/pyrefly.sh --update-baseline  # refresh grandfathered findings
```

**Spell-check (cspell):**
```bash
bunx cspell
```

**Check the docs name things that exist** (paths, modules, script flags, links, `BARKS_*`
variables; no line numbers in the evergreen docs; `--only RULE`, `--quiet`):
```bash
uv run scripts/check_docs_refs.py
```

**Run all lint/static checks plus benchmarks (ruff check+format, ty, pyrefly, import-linter, deptry, vulture, relative imports, .kv imports, the GUI-key check, cspell, benchmark compare; `uv audit` and the wiki story-order check warn only; add `--with-gui-test` to also run the GUI path tests headless, quietly):**
```bash
bash scripts/full-lint.sh
bash scripts/full-lint.sh --with-gui-test
```

**Check only uncommitted files (ruff/ty/cspell/.kv imports):**
```bash
bash scripts/git-ruff.sh
bash scripts/git-ty.sh
bash scripts/git-cspell.sh
bash scripts/git-kv.sh
```

**Bump the pinned toolchain (monthly):**
`ruff` and `ty` are `==`-pinned in `pyproject.toml` (a `select = ["ALL"]` ruff release
changes our lint policy; ty is a 0.0.x beta that has shipped a flaky panic). This moves
them forward on a branch, re-locks, and runs every gate — it never commits or pushes.
Full rationale and triage steps in `docs/toolchain-bump.md`.
```bash
bash scripts/bump-toolchain.sh
```

**Build standalone executable:**
```bash
bash scripts/build.sh
```

## Architecture

### Cross-Repository Dependencies

`src/barks-fantagraphics/` and `src/comic-utils/` are also consumed by sibling repositories:
- `../barks-ocr/` — OCR pipeline
- `../barks-comic-building/` — comic image build pipeline

Breaking changes to the public API of either package require coordinated updates in those repos.

### barks-wiki (read-only)

The sibling `../barks-wiki` repo (the OKF knowledge bundle and its generators, e.g.
`okf/reference/data/generate_tables.py`) is maintained by its own Claude sessions.
**Treat it as read-only from this repo** — never edit, regenerate, or commit there, even when
a change here seems to call for it. Raise the need instead.

Joining stories to wiki pages and displaying story titles follow one convention (identity is the
plain canonical title; parentheses are presentation). Before doing either, read
`.claude/skills/wiki-title-convention/SKILL.md`.

### Source Packages

All code under `src/` is a **uv workspace**; each package installs editable into the shared `.venv` — no `PYTHONPATH` setup needed for development or tooling.

Entry point: `main.py` (root). Run `uv sync` after cloning to install all workspace packages. The standalone build needs no special workspace handling: Nuitka compiles `main.py` from the synced workspace `.venv`, with each app package and its data pulled in explicitly via the `--include-package`/`--include-package-data`/`--include-data-dir` flags in `scripts/build.sh` (a new package or data dir must be added there).

### Import Layering

Enforced by `import-linter` (`.importlinter`).

Always run `uv run lint-imports` after any code changes — not just when imports change.

### Navigation model

`barks_reader.core.navigation` owns tree-view navigation policy independent of Kivy — a
`Destination` hierarchy plus `NavigationModel`. Payloads live on destinations, not on widget
subclasses, and widgets/coordinators route through the model rather than switching on widget
subclass. Adding a new navigable target = add a `Destination` subclass + register it in the model.

### Kivy Initialization Order (Critical)

`barks_reader.core.config_info` **must be imported before any Kivy imports** to redirect `KIVY_HOME` to the app's config directory. `main.py` enforces this at the top with a comment.

### Testing

- Unit tests are in each package's `tests/` (`src/barks-reader/tests/unit/`,
  `src/barks-fantagraphics/tests/`, `src/barks-build-comic-images/tests/`, `src/okf-reader/tests/`,
  `src/comic-utils/tests/`) and the scripts' in `scripts/tests/`; see `testpaths` in `pyproject.toml`.
  Benchmarks are in `src/barks-reader/tests/benchmarks/` and are excluded from the default `uv run pytest` run.
  CI's `diff-coverage` job holds the lines a push changes to 80% coverage (`diff-cover`;
  `scripts/diff-cover.sh` runs it locally).
- Corpus consistency (every title's panel files, prebuilt comic, layout, panel-segments
  JSONs, wiki joins and splash tags) is `scripts/validate-barks-reader-files.py`, run against the real
  data pack, nightly rather than in a gate; its tests are in `scripts/tests/`. The GUI tests
  assert one sample title each and leave the whole corpus to it.
- Use `pytest` fixtures and `patch.object(module, ClassName)` style mocking — **not** string-path patching like `patch("barks_reader.core.module.ClassName")`. <!-- docs-refs: ok -->
- Docs name paths and symbols, never line numbers (`core/image_selector.py` and
  `ImageSelector`, not the file with a colon and a line): `scripts/check_docs_refs.py` holds the
  README, `CLAUDE.md` and `docs/*.md` to that and to naming files, modules, flags, links
  and `BARKS_*` variables that exist (warn-only in `full-lint.sh` and the overnight run;
  the pre-commit hook gates the line numbers). A dated note under `docs/plans/` keeps its
  record. A line that must name something gone carries `<!-- docs-refs: ok -->`.
- GUI path tests are in `src/barks-reader/tests/gui/` (outside `testpaths`; run with
  `bash scripts/run_gui_tests.sh`; runners, options, taps, leak tests and timing budgets:
  `src/barks-reader/tests/gui/CLAUDE.md`). They boot the real app from a scratch profile and
  wait only on lines the app logs, so a screen's log markers are part of its contract: when a
  user-visible transition gets no log line, add one (with a `loguru_sink` unit test) rather
  than a sleep. A GUI test presses only the remote's six keys (Escape, Return, Up, Down,
  Left, Right): `scripts/check_gui_keys.py` (pre-commit, CI, full-lint) fails on any other,
  unless the call carries `# desktop key: <why>`.
