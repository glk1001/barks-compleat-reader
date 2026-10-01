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

**First-time setup (after cloning, and after any `git lfs install`):**
```bash
uv run prek install
```
The hooks run on [prek](https://github.com/j178/prek), as in the two sibling repos; it comes from
the `dev` dependency group (`uv sync`) and reads `.pre-commit-config.yaml`. The cspell hooks also
need [bun](https://bun.sh) on the PATH (on Windows, `winget install Oven-sh.Bun`, whose package
lacks `bunx`: beside `bun.exe`, add a `bunx.cmd` holding `@"%~dp0bun.exe" x %*`. A `bunx.exe`
link did not do under pre-commit, which ran it as `bunx.EXE` while bun matches its own name
case-sensitively).
`default_install_hook_types` in `.pre-commit-config.yaml` makes that one command write all three
hook types. Without it, only `.git/hooks/pre-commit` is written and the pre-push (full-suite
pytest) and commit-msg (cspell) gates are silently absent — the failure mode is a green commit and
a red CI. `git lfs install` also claims the `pre-push` slot, so re-run this after it; prek
preserves the LFS hook as `pre-push.legacy` and chains to it. To verify, `.git/hooks/pre-push`
should name `--hook-type=pre-push`, not `git lfs pre-push`. On Windows, change
`pre-push.legacy`'s first line from `#!/bin/sh` to `#!/usr/bin/env sh`: pre-commit looked for an
absolute shebang as a Windows path, failed every push with "Executable `/bin/sh` not found", and
pushed nothing. (Both Windows notes were found under pre-commit. Under prek, on the Windows
laptop on 2026-10-01, every commit hook ran, the cspell one through `bunx.cmd`, so the
`bunx` note holds; the commit-message check calls `bun x` and needs no `bunx`. The
`pre-push.legacy` shebang is not yet re-checked under prek: that laptop's file already had
the fix, and its pushes skipped the hook.)

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

**Run the whole repo overnight** (the data-pack validators, full-lint, the suite with coverage,
in random order and against upgraded dependencies, the sibling repos' tests, a Nuitka build and
its smoke test, every GUI stage below against that build, GUI timing drift, a weekday slice of
mutation testing; `--list`, `--only`, `--skip`, `--app PATH`; results in
`build/overnight/<stamp>/summary.txt`, where a warn-only stage shows WARNED):
```bash
bash scripts/run_overnight.sh
```
To run it on another machine, `bash scripts/copy-to-overnight-host.sh [--dry-run] HOST`
sets that one up over ssh (repos, `.env.runtime`'s `BARKS_` lines, about 36 GB of data;
not the build tree, so it runs with `--skip build-check`), and
`bash scripts/check-overnight-host.sh` there says what is still missing.
On Windows, `uv run python scripts/run_overnight_windows.py` (same options and summary)
runs what only a Windows machine can: the suite with the data pack, the GUI suite on the
workspace app and on CI's build of this commit, a soak, `validate`, and the coverage of
what only Windows runs; nightly through `scripts/windows/register-overnight-task.ps1`;
`uv run python scripts/check_windows_overnight_host.py` says what a machine still lacks for it
(setup: `docs/setup.md`, Windows). Plan: `docs/plans/windows-overnight.md`.
Pull before starting it (`git pull --ff-only; uv run python scripts/run_overnight_windows.py`):
its `update` stage pulls too, but the runner is loaded by then, so a pull that changes the
runner itself takes effect only on the next run (on 2026-10-01 a run started that way lacked
the new coverage stage). The nightly task `register-overnight-task.ps1` registers does
not pull first.
`uv run python scripts/coverage_all_platforms.py LINUX_HOST WINDOWS_HOST` combines the two
machines' coverage of the newest commit both ran overnight (`--commit`), reported against
that commit's source: Linux, Windows, both, and what only Windows ran (report only).

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
  minutes for the suite; on Windows and macOS, `uv run python scripts/run_gui_tests.py`,
  one worker on the real desktop, through `scripts/gui_probe.py`'s backend for each,
  `gui_probe_win32.py` and `gui_probe_darwin.py`; macOS plan:
  `docs/plans/macos-gui-tests.md`). They boot the real app from a scratch profile and wait
  only on lines the app logs, so a screen's log markers are part of its contract: when a
  user-visible transition gets no log line, add one (with a `loguru_sink` unit test) rather
  than a sleep. The marker text is written once, in `barks_reader.core.log_markers`
  (`okf_reader.core.log_markers` for the wiki viewer): the app logs it with `.format`, a
  GUI test waits on it with `pattern()`. Plan and status: `docs/plans/gui-test-suite.md`.
  `--soak` runs the random walk instead (off by default); `--app PATH` runs the suite
  against a Nuitka build; `--prebuilt`, `--png-images` and `--ini` move a run to other
  settings; `--screen WxH` picks another nested screen size; `--keep-logs` saves every
  passing test's artifacts too (logs, profile, final frame), as a failure's;
  `bash scripts/run_gui_matrix.sh` runs the suite once per settings variant (themes,
  double-page, virtual keyboard, ...; `--list`, `--only NAME`). A GUI test presses only the
  remote's six keys (Escape, Return, Up, Down, Left, Right): `scripts/check_gui_keys.py`
  (pre-commit, CI, full-lint) fails on any other, unless the call carries
  `# desktop key: <why>`.
  `test_taps.py` taps instead, by what a widget shows, never by pixel: the app lists
  its tappable widgets on request (`barks_gui.taps`, `barks_reader.core.tap_targets`).
  A tap is a click; `--touch` makes it a real touch too, on a virtual touchscreen, and
  needs the udev rule in `scripts/udev/` once (select with `-k test_taps`: one worker).
  The leak tests (`-k leave_no`) ask the app the same way what it holds after a full
  garbage collection (`barks_gui.memory`, `barks_reader.core.memory_census`): widgets and
  textures may not climb over repeated round trips. The app's resident size is no leak
  signal here: garbage waits long for a full collection, and glibc keeps freed memory.
  Plan: `docs/plans/touch-gui-tests.md`.
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
