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
`default_install_hook_types` in `.pre-commit-config.yaml` makes that one command write all three
hook types. Without it, `pre-commit install` writes only `.git/hooks/pre-commit` and the pre-push
(full-suite pytest) and commit-msg (cspell) gates are silently absent — the failure mode is a green
commit and a red CI. `git lfs install` also claims the `pre-push` slot, so re-run this after it;
pre-commit preserves the LFS hook as `pre-push.legacy` and chains to it. To verify,
`.git/hooks/pre-push` should name `--hook-type=pre-push`, not `git lfs pre-push`.

**Run benchmarks** (excluded from the default test run):
```bash
bash scripts/run_benchmark.sh
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

**Run all lint/static checks plus benchmarks (ruff check+format, ty, pyrefly, import-linter, relative imports, cspell, benchmark compare):**
```bash
bash scripts/full-lint.sh
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

All code lives under `src/`, split into four packages managed as a **uv workspace**. Each has its own `pyproject.toml` and is installed as an editable package into the shared `.venv` — no `PYTHONPATH` configuration needed for development or tooling.

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
- Use `pytest` fixtures and `patch.object(module, ClassName)` style mocking — **not** string-path patching like `patch("barks_reader.core.module.ClassName")`.

## Code Style

- `experiments/` and `scraps/` directories are excluded from linting and type checking.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
