# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Compleat Barks Disney Reader is a Kivy-based Python desktop application for browsing and
reading the Fantagraphics Carl Barks comic library. It is packaged as a standalone executable
via Nuitka (`--mode=app`): a single-file onefile binary on Linux/Windows, a zipped `.app`
bundle on macOS.

## Commands

**First-time setup (after cloning, and after any `git lfs install`):**
```bash
uv run pre-commit install
```
`pre-commit` comes from the `dev` dependency group (`uv sync`); the cspell hooks also need
[bun](https://bun.sh) on the PATH (on Windows, `winget install Oven-sh.Bun`, whose package lacks
`bunx`: beside `bun.exe`, add a `bunx.cmd` holding `@"%~dp0bun.exe" x %*`. A `bunx.exe` link does
not do: pre-commit runs it as `bunx.EXE`, and bun matches its own name case-sensitively).
`default_install_hook_types` in `.pre-commit-config.yaml` makes that one command write all three
hook types. Without it, `pre-commit install` writes only `.git/hooks/pre-commit` and the pre-push
(full-suite pytest) and commit-msg (cspell) gates are silently absent — the failure mode is a green
commit and a red CI. `git lfs install` also claims the `pre-push` slot, so re-run this after it;
pre-commit preserves the LFS hook as `pre-push.legacy` and chains to it. To verify,
`.git/hooks/pre-push` should name `--hook-type=pre-push`, not `git lfs pre-push`. On Windows, change
`pre-push.legacy`'s first line from `#!/bin/sh` to `#!/usr/bin/env sh`: pre-commit looks for an
absolute shebang as a Windows path, fails every push with "Executable `/bin/sh` not found", and
pushes nothing.

**Run benchmarks** (excluded from the default test run; `--quiet` for just the tables):
```bash
bash scripts/run_benchmark.sh
```

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

**Run all lint/static checks plus benchmarks (ruff check+format, ty, pyrefly, import-linter, relative imports, cspell, benchmark compare; add `--with-gui-test` to also run the GUI path tests headless, quietly):**
```bash
bash scripts/full-lint.sh
bash scripts/full-lint.sh --with-gui-test
```

**Check only uncommitted files (ruff/ty/cspell):**
```bash
bash scripts/git-ruff.sh
bash scripts/git-ty.sh
bash scripts/git-cspell.sh
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

- Unit tests are in `src/barks-reader/tests/unit/` and `src/barks-fantagraphics/tests/`.
  Benchmarks are in `src/barks-reader/tests/benchmarks/` and are excluded from the default `uv run pytest` run.
- Corpus consistency (every title's panel files, prebuilt comic, layout, panel-segments
  JSONs and wiki joins) is `scripts/validate-barks-reader-files.py`, run against the real
  data pack, nightly rather than in a gate; its tests are in `scripts/tests/`. The GUI tests
  assert one sample title each and leave the whole corpus to it.
- Use `pytest` fixtures and `patch.object(module, ClassName)` style mocking — **not** string-path patching like `patch("barks_reader.core.module.ClassName")`.
- GUI path tests are in `src/barks-reader/tests/gui/` (outside `testpaths`; run with
  `bash scripts/run_gui_tests.sh`, or `--headless` on Xvfb with no window or desktop
  session, which also runs four workers in parallel on displays :2 to :5, about three
  minutes for the suite). They boot the real app from a scratch profile and wait
  only on lines the app logs, so a screen's log markers are part of its contract: when a
  user-visible transition gets no log line, add one (with a `loguru_sink` unit test) rather
  than a sleep. The marker text is written once, in `barks_reader.core.log_markers`
  (`okf_reader.core.log_markers` for the wiki viewer): the app logs it with `.format`, a
  GUI test waits on it with `pattern()`. Plan and status: `docs/plans/gui-test-suite.md`.
  `--soak` runs the random walk instead (off by default); `--app PATH` runs the suite
  against a Nuitka build; `--prebuilt`, `--png-images` and `--ini` move a run to other
  settings; `--screen WxH` picks another nested screen size;
  `bash scripts/run_gui_matrix.sh` runs the suite once per settings variant (themes,
  double-page, virtual keyboard, ...; `--list`, `--only NAME`). A GUI test presses only the
  remote's six keys (Escape, Return, Up, Down, Left, Right): `scripts/check_gui_keys.py`
  (pre-commit, CI, full-lint) fails on any other, unless the call carries
  `# desktop key: <why>`.
  Every duration the app logs is held to a loose budget at teardown
  (`tests/gui/barks_gui/timings.py`): this machine's, once `--calibrate` has written
  `.benchmarks/gui-timings.json`, else the committed ones; skipped when the load exceeds
  what the cores and the run's workers account for; `BARKS_GUI_NO_BUDGETS=1` turns it off.
  A new timed line is a marker with an `{elapsed}` field, added to `TIMED` and `BUDGETS`
  there.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
