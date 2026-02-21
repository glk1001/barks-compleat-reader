# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Compleat Barks Disney Reader is a Kivy-based Python desktop application for browsing and reading the Fantagraphics Carl Barks comic library. It is packaged as a single-file executable via `pycrucible`.

## Commands

**Run the application:**
```bash
uv run python main.py
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
uv run pytest src/barks-reader/tests/benchmarks/
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

**Check only uncommitted files (ruff/ty):**
```bash
bash scripts/git-ruff.sh
bash scripts/git-ty.sh
```

**Build standalone executable:**
```bash
bash scripts/build.sh
```

## Architecture

### Source Packages

All code lives under `src/`, split into four packages managed as a **uv workspace**. Each has its own `pyproject.toml` and is installed as an editable package into the shared `.venv` — no `PYTHONPATH` configuration needed for development or tooling.

| Directory | Python Package | Role |
|---|---|---|
| `src/barks-reader/src` | `barks_reader` | Main application (core + UI) |
| `src/barks-fantagraphics/src` | `barks_fantagraphics` | Comics data model, database, titles, pages, panels |
| `src/barks-build-comic-images/src` | `barks_build_comic_images` | Image building utilities |
| `src/comic-utils/src` | `comic_utils` | Shared low-level utilities (image I/O, CV, timing, etc.) |

Entry point: `main.py` (root). Run `uv sync` after cloning to install all workspace packages. Note: `pycrucible.toml` still sets `PYTHONPATH` for the bundled standalone executable's runtime — that is intentional and cannot be removed. pycrucible uses a flat archive internally, so multiple `pyproject.toml` files collide on the same name and cannot be bundled. The workspace editable installs do not exist in the bundled executable context, so PYTHONPATH is the only way to locate packages within the extracted source tree.

### `barks_reader` Internal Layering

Enforced by `import-linter` (`.importlinter`):
- `barks_reader.core` — **must never import** from `barks_reader.ui` or `kivy`. Pure business logic.
- `barks_reader.ui` — Kivy widgets, screens, and app. May import from `core`.

Key `core` modules: `config_info`, `comic_book_loader`, `filtered_title_lists`, `image_file_getter`, `panel_image_loader`, `reader_settings`, `services`, `fantagraphics_volumes`.

Key `ui` modules: `barks_reader_app` (Kivy `App` subclass, orchestrates everything), `main_screen`, `tree_view_screen`, `comic_book_reader`, `bottom_title_view_screen`, `reader_screens` (screen manager), `view_state_manager`.

### Kivy Initialization Order (Critical)

`barks_reader.core.config_info` **must be imported before any Kivy imports** to redirect `KIVY_HOME` to the app's config directory. `main.py` enforces this at the top with a comment.

### Testing

- Unit tests are in `src/barks-reader/tests/unit/` and `src/barks-fantagraphics/tests/`. Benchmarks are in `src/barks-reader/tests/benchmarks/` and are excluded from the default `uv run pytest` run.
- Use `pytest` fixtures and `patch.object(module, ClassName)` style mocking — **not** string-path patching like `patch("barks_reader.core.module.ClassName")`.
- `testpaths = ["src/barks-reader/tests/unit", "src/barks-fantagraphics/tests"]` in `pyproject.toml`.

## Code Style

- Python 3.13+ syntax required.
- Type hints required on all function signatures; use `str | None` not `Optional[str]`.
- Public functions require Google-style docstrings.
- Formatter: `ruff` (line length 100, `ruff: noqa` rules in `.ruff.toml`).
- Type checker: `ty` (config in `ty.toml`).
- `experiments/` and `scraps/` directories are excluded from linting and type checking.
