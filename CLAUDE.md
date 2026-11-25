# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

You are the owner and long-term maintainer of this codebase, and its design is up to you.

The Compleat Barks Disney Reader is a Kivy-based Python desktop application for browsing and
reading the Fantagraphics Carl Barks comic library. It is packaged as a standalone executable
via Nuitka (`--mode=app`): a single-file onefile binary on Linux/Windows, a zipped `.app`
bundle on macOS.

## Commands

A clean machine's whole setup, in order (system packages, tools, sibling repos, hooks,
secrets, data, the one-off calibrations and the checks that say what is missing), is in
`docs/setup.md`; keep it current when a new tool or package becomes necessary. Every other
script (benchmarks, the overnight and GUI runners, the popup gallery, the GUI path tests, the
data-pack and docs-refs checks, the toolchain bump, the standalone build) is in
`docs/commands.md`.

**First-time setup (after cloning):**
```bash
uv run prek install
```
`default_install_hook_types` in `.pre-commit-config.yaml` makes that one command write all three
hook types. Without it, only `.git/hooks/pre-commit` is written and the pre-push (full-suite
pytest) and commit-msg (cspell) gates are silently absent — the failure mode is a green commit and
a red CI. To verify, `.git/hooks/pre-push` should name `--hook-type=pre-push`. A clone made
while the repo used git-lfs (before 2026-10-03), or whose hooks pre-commit installed (before
2026-09-29), has old hooks to retire: `docs/setup.md`, step 4.

Then generate the two gitignored modules every workspace boot imports:
```bash
bash scripts/generate-panel-module.sh   # comic_utils/get_panel_bytes.py; needs BARKS_ZIPS_KEY in .env.runtime
bash scripts/build.sh                   # barks_reader/_version.py (its first step writes it)
```
Without them the app dies on an import at boot (so every GUI test fails at its boot timeout;
`run_gui_tests.sh` checks for both first), and ty, pyrefly and full-lint refuse to run. Running
the app does not create either.

**Type-check (pyrefly):**
A second type checker gated alongside `ty`. Findings in `pyrefly-baseline.json` are
grandfathered, so only new ones fail; refresh it after an intended change (rationale: `pyrefly.toml`).
```bash
bash scripts/pyrefly.sh                    # or: uv run pyrefly check
bash scripts/pyrefly.sh --update-baseline  # refresh grandfathered findings
```

**Run every lint/static gate plus benchmarks** (a few checks only warn; `--with-gui-test` adds the GUI path tests, headless):
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

The standalone build needs no special workspace handling: Nuitka compiles `main.py` from the synced workspace `.venv`, with each app package and its data pulled in explicitly via the `--include-package`/`--include-package-data`/`--include-data-dir` flags in `scripts/build.sh` (a new package or data dir must be added there).

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

- Unit tests are in each package's `tests/` and in `scripts/tests/` (`testpaths` in
  `pyproject.toml`); the benchmarks in `src/barks-reader/tests/benchmarks/` are left out of the
  default run.
  CI's `diff-coverage` job holds the lines a push changes to 80% coverage (`diff-cover`) and
  each package to its own floor (`scripts/package_coverage.py`, a point below what it
  reached); `scripts/diff-cover.sh` runs both locally.
- Corpus consistency (every title's panel files, prebuilt comic, layout, panel-segments
  JSONs, wiki joins, splash tags, the search index and the Statistics charts' sidecar) is `scripts/validate-barks-reader-files.py`, run against the real
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

<!-- groma:start -->
## Groma

This project uses Groma. Before you scan, inspect, or curate architecture, or change files for a Backlog task, run `groma agent-instructions` and read the guide it names for that job. When it reports a first scan, ask the user whether they want you to curate the architecture. Do not edit Groma-owned architecture files directly.
<!-- groma:end -->

The map under `groma/` is the maintainer's own aid to understanding the code, written in
their words: Claude drafts a component's files and the questions its description should
answer, the maintainer writes the description, Claude checks it. The plan, the structure
and the stages are `docs/plans/architecture-map.md`. Do not write descriptions unasked.
