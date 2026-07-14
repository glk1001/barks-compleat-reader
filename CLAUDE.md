# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Compleat Barks Disney Reader is a Kivy-based Python desktop application for browsing and
reading the Fantagraphics Carl Barks comic library. It is packaged as a standalone executable
via Nuitka (`--mode=app`): a single-file onefile binary on Linux/Windows, a zipped `.app`
bundle on macOS.

## Commands

**Run the application:**
```bash
uv run main.py
```

**Run all tests:**
```bash
uv run pytest
```

**Run a single test file:**
```bash
uv run pytest src/barks-reader/tests/unit/test_reader_utils.py
```

**Run tests with coverage:**
```bash
uv run pytest --cov
```

**Run benchmarks** (excluded from the default test run):
```bash
bash scripts/run_benchmark.sh
```

**Lint (ruff):**
```bash
uv run ruff check .
uv run ruff format .
```

**Type-check (ty):**
```bash
uv run ty check
```

**Check import layering:**
```bash
uv run lint-imports
```

**Spell-check (cspell):**
```bash
bunx cspell
```

**Run all lint/static checks plus benchmarks (ruff check+format, ty, import-linter, relative imports, cspell, benchmark compare):**
```bash
bash scripts/full-lint.sh
```

**Check only uncommitted files (ruff/ty/cspell):**
```bash
bash scripts/git-ruff.sh
bash scripts/git-ty.sh
bash scripts/git-cspell.sh
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

#### Wiki title convention — how to join and display

The barks-wiki bundle and this app share one rule: **identity is the plain canonical title;
parentheses are presentation**, applied at render time from `is_barks_title`. Concretely:

1. **Joining to wiki pages:** map a story via `cbi.get_title_str()` → the wiki story page's
   frontmatter `title` (exact match), or its filename slug at
   `okf/concept/stories/<series>/<slug>.md`. The slug convention: lowercase, apostrophes
   dropped (not hyphenated), every other run of non-alphanumerics becomes a single hyphen,
   leading/trailing hyphens stripped — e.g. You Can't Guess! → `you-cant-guess`,
   Ten-Dollar Dither → `ten-dollar-dither`. Frontmatter titles, slugs, and H1s are always
   plain — never parenthesised.
2. **Displaying titles:** when the Barks Reader UI shows a story title, apply the parentheses
   convention from our own data: `f"({title})" if not cbi.is_barks_title else title`. Never
   scrape parentheses (or their absence) out of wiki markdown — the wiki's `chronology.md`
   shows parenthesised assigned titles, but that is the same rule applied by its generator at
   generation time, not data to parse back.
3. **Keep okf-reader generic:** it must not grow a `barks_fantagraphics` dependency or any
   parens logic. If the viewer needs to show a decorated title, the app's integration layer
   computes the display string (per #2) and passes it in; okf-reader keeps joining on
   frontmatter `title` as-is (e.g. its backgrounds matching).
4. **Never parse wiki data tables for facts we own.** `okf/reference/data/*.md` (chronology,
   payments, tags…) are generated from this repo's `barks_fantagraphics` — for
   `is_barks_title`, issue, dates, etc., import `BARKS_TITLE_INFO` directly; the wiki tables
   are downstream of us and their display format can change.

### Source Packages

All code lives under `src/`, split into four packages managed as a **uv workspace**. Each has its own `pyproject.toml` and is installed as an editable package into the shared `.venv` — no `PYTHONPATH` configuration needed for development or tooling.

| Directory | Python Package | Role |
|---|---|---|
| `src/barks-reader/src` | `barks_reader` | Main application (core + UI) |
| `src/barks-fantagraphics/src` | `barks_fantagraphics` | Comics data model, database, titles, pages, panels |
| `src/barks-build-comic-images/src` | `barks_build_comic_images` | Image building utilities |
| `src/comic-utils/src` | `comic_utils` | Shared low-level utilities (image I/O, CV, timing, etc.) |

Entry point: `main.py` (root). Run `uv sync` after cloning to install all workspace packages. The standalone build needs no special workspace handling: Nuitka compiles `main.py` from the synced workspace `.venv`, with each app package and its data pulled in explicitly via the `--include-package`/`--include-package-data`/`--include-data-dir` flags in `scripts/build.sh` (a new package or data dir must be added there).

### Import Layering

Enforced by `import-linter` (`.importlinter`), three contracts:
- `barks_reader.core` — **must never import** from `barks_reader.ui` or `kivy`. Pure business logic.
- `barks_reader.ui` — Kivy widgets, screens, and app. May import from `core`.
- `barks_fantagraphics` — **must not import** from `barks_reader`.
- `comic_utils` — **must not import** from `barks_reader` or `barks_fantagraphics`.

Always run `uv run lint-imports` after any code changes — not just when imports change.

### Navigation model

`barks_reader.core.navigation` owns tree-view navigation policy independent of Kivy:
- `Destination` — frozen-dataclass hierarchy describing every navigable target (intro, stories, year ranges, series, categories, tag groups, tags, titles, articles, search, index, appendix). One subclass per navigable kind; payloads (e.g. `TagDestination.tag`, `TitleDestination.fanta_info`) live on destinations, not on widget subclasses.
- `NavigationModel.view_state_for(dest)` — resolves `(ViewStates, params)` for a destination.
- `NavigationModel.auto_select_target(parent, children)` — single-title-child auto-select rule.
- `NavigationModel.tag_context(dest)` — tag/tag-group carried by a parent destination.
- `ViewStates` — enum of all navigable states, re-exported from `ui.view_states` for back-compat.

Tree-view widgets (`ui/tree_view_nodes.py`) carry a `destination: Destination | None` slot. `ui/tree_view_manager.py` and `ui/navigation_coordinator.py` route through `NavigationModel` rather than switching on widget subclass. Adding a new navigable target = add a `Destination` subclass + register it in the model.

### Kivy Initialization Order (Critical)

`barks_reader.core.config_info` **must be imported before any Kivy imports** to redirect `KIVY_HOME` to the app's config directory. `main.py` enforces this at the top with a comment.

### Testing

- Unit tests are in `src/barks-reader/tests/unit/` and `src/barks-fantagraphics/tests/`.
  Benchmarks are in `src/barks-reader/tests/benchmarks/` and are excluded from the default `uv run pytest` run.
- Use `pytest` fixtures and `patch.object(module, ClassName)` style mocking — **not** string-path patching like `patch("barks_reader.core.module.ClassName")`.
- `testpaths` in `pyproject.toml` covers `src/barks-reader/tests/unit`, `src/barks-fantagraphics/tests`, and `src/barks-build-comic-images/tests`.

## Code Style

- `experiments/` and `scraps/` directories are excluded from linting and type checking.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
