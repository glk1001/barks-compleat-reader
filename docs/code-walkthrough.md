# The Compleat Barks Reader — A Linear Code Walkthrough

A guided tour of how the app works, following the runtime flow from the moment
you type `python main.py` to the moment a comic page paints on screen. Read it
top to bottom: each section builds on the last.

All `file:line` references are clickable in most editors. Paths are given
relative to the app package `src/barks-reader/src/barks_reader/` unless they
carry a package prefix (`barks_fantagraphics/…`, `comic_utils/…`) or start at
the repo root (`main.py`, `.importlinter`).

**How to use this doc:** if you just want the mental model, read sections 1–3
and the diagrams. If you're about to change something, read the section that
owns that subsystem — each one ends with the extension point and the gotchas
you need to know.

---

## Table of contents

1. [Orientation — the shape of the codebase](#1-orientation)
2. [Boot — from `main.py` to the first frame](#2-boot)
3. [The data layer — `barks_fantagraphics`](#3-the-data-layer)
4. [Navigation — turning a click into an intent](#4-navigation)
5. [The view pipeline — computing what to show](#5-the-view-pipeline)
6. [Opening a comic — loading and reading pages](#6-opening-a-comic)
7. [The UI shell — screens, action bar, indexes, search, wiki](#7-the-ui-shell)
8. [Ports, adapters, and cross-cutting concerns](#8-ports-adapters-and-cross-cutting)
9. [Putting it together — three end-to-end traces](#9-end-to-end-traces)

---

## 1. Orientation

The Compleat Barks Reader is a **Kivy desktop app** for browsing and reading the
Fantagraphics *Carl Barks Library* of Disney comics. It ships as a standalone
executable built by Nuitka (`--mode=app` in `scripts/build.sh`: a single-file
onefile binary on Linux/Windows, a zipped `.app` bundle on macOS), but for
development it's a `uv` workspace of four Python packages (`src/…`):

| Package | Role |
|---|---|
| `barks_reader` | The app itself — split into `core` (logic) and `ui` (Kivy). |
| `barks_fantagraphics` | The domain/data layer: titles, stories, tags, volumes. |
| `barks_build_comic_images` | Image-building utilities (panel assembly). |
| `comic_utils` | Low-level shared utilities (image I/O, timing, decryption). |

### The one architectural idea that explains everything

The whole app is organized around a single rule: **`barks_reader.core` never
imports Kivy.** Business logic — navigation policy, the view pipeline, comic
loading, settings — lives in `core` as plain Python. Everything Kivy-specific
lives in `barks_reader.ui`. The two layers meet through **Protocol "ports"**
(defined in `core/ports/`) that `ui` satisfies with **"adapters"**.

Why bother? Two payoffs: `core` is unit-testable without spinning up a window
(the fakes in `core/testing/fakes.py` stand in for Kivy), and the Kivy surface
is small and quarantined. The rule is not a convention — it's mechanically
enforced by `import-linter`. From `.importlinter` (repo root), the six
contracts, in plain terms:

1. `barks_reader.core` must not import `barks_reader.ui`, `okf_reader.ui`, or `kivy`.
2. `barks_fantagraphics` must not import `barks_reader`.
3. `comic_utils` must not import `barks_reader` or `barks_fantagraphics`.
4. `barks_fantagraphics` and `comic_utils` must not import `kivy`.
5. `okf_reader.core` must not import `okf_reader.ui` or `kivy`.
6. `okf_reader` must stay independent of the Barks packages.

The allowed dependency direction is therefore `ui → core → (barks_fantagraphics,
comic_utils)`. Keep this picture in your head; every subsystem below is a
concrete instance of it. Run `uv run lint-imports` after any change — the CLAUDE.md
insists on it because `.kv` files and lazy imports can smuggle a violation past
ruff and ty.

### The three "spines" of the app

Almost everything routes through one of three flows, and the rest of this doc is
organized around them:

- **The view pipeline** (section 5): navigate the tree → compute an immutable
  `ViewSnapshot` in `core` → apply it to widgets in `ui`. This drives the *main
  screen* — backgrounds, the title view, the fun-image view, index/search
  visibility.
- **The comic reader** (section 6): open a title → load its pages off-thread →
  paint textures. This is a separate top-level screen pushed over the main one.
- **The screen manager** (section 7): a fixed registry of four top-level screens
  (main, comic reader, document reader, wiki) with named switch/close callbacks.

---

## 2. Boot

Entry point: `main.py` (repo root). The single most important thing about
startup is an **import-ordering constraint**, so we start there.

### 2.1 The `KIVY_HOME` constraint (read this first)

Kivy reads several environment variables exactly once, on its first import:
`KIVY_NO_ARGS`, `KIVY_NO_CONSOLELOG`, some SDL window-class hints, and — most
importantly — **`KIVY_HOME`**, which decides where Kivy stores its config and
logs. The app wants those under its own settings directory, not `~/.kivy`. So it
must set those env vars **before any `kivy` module loads**.

`core/config_info.py` does this at module scope and per-`ConfigInfo`-instance,
and it guards the invariant three ways:

1. **Static guard** — `_assert_kivy_not_yet_imported()` (`core/config_info.py:35`)
   scans `sys.modules` for anything `kivy*` and raises `ImportError` if found.
   It runs at import (`:59`) and again right before setting `KIVY_HOME` (`:119`).
2. **Ordering discipline** — `main.py` imports `config_info` (line 22) *before*
   any Kivy import; the first real Kivy import is deferred inside
   `start_logging` (`main.py:92`). A header comment at `main.py:1–6` documents
   the rule.
3. **Runtime assertion** — `start_logging` verifies that Kivy's resolved
   `kivy_home_dir` actually equals the app's config dir, raising `RuntimeError`
   otherwise (`main.py:118–123`).

This is why `main.py` is written the way it is, with almost every Kivy touch
tucked inside a function rather than at module top. (The same rule is captured
in project memory as "Kivy import order.")

### 2.2 The boot sequence

Numbered, in the order it actually happens:

1. **`main.py` imports.** A module-level `_timing = Timing()` (`main.py:16–18`)
   starts the boot stopwatch.
2. **The import-order guard fires** as `config_info` imports (`main.py:22`),
   setting the pre-Kivy env vars (`core/config_info.py:59–71`).
3. **Sibling core modules import** (`main.py:32–36`). Two module-level singletons
   are built right here, before Kivy: `PLATFORM` (`core/platform_info.py:46`)
   and `SCREEN_METRICS` (`core/screen_metrics.py:161`), the latter querying your
   monitors via `screeninfo.get_monitors()`.
4. **Exception hooks installed.** `sys.excepthook = handle_uncaught_exception`
   (`main.py:58–73`) and `threading.excepthook = handle_thread_exception`
   (`main.py:76–86`) route any crash — main thread or background thread — to a
   full-screen error renderer.
5. **`__main__` runs** (`main.py:348`). In a compiled (Nuitka) build it first
   handles the `--run-first-run-installer` re-exec sentinel (`main.py:281`) and,
   on a first run, blocks in `maybe_run_first_run_installer()` (`main.py:284`)
   while an isolated subprocess unpacks the data zips — a failed install aborts
   the launch. Then `ok_to_run()` checks the installer-failed flag file;
   `reset_python_gc()` raises the GC thresholds (a real startup speedup); and
   Typer dispatches to `main()`.
6. **`main()` executes** (`main.py:290`). It builds `ConfigInfo()` (which sets
   `KIVY_HOME`, `core/config_info.py:118–120`), reads a lightweight
   `MinimalConfigOptions` from the ini *before* Kivy is up
   (`core/minimal_config_info.py:21`), calls `start_logging` (first Kivy import,
   `main.py:92`), computes and applies the window geometry via
   `update_window_size` → `set_window_size` (`main.py:166`, `:225`), and finally
   `call_reader_main` (`main.py:259`).
7. **`reader_main(config_info)`** (`ui/barks_reader_app.py:539`) constructs the
   **data layer** — `ComicsDatabase(for_building_comics=False)` (`:544`) — then
   the Kivy app `BarksReaderApp(config_info, comics_database)` (`:553`) and calls
   `kivy_app.run()` (`:555`). The whole thing is wrapped in a try/except that
   renders a crash screen (`:556–558`).
8. **`BarksReaderApp.build()`** (`ui/barks_reader_app.py:226`) is Kivy's build
   hook. In order: apply two Kivy 2.3.1 monkeypatches (`:235–257`);
   `_initialize_settings_and_db()` (`:259`); load every `.kv` file via `Builder`
   (`:263–280`); `_build_screens()` (`:282`); build the tree view (`:290`);
   `_finalize_window_setup()` (`:292`); return the root `ScreenManager`.
9. **`_build_screens()`** (`ui/barks_reader_app.py:327`) instantiates the
   `MainScreen` and all its sub-screens plus the comic/document/wiki reader
   screens, and registers the four top-level screens with the
   `ReaderScreenManager`.
10. **`build_tree_view()`** (`ui/main_screen.py:300`) builds a `ReaderTreeBuilder`
    and hands off to `AppInitializer.start` (`ui/app_initializer.py:99`), which
    **defers** the actual tree construction to the next frame with
    `Clock.schedule_once(...)` — so `build()` can return fast.
11. **`_finalize_window_setup()`** (`ui/barks_reader_app.py:437`) sets the icon,
    binds window move/resize to the geometry helper, performs a "wiggle" resize
    trick to force widgets to size themselves (`:462–467`), and **schedules the
    window to actually become visible ~2 seconds later** via `Window.show()`
    (`:477–482`).
12. **Kivy's event loop starts.** The deferred callbacks fire: the tree finishes
    building → `AppInitializer.on_tree_build_finished` (`ui/app_initializer.py:106`)
    dismisses the loading popup, renders the initial view
    (`render_state(ViewStates.INITIAL)`, `:121`), initializes comic data, and
    restores the last-selected node. ~2s in, `show_the_window` fires and you see
    the first frame.

### 2.3 Boot gotchas worth knowing

- **The window is deliberately hidden, then shown ~2s later.** `set_window_size`
  sets `window_state=hidden` on non-Windows (`main.py:240`), so all the sizing
  and moving happens invisibly. **Windows is exempted** — hiding there trashes
  fonts and triggers a `ZeroDivisionError` deep in Kivy's mouse code (documented
  inline at `main.py:228–240`).
- **There is no `on_start` override.** Despite Kivy convention, the "after build"
  work is driven entirely by `Clock.schedule_once` deferrals. Only `on_stop` is
  overridden (`ui/barks_reader_app.py:144`), to save the wiki resume point on
  quit.
- **Compiled-vs-dev affects path resolution.** `IS_COMPILED`
  (`core/config_info.py:17` — Nuitka defines `__compiled__` in every module it
  compiles) selects the strategy: a compiled build anchors config/data/installer
  zips on the executable's directory via `get_app_exe_dir()`
  (`core/config_info.py:78`; on macOS that's the directory *beside* the `.app`
  bundle). A plain dev run instead requires `BARKS_READER_CONFIG_DIR` /
  `BARKS_READER_DATA_DIR` env vars, loaded from `.env.runtime` (`main.py:52`).
- **Fonts are bimodal.** `FontManager.update_font_sizes` switches between a
  low-res and hi-res font theme at a window-height cutoff of 1090px
  (`ui/font_manager.py:188`), and no-ops otherwise — so resize-driven font
  changes only fire when you cross that threshold.

---

## 3. The data layer

Package: `barks_fantagraphics`. This is a **pure, Kivy-free domain library** the
reader depends on one-directionally (contract #2). One surprising fact up front:
despite the name `ComicsDatabase`, **there is no SQL database and no runtime
JSON.** Almost all metadata is *generated Python literals compiled into the
package*, plus per-story `.ini` files on disk for page layout. "Queries" are
dict/list lookups and `configparser` reads.

### 3.1 The domain model

Everything keys off one canonical enum, `Titles` (`barks_titles.py:13`) — an
`IntEnum` with one member per story (`NUM_TITLES = 689`: 684 stories + 4 articles
+ 1 synthetic "All One-Pagers" collection). The rest of the model hangs off it:

| Concept | Owned by | Location |
|---|---|---|
| Canonical title identity | `Titles` enum | `barks_titles.py:13` |
| Title display string | `ENUM_TO_STR_TITLE` / `STR_TITLE_TO_ENUM` | `barks_titles.py:888`, `:893` |
| Per-story metadata | `ComicBookInfo` + master table `BARKS_TITLE_INFO` | `comic_book_info.py:31`, `:79` |
| Story + series join | `FantaComicBookInfo` | `fanta_comics_info.py:76` |
| Physical Fanta volume | `FantaBook` + registry `FANTA_SOURCE_COMICS` (29 vols) | `fanta_comics_info.py:139`, `:199` |
| Tags / tag groups / categories | `Tags`, `TagGroups`, `TagCategories` (~200 tags, 18 groups) | `barks_tags_enums.py:11`, `:206`, `:198` |
| Page classification | `PageType` enum + frozensets | `comics_consts.py:64` |
| Entity types (search) | `EntityType` (PERSON/LOCATION/…) | `entity_types.py:4` |

At import time, `_get_all_fanta_comic_book_info()` (`fanta_comics_info.py:91`)
joins the title table and the series table into a module-global
`ALL_FANTA_COMIC_BOOK_INFO` ordered dict — the in-memory "database".

### 3.2 Where the comic files actually live

Two distinct on-disk stories, and it's easy to conflate them:

- **Per-story layout** comes from `.ini` files under a `story-titles/` data dir
  (`comics_consts.py:29`). `ComicsDatabase.__init__` (`comics_database.py:73`)
  globs them; each has an `[info]` section (title, `source_comic=FANTA_nn`, font
  sizes) and a `[pages]` section (page-key → `PageType`), parsed in
  `_build_comic_book` (`comics_database.py:491`).
- **Page images** come from **ZIP archives** at runtime. The `.ini`'s
  `source_comic` selects a `FantaBook`; the reader reads `.cbz`/`.zip` volume
  archives through `FantagraphicsVolumeArchives` (`core/fantagraphics_volumes.py:120`),
  with an optional **overrides** archive layered on top. (The full resolution
  logic is section 6.)

### 3.3 The public API the reader calls

`ComicsDatabase` (`comics_database.py:72`) is the façade, constructed once and
injected everywhere. Key methods:

- `get_comic_book(title)` → `ComicBook` — the main story loader (`:409`).
- `get_fanta_comic_book_info(title)` → `FantaComicBookInfo` (`:395`).
- `is_story_title`, `get_story_title_from_issue`, `get_all_story_titles`,
  volume getters (`:132`, `:140`, `:149`, `:255`+).

Module-level helpers used pervasively: `ENUM_TO_STR_TITLE` /
`STR_TITLE_TO_ENUM`, `get_fanta_info`, the tag API in `barks_tags.py`
(`get_sorted_tagged_titles` `:300`, `get_tag_group_titles` `:317`, etc.).

### 3.4 The parenthesized-title convention

A recurring rule you'll see referenced across the codebase and CLAUDE.md, and it
lives in exactly one place in code (`comic_book_info.py:70`):

```python
def get_display_title(self) -> str:
    return self.get_title_str() if self.is_barks_title else f"({self.get_title_str()})"
```

Identity is the plain canonical title; **parentheses are presentation**, applied
only when Barks drew a story but did not himself title it (`is_barks_title` is
False). Never scrape parens from wiki data — compute them here.

---

## 4. Navigation

The left sidebar tree (year ranges, series, categories, tags, titles, search,
index, appendix) is where the user drives the app. Its **policy is Kivy-free**
(`core/navigation/`) and its **widgets are Kivy** (`ui/`). This section traces a
click from widget to rendered view.

### 4.1 The Kivy-free model (`core/navigation/`)

Three types carry the whole model:

- **`Destination`** (`destinations.py:32`) — a frozen dataclass base with one
  subclass per navigable kind. Two flavors: no-payload singletons
  (`StoriesDestination`, `SearchDestination`, `IndexDestination`, …) and
  payload-bearing ones that carry the domain data needed to reconstruct the
  decision: `YearRangeDestination` (start/end/kind), `SeriesDestination`,
  `CategoryDestination`, `TagGroupDestination`, `TagDestination`,
  `TitleDestination(fanta_info=…)` (the leaf), `ArticleDestination`. Payloads
  live on destinations, *not* on widget subclasses — that's the key design move.
- **`ViewStates`** (`view_states.py:13`) — a plain `IntEnum` naming every
  top-level view (`INITIAL`, `ON_TITLE_NODE`, `ON_SERIES_*`, `ON_TAG_NODE`,
  the search/index/appendix states, …). It's the single vocabulary the whole
  render path speaks, re-exported from `ui.view_states` for back-compat.
- **`tree_spec.py`** — a *declarative* description of the tree, no Kivy. A
  `NodeSpec` (`:159`) says what one node is: its `NodeKind` (which widget class),
  its text, its `Destination`, its `PressAction` (toggle-only vs. open-a-view vs.
  a special handler), and its children. **Title rows are always lazy** — deferred
  via `lazy_children=partial(_title_rows, …)` so startup stays fast.
  `build_reader_tree_spec(...)` (`:180`) returns the five top-level specs:
  Intro, The Stories, Search, Appendix, Index.

**`NavigationModel`** (`navigation_model.py:117`) is the stateless policy engine.
Its central method, `view_state_for(dest)` (`:127`), resolves a `Destination`
into a `ViewRequest` using a dispatch table for the singletons
(`_SIMPLE_DESTINATION_TO_VIEW_STATE`, `:81`) and `isinstance` branches for the
payload-bearing kinds (e.g. a `YearRangeDestination` splits on its kind into the
CHRONO/CS/US view states and formats the range string). Two more methods encode
subtle UX rules: `auto_select_target` (`:171`, the "if a node has exactly one
title child, jump straight to it" rule) and `tag_context` (`:185`, "which tag/
tag-group does this parent carry", used to pick the right page to jump to).

### 4.2 From spec to widgets

`ReaderTreeBuilder` (`ui/reader_tree_builder.py`) walks the spec and instantiates
Kivy widgets — it holds no tree structure itself. `build_main_screen_tree`
(`:104`) calls `build_reader_tree_spec(...)` then `_add_node` for each top-level
spec. `_add_node` (`:124`) maps `NodeKind` → widget class, binds the right press
handler, and **defers lazy children** via `_defer_node_population` (`:178`),
which sets a `populate_callback` that runs on first expand. The widget classes
live in `ui/tree_view_nodes.py`: `ButtonTreeViewNode` (`:99`, container nodes,
whose `on_press` toggles expand/collapse) and `TitleTreeViewNode` (`:150`, the
leaf row that auto-builds a `TitleDestination`). Every `BaseTreeViewNode` carries
a `destination: Destination | None` slot (`:93`) — that's the bridge back to the
Kivy-free model.

### 4.3 The click-to-view flow

There are two entry paths, both ending at `ViewRenderer` → `NavigationModel` →
the view pipeline:

**A container node (year range, series, tag, …):**
1. Kivy fires the node's `on_press`; for toggle-only nodes this just expands/
   collapses. The *view change* is driven by the expand event, not the press.
2. `ReaderTreeView` emits `on_node_expand`, bound to
   `TreeViewManager.on_node_expanded` (`ui/tree_view_manager.py:218`).
3. That handler closes siblings, lazily populates the node once, checks the
   single-title-child auto-select rule (`:250`), and otherwise calls
   `set_view_state_for_node(node)` (`:203`) → `self._renderer.render(node.destination)`.
4. `ViewRenderer.render(destination)` (`ui/view_renderer.py:126`) resolves the
   destination via `NavigationModel.view_state_for` and dispatches into the
   pipeline.

**A title row (leaf → title view):**
1. The row press lands in `TreeViewManager.on_title_row_button_pressed` (`:295`).
   It reads the row's `TitleDestination.fanta_info`, computes the tag from the
   *parent* node via `nav_model.tag_context`, and calls
   `nav.select_title(TitleTarget(fanta_info, tag))`.
2. `NavigationCoordinator.select_title` (`ui/navigation_coordinator.py:135`) calls
   `renderer.render_title(...)`, which builds a `ViewRequest(view_state=ON_TITLE_NODE, …)`
   and (if a tag is present) sets the tag-specific goto page from
   `BARKS_TAGGED_PAGES`.

Programmatic navigation (Back history, "goto title" from a background image, a
search or index result) goes through `TreeViewManager.setup_and_select_node`,
which uses the `chrono_year_range_nodes` / `series_nodes` lookups the builder
collected (`reader_tree_builder.py:167`) to open the tree to the right node.

### 4.4 Extending it

Adding a navigable target is a three-step recipe (from the module docstrings and
CLAUDE.md): add a `Destination` subclass, register it in `NavigationModel` (a
dispatch-table entry or an `isinstance` branch), and add a `NodeSpec` in the
`_SpecBuilder`. Exhaustiveness is asserted at wiring time — every `PressAction`
must have a handler (`reader_tree_builder.py:91`).

---

## 5. The view pipeline

This is the heart of the *main screen*. It's the cleanest expression of the
compute/apply split: `core` computes an immutable `ViewSnapshot` describing what
the screen should show; `ui` applies it to widgets. Nothing in the compute half
touches Kivy.

### 5.1 The shape

```
Destination ──► NavigationModel.view_state_for() ──► ViewRequest        (core, immutable input)
                                                         │
ViewRenderer._dispatch()  ──stamps theme policy──►  ViewPipeline.render()  (core engine)
   (ui facade)                                            │
                                          _compute_snapshot() ──► ViewSnapshot  (core, immutable)
                                                         │
SnapshotApplicator.apply(snapshot)  ◄── SnapshotSink port ◄───┘
   (ui — the ONLY class that touches these widgets)
                                                         │
   PanelTextureLoader → PanelImageLoader (bg thread) → Scheduler.schedule_once → Kivy widgets
```

### 5.2 The two immutable messages

**`ViewRequest`** (`core/view_request.py:45`) is the navigation intent: a frozen
dataclass whose only required field is `view_state`, plus nav-context selectors
(`category`, `year_range`, `tag`, `tag_group`, `title_str`), a one-shot
`title_image_file`, a `preserve_top_view` flag (keep the current background
instead of re-picking), and `fun_image_themes` (stamped by the renderer, not by
call sites).

**`ViewSnapshot`** (`core/view_snapshot.py:64`) is the complete description of one
screen state, composed of five sub-snapshots:

- `top_view` — the tree background image (info, opacity, color).
- `fun_view` — the decorative bottom image (visible?, info, color).
- `title_view` — the selected title's image (visible?, info, color).
- `screen_visibility` — booleans for the index/statistics/history sub-screens.
- `search_view` — search visibility + mode (Title/Tag/Word).

Note the boundary discipline: `ViewSnapshot.view_state` is stored as a **raw
`int`**, deliberately, "to avoid a ui import" (`core/view_snapshot.py:72`).

### 5.3 How the pipeline decides

`ViewPipeline.render()` (`core/view_pipeline.py:252`) writes the request's context
onto ~12 mutable internal fields, calls `_update_views()` to re-pick images and
opacities, then `_compute_snapshot()` to freeze the result. Two mechanisms do the
deciding:

- **Opacity/visibility** is driven by *set membership*. Module-level constants
  like `_BOTTOM_VIEW_FUN_IMAGE_OPACITY_1_STATES` (`:96–133`) list which view
  states show which panel; `_update_views` (`:369`) checks membership, and
  `_compute_snapshot` (`:328`) reads it back into the snapshot.
- **Top-view image choice** is an ordered `(predicate, handler)` dispatch list
  (`_set_next_top_view_image`, `:392`) with `else: raise AssertionError` for an
  unhandled state — series states pick a random title from that series, index/
  intro states use a hard-coded inset, tag/category states pick from the tag's
  titles with a fixed fallback, and so on.

The **fun-image theme policy** (decade filters, "classics", file-type themes)
lives in the pipeline, not the image selector: `_get_themed_fun_image_titles`
(`:637`) translates the requested `ImageThemes` into a `(title_list, file_types)`
pair, cached, then handed to the selector.

### 5.4 Choosing the actual image file

`ImageSelector` (`core/image_selector.py:103`) picks concrete files, delegating
all filesystem access to an `ImageFileResolver` protocol (`:58`, production impl
`ReaderFilePathsResolver`). Its workhorse `get_random_image` (`:250`) makes up to
10 attempts to pick a title and a candidate file that isn't in a 100-entry MRU
deque (so you don't see the same panel twice in a row), optionally upgrading the
fit mode. The result is an `ImageInfo(filename, from_title, fit_mode)` (`:44`).

### 5.5 Applying the snapshot to widgets

`SnapshotApplicator` (`ui/snapshot_applicator.py:35`) is described in its own docs
as "the only class that directly touches these Kivy widgets." Its `apply()`
(`:51`) fans out to `_apply_top_view`, `_apply_fun_view`, `_apply_title_view`,
`_apply_screen_visibility`, `_apply_search_view`. Each sets the cheap properties
(visibility, opacity, color, fit mode) immediately and **defers the texture**:
it holds four `PanelTextureLoader`s (one per view) and loads the image
asynchronously, so a slow disk read never blocks the UI thread. Change
suppression (skip reload when the `ImageInfo` is unchanged) keeps it cheap.

The async chain — important, because you'll see it again in section 6:

1. `PanelTextureLoader.load_texture` (`ui/panel_texture_loader.py:34`) delegates
   the read/decode to `PanelImageLoader.load_pil`.
2. `PanelImageLoader` (`core/panel_image_loader.py:39`) runs the heavy I/O +
   Pillow decode on a **daemon thread** (`_worker`, `:79`), killing any in-flight
   thread first.
3. On completion it marshals back to the UI thread via
   `self._scheduler.schedule_once(...)` (`:95`, `:98`) — **this is what the
   `Scheduler` port is for**: crossing the thread boundary without importing
   Kivy's `Clock` into `core`.
4. Back on the UI thread, `PanelTextureLoader._pil_to_texture` (`:45`) uploads
   the PIL image to a Kivy `Texture` (`Texture.create` → `blit_buffer` →
   `flip_vertical`) — texture upload *must* happen on the UI thread, and this
   split guarantees it.

### 5.6 Who wires it together

The composition root is `build_main_screen_components()`
(`ui/main_screen_components.py:64`) — one function that constructs and injects the
whole graph: the `ImageSelector`, the `ViewPipeline` (with `scheduler=KivyClockScheduler()`
and `colors=TintColorSource()` injected as ports), the `SnapshotApplicator`, and
the `ViewRenderer` (with a `NavigationModel` and the `on_view_state_changed`
callback). `ViewRenderer`'s entry points — `render(destination)`,
`render_state(view_state)`, `render_title(fanta_info)`, `refresh()` — all funnel
through `_dispatch` (`ui/view_renderer.py:222`), the single seam between
navigation and rendering.

---

## 6. Opening a comic

Selecting a title to *read* leaves the main-screen view pipeline entirely and
enters the comic reader — a separate top-level screen with its own threaded
image loader. The split across `core`/`ui` holds here too: `core` owns
orchestration, threading, and I/O; `ui` owns the widget that paints textures;
they talk through `core/ports/comic_reader.py`.

### 6.1 End-to-end trace

1. **Trigger** — pressing the title portal image calls
   `NavigationCoordinator._read_comic(...)` (`ui/navigation_coordinator.py:319`),
   which deactivates the current screen and calls
   `comic_reader_manager.read_barks_comic_book(...)`.
2. **Manager** — `ComicReaderManager.read_barks_comic_book` (`core/comic_reader_manager.py:109`)
   → `_read_comic_book(...)` (`:126`).
3. **Prep** — `prepare_comic_for_reading(...)` (`core/reader_setup.py:47`) builds
   the `ComicLayout`, chooses a decryption function based on whether panels are
   encrypted (`:60`), constructs a `ComicBookImageBuilder`, and returns
   `(layout, image_builder)`.
4. **Resume session begins** — `LastReadPageTracker.begin(title, layout, save_enabled)`
   (`:151`).
5. **Hand to the widget** — through the `ComicBookReaderPort`,
   `comic_book_reader.read_comic(...)` (`:156`). A `MissingVolumeError` here is
   caught, shown to the user, and schedules the reader to close after 1s.
6. **Widget setup** — `ComicBookReader.read_comic()` (`ui/comic_book_reader.py:411`)
   sets up page state, double-page mode, and the page map, then
   `resolve_archive_for_comic(fanta_info)` (`:444`) and constructs an
   `ArchivePageImageSource` (`:447`).
7. **Start loading** — `comic_book_loader.set_comic(image_source, load_order, page_map, …)`
   (`:457`). The **load order** (`_ComicPageManager.get_image_load_order`, `:246`)
   is deliberate: the page you're jumping to first, then its neighbor, then
   forward, then the rest backward — so the opening page appears fastest.
8. **First page** — when the loader thread finishes the target page it schedules
   `_first_image_loaded` on the UI thread, which sets `_current_page_index`; that
   `NumericProperty` is bound to `_show_page` (`:329`), which pulls the decoded
   PNG stream and uploads `CoreImage(stream).texture` to the `Image` widget
   (`:570`).

### 6.2 Where pages come from, and decryption

Archives are ZIPs, in one of two modes (chosen by `reader_settings.use_prebuilt_archives`):

- **Prebuilt** — one `.cbz` per comic; pages read straight from `images/<name>`
  inside the zip.
- **Fantagraphics volumes** — per-volume archives via `FantagraphicsVolumeArchives`,
  with a resolution priority (`core/archive_page_image_source.py:135`): title/blank
  page → extra-images map → **override** map (if overrides active) → base archive.

The `PageImageSource` protocol (`core/page_image_source.py:20`) hides all of this
— I/O, decryption, transform, resize — behind `load_page_image(page_info) →
(BytesIO, str)`. The production implementation `ArchivePageImageSource`
(`:36`) does: resolve path → read → (for Fanta volumes) assemble/transform the
page via `ComicBookImageBuilder.get_dest_page_image` → `resize_contain` (LANCZOS)
→ encode an **uncompressed** PNG (`compress_level=0`, for speed).

**Decryption is the load-bearing subtlety** (and the subject of recent bug
fixes). The decryptor is a *generated module* (`comic_utils/get_panel_bytes.py`,
emitted by `scripts/generate-panel-module.sh` with an XOR-masked key; in a
standalone build Nuitka compiles it to native code, so neither the key nor the
logic ships as readable source) that **returns empty bytes to any caller not
on its allow-list**. Only two modules may reach it:
`comic_utils.pil_image_utils.load_pil_image_from_zip` and this repo's
`barks_reader.core.panel_image_loader`. Notably, `core/image_pipeline.py` is
**not** allow-listed and its docstrings warn it must never call the decryptor
directly. Base archive pages are read unencrypted; **override-archive pages are
encrypted**. This is exactly the trap behind commit 605788f ("wiki background
decryption"): the wiki's image provider called `image_pipeline.load_pil`
directly, wasn't allow-listed, got empty bytes, and raised `DecryptionError` —
fixed by routing it through the allow-listed `panel_image_loader.load_panel_pil`.

### 6.3 Threading

`ComicBookLoader` (`core/comic_book_loader.py:52`) orchestrates a single
background loader thread plus a worker pool, never touching Kivy, marshaling back
via injected `Scheduler` + `Cursor` ports:

- `set_comic()` (`:179`) stops any prior load, creates one `threading.Event` per
  page, and starts the daemon loader thread.
- `_load_pages()` (`:403`) runs a `ThreadPoolExecutor` with a **dynamic sliding
  prefetch window** — worker count auto-tuned to the platform, window size
  growing/shrinking with live memory pressure.
- Futures complete out of order; each result is stored at its page-index slot and
  its Event is set. The first-displayed page triggers an early UI callback; when
  all pages finish, another callback fires.
- The widget consumes results synchronously via
  `get_image_ready_for_reading(idx)` (`:212`) or a double-page composite (`:224`),
  and can block on `wait_load_event(idx, timeout)` (`:257`) for a page that isn't
  loaded yet.

### 6.4 The reader widget, page manager, and resume

`ui/comic_book_reader.py` holds three cooperating classes:

- **`_ComicPageManager`** (`:82`) — pure page-navigation state (page map, index
  maps, double-page display units, `next_page`/`prev_page`/`goto_*`). It knows
  nothing about images; moving its `_current_page_index` is what drives redisplay.
- **`ComicBookReader`** (`:274`) — owns the `ComicBookLoader` and the single Kivy
  `Image` widget, binds page-index → `_show_page`, handles margin-click page
  turns and the goto-page dropdown.
- **`ComicBookReaderScreen`** (`:706`) — the host screen; owns the action bar
  (fullscreen, double-page toggle, goto start/end, close), the window-mode
  transitions, and the close lifecycle. It implements both comic-reader ports.

**Resume tracking** is bracketed by `LastReadPageTracker.begin/end`
(`core/last_read_page_tracker.py`). On close (`on_comic_closed` →
`comic_closed()` → `tracker.end(...)`), it reads the widget's last page, resolves
it through the layout (in double-page mode, preferring the right page unless the
left is an edge), and persists a `SavedPageInfo` (`core/saved_page_info.py:14`)
as JSON via `SettingsManager`. A finished comic is normalized back to its cover
so next time you start fresh.

The same open/close bracket also feeds the **reading-history log**:
`_read_comic_book` calls `ReadingHistoryTracker.begin`
(`core/comic_reader_manager.py:164`) and `comic_closed()` passes the resolved
`SavedPageInfo` to `ReadingHistoryTracker.end` (`:192`). Section 7.5 covers the
whole subsystem.

### 6.5 A note on "panel-by-panel" vs. "comic page"

Don't confuse the two image paths. The full **comic page** display
(`comic_book_reader.py`) uses `ComicBookLoader` + `ArchivePageImageSource`. The
`PanelImageLoader` / `PanelTextureLoader` pair (section 5.5) loads **individual
Barks panels/insets** — the backgrounds, title views, fun images, index
thumbnails, and wiki backgrounds — and those panels are *always* encrypted
(`core/panel_image_loader.py:81`).

---

## 7. The UI shell

The visible app is a **fixed registry of four top-level screens** plus a set of
sub-screens toggled inside the main screen. Keeping these two mechanisms
distinct is the key to reading `ui/`.

### 7.1 The two levels

**Top-level screens** are real `ScreenManager` screens; exactly one is visible,
switching is an animated push/pop:

| Screen | Location | Purpose |
|---|---|---|
| `MainScreen` | `ui/main_screen.py:58` | The always-present shell (action bar + tree + bottom pane). |
| `ComicBookReaderScreen` | `ui/comic_book_reader.py:706` | Page-by-page reader. |
| `DocumentReaderScreen` | `ui/document_reader.py:31` | Simple image-page "How To" viewer. |
| `WikiReaderScreen` | `ui/wiki_reader.py:96` | Embedded Carl Barks Wiki (OKF viewer). |

**Sub-screens** are plain layouts stacked inside the `MainScreen` bottom pane,
grouped by the `ScreenBundle` dataclass (`ui/screen_bundle.py:21`) and toggled by
an `is_visible` property — *not* by the screen manager: `TreeViewScreen`,
`BottomTitleViewScreen`, `FunImageViewScreen`, `MainIndexScreen`,
`SpeechIndexScreen`, two `EntityIndexScreen`s (names, locations),
`StatisticsScreen`, `HistoryScreen`, `SearchScreen`.

### 7.2 The main screen layout

`ui/main_screen.kv` composes a vertical `BoxLayout`: an action-bar row on top,
and a content area filled at runtime by `_wire_screens` (`ui/main_screen.py:131`)
— the `TreeViewScreen` plus a single wrapper `Screen` into which all nine bottom
sub-screens are stacked. Only one bottom screen shows at a time, and their
`is_visible` flags are pushed by `SnapshotApplicator` (section 5.5).

The **fun view and the bottom title view** are mutually exclusive presentations
of the same pane: the title view (with its reading controls, Wiki-Page chip,
goto-page, use-overrides checkbox) shows when a title is selected; the fun view
(rotating decorative panels with prev/next history) is the default otherwise.

### 7.3 Screen management and the action bar

`ReaderScreenManager` (`ui/reader_screens.py:79`) owns the single `ScreenManager`.
Screens are never switched directly — instead a `ScreenSwitchers` bundle of
callbacks (`:65`) is handed to collaborators, so nothing outside this module
imports the screen manager. Each pushed screen gets a named switch/close pair
(e.g. `_switch_to_comic_book_reader` / `_close_comic_book_reader`), and "close"
always returns to main and calls the corresponding `on_*_closed` hook so the main
screen re-activates.

The **action bar** (`ReaderActionBar`, `ui/action_bar.py:32`) is a shared
skeleton reused by the main/comic/document screens; its draggable title region is
what backs `Window.set_custom_titlebar`. The main screen's buttons
(`main_screen.kv:89–131`): fullscreen toggle, **Go Back** (which is
*tree-navigation* back to the previous node — `on_action_bar_go_back` →
`tree_view_manager.go_back_to_previous_node()`, **not** a screen pop), Collapse
(close all open tree nodes), Change Pics (new random images + `renderer.refresh()`),
Menu (Settings/How To/About dropdown), and Quit (fenced off by a separator so an
overshoot can't hit it).

### 7.4 The specialized screens

- **Search** (`ui/search_screen.py:92`) — three mode panels (Title/Tag/Word)
  swapped by opacity; all queries go through `barks_fantagraphics.comic_search.ComicSearch`
  over the reader's index dir. Selecting a result invokes injected
  `on_goto_title` / `on_goto_title_with_page` callbacks that route back into
  navigation.
- **Index screens** (`ui/index_screen.py` base) — A–Z alphabet menu + item grid +
  drill-down + heavy keyboard nav. `MainIndexScreen` builds its index purely from
  the in-memory bibliography (`Titles`/`Tags`/`TagGroups`); `SpeechIndexScreen`
  and `EntityIndexScreen` query `ComicSearch` for words/entities and show
  speech-bubble popups.
- **Wiki** (`ui/wiki_reader.py` + `core/wiki_integration.py`) — hosts an
  `okf_reader.OKFViewer` built lazily on first open. Barks-specific behavior comes
  from Kivy-free providers in `core/wiki_integration.py`: `BarksPanelsImageProvider`
  backs pages with panel imagery (through the shared `ImageSelector`, handling the
  encrypted-zip decrypt), and `BarksTableRewriter` applies the parenthesized-title
  convention. "Goto Title" closes the wiki and calls `MainScreen.goto_title_from_wiki`.
- **Statistics** (`ui/statistics_screen.py:78`) — pure display: a tab bar over
  pre-rendered PNG charts plus a word-cloud dropdown discovered by globbing. No
  live querying.

### 7.5 Reading History

Every comic you open is recorded to a persistent event log, browsable from a
top-level **Reading History** tree node (between Search and Appendix). The
feature splits cleanly along the core/ui line.

**Recording (core)** — `core/reading_history.py`, Kivy-free:

- `ReadEvent` (`:35`) is one reading session: title, opened/closed timestamps,
  and the last display/body page. Events serialize to JSON.
- `ReadingHistoryStore` (`:77`) persists the log to
  `barks-reader-history.json` beside the app settings
  (`ReaderSettings.get_user_history_path`, `core/reader_settings.py:159`) —
  the JSON-store sibling of `barks-reader.json` (§8.3). It tolerates a
  missing/corrupt file (starts empty with a logged error) and rewrites the
  whole file on every mutation.
- `ReadingHistoryTracker` (`:134`) brackets a session with `begin`/`end`,
  mirroring `LastReadPageTracker`. Recording is gated by an injected
  `is_enabled` callable — bound at the composition root to the
  **Record Reading History** settings toggle
  (`record_reading_history`, `core/reader_settings.py:254`) — and the clock is
  injectable for tests.
- The hook lives in `ComicReaderManager`: `begin` fires in `_read_comic_book`
  (`core/comic_reader_manager.py:164`) only when `save_last_page` is true, so
  **articles are never recorded**. A one-pager read via the "All One-Pagers"
  collection passes `history_title_str` (`ui/navigation_coordinator.py:368`)
  so the history records the *individual one-pager*, not the collection.
  `end` fires from `comic_closed` (`:192`) with the same `SavedPageInfo` the
  resume tracker just persisted (§6.4).
- Pure derivation helpers turn the raw log into the two views:
  `group_events_by_day` (`:218`, newest-first day groups with
  "Today"/"Yesterday" headings) and `summarize_titles` (`:239`, per-title
  read count + last-opened time; the last-page fields come from the most
  recent event *that recorded a page*, so a crash-truncated session doesn't
  hide the reading position). Formatting helpers (`:273–309`) render duration
  ("1 hr 5 min"), open time, and "to p N" / "at p N" fragments — a finished
  comic's position is normalized to the cover (§6.4), so only genuinely
  mid-comic positions produce a page fragment.

**Browsing (ui)** — `HistoryScreen` (`ui/history_screen.py:130`), a bottom
sub-screen wired exactly like Statistics:

- Two toggleable views over the same log: **Journal** (sessions grouped by
  day, with time/duration/last-page columns) and **Titles** (one row per
  title with read count and unfinished-at-page). The screen holds no cached
  rows — it re-reads the store every time it becomes visible or is modified
  (`on_is_visible` → `_refresh`, `:209`).
- Clicking any cell of a row navigates to that title's tree view
  (`on_goto_title` → `MainScreen._on_goto_history_title`); each row has a
  delete button, and the top bar has a clear-all button behind a confirmation
  popup (`on_clear_pressed`, `:449`).
- The backdrop is a random panel drawn *from the history's own titles*
  (`update_background_image`, `:166`, via the shared `ImageSelector`), and
  refreshes with the action bar's Change Pics button.
- Full keyboard navigation (`enter_nav_focus`/`handle_key`, `:359`/`:376`):
  Up/Down move the row focus (Page Up/Down jump 10 rows), Left/Right switch
  Journal/Titles, Enter opens the focused row's title, Delete removes it,
  Esc returns focus to the tree. `MainScreenNavigation` routes Enter on the
  tree node into the panel like it does for Statistics
  (`ui/main_screen_nav.py:272`).

**Navigation wiring** is a textbook run of the §4.4 recipe: a payload-free
`HistoryDestination` mapped to `ViewStates.ON_HISTORY_NODE` in the dispatch
table (`core/navigation/navigation_model.py:93`), a `history_spec` node in
the tree spec (`core/navigation/tree_spec.py:359`), a
`_BOTTOM_VIEW_HISTORY_OPACITY_1_STATES` set plus a fixed *Good Neighbors*
top-view image in the pipeline (`core/view_pipeline.py:112`, `:439`), and a
`ScreenVisibility.history` flag applied by `SnapshotApplicator`.

### 7.6 How screens get their data

Two channels, and it's worth keeping them straight:

- **Sub-screens get snapshots.** The tree background, fun image, title view, and
  each screen's `is_visible` all arrive as `ViewSnapshot` fields applied by
  `SnapshotApplicator`. No screen mutates another; the snapshot is the contract.
- **Pushed screens get direct calls.** The comic/document/wiki readers receive
  their payload through the switcher methods (`open_document`, `open_wiki`, the
  comic reader via `ComicReaderManager`). Statistics and index screens build their
  own data at construction and only receive `is_visible`.

The wiring hub for all the "goto" callbacks is
`MainScreen._bind_screen_callbacks` (`ui/main_screen.py:186`), routing every
screen's navigation callback through `NavigationCoordinator`. The whole
collaborator graph (renderer, nav coordinator, tree view manager, comic reader
manager, window helper) is assembled once in `build_main_screen_components`,
keeping `MainScreen.__init__` thin.

---

## 8. Ports, adapters, and cross-cutting

This section makes the section-1 idea concrete: the actual ports, their Kivy
adapters, and the shared concerns (settings, colors, fonts, errors, paths).

### 8.1 The ports and their adapters

Every place `core` needs a host capability, it depends on a `@runtime_checkable`
Protocol in `core/ports/`; `ui` satisfies it structurally. The fakes in
`core/testing/fakes.py` satisfy the same Protocols with no Kivy — that's the
whole point.

| Port | Abstracts | Production adapter | Test fake |
|---|---|---|---|
| `Scheduler` (`ports/scheduler.py:21`) | Marshal a callback onto the UI thread (one-shot + repeating) | `KivyClockScheduler` (`ui/adapters/kivy_scheduler.py:26`) | `FakeScheduler` |
| `Cursor` (`ports/cursor.py:9`) | Busy/normal cursor for long loads | `KivyCursor` (`ui/adapters/kivy_cursor.py:8`) | recording |
| `ColorSource` (`ports/color_source.py:21`) | `next_color(palette)` view tints | `TintColorSource` (`ui/adapters/tint_color_source.py:34`) | `ScriptedColorSource` |
| `SnapshotSink` (`ports/snapshot_sink.py:12`) | `apply(ViewSnapshot)` | `SnapshotApplicator` (`ui/snapshot_applicator.py:35`) | `RecordingSink` |
| `ComicBookReaderPort` (`ports/comic_reader.py:22`) | The reader widget's API | `ComicBookReader` | — |
| `ComicBookReaderScreenPort` (`ports/comic_reader.py:54`) | The reader host screen | `ComicBookReaderScreen` | — |

A nice detail: `ColorSource`'s adapter lives in `ui/adapters/`, but the
`RandomColorTint` engine it wraps is itself Kivy-free (`core/reader_colors.py`).
The adapter exists only to hold the palette config and satisfy the port, not to
bridge Kivy.

### 8.2 Dependency injection

Adapters are wired into `core` by **constructor injection at one composition
root**: `build_main_screen_components` (`ui/main_screen_components.py:64`), which
replaced a ~120-line inline `MainScreen.__init__`. A second, smaller composition
site is the comic reader itself (`ui/comic_book_reader.py:319` injects
`KivyClockScheduler()` + `KivyCursor()` into `ComicBookLoader`). Adapters are
always pulled in via `from .adapters import …`.

### 8.3 Settings

- **Model** — `core/reader_settings.py`. Each setting is a declarative `FieldSpec`
  (`:66`) — one source of truth for the Kivy schema entry, the config default,
  and an optional validator. All specs live in `_FIELDS` (`:370`). `ReaderSettings`
  (`:130`) exposes typed properties funneling through `_read(key)` (`:164`). It
  stays in `core` by depending on structural `ConfigReader`/`ConfigParser`/`Settings`
  Protocols that both Kivy's and stdlib's config parsers satisfy.
- **Persistence — two stores.** App settings live in a Kivy-style **ini** file;
  user data / reading progress lives in a plain **JSON** store
  (`core/json_settings_manager.py`) recording the last-selected tree node and
  per-title last-read page.
- **Kivy UI** — `ui/reader_settings_buildable.py` (`BuildableReaderSettings`
  subclasses the pure model, adding `build_config`/`build_settings`/validators)
  plus custom widgets in `ui/settings_fix.py`.
- **Change propagation** — `core/settings_notifier.py` is a Kivy-free
  `(section, key) → callbacks` registry; the singleton `settings_notifier.notify`
  fires from `BarksReaderApp.on_config_change` (`ui/barks_reader_app.py:207`),
  and screens subscribe to the changes they care about.

### 8.4 Other cross-cutting concerns

- **Colors** — `core/reader_colors.py` (`RandomColorTint`, Kivy-free), reached
  from `core` only through the `ColorSource` port.
- **Fonts** — `ui/font_manager.py`: two font themes selected by the 1090px
  window-height cutoff (section 2.3), ~50 `NumericProperty` sizes bound in `.kv`.
- **Errors — two subsystems, both split pure/UI.** *Recoverable user errors*:
  pure types/messages in `core/user_error_types.py` + `core/user_error_messages.py`,
  presented by `ui/user_error_handler.py`. *Fatal crashes*: `ui/error_handling.py`
  formats the traceback and shows a standalone popup, wired to the excepthooks
  from section 2.2.
- **File paths — three collaborators, all Kivy-free `core`:** `ReaderFilePaths`
  (panel-image sources, incl. the encrypted-zip handling), `ReaderFilePathsResolver`
  (a thin `resolve(...)` adapter over it, consumed by `ImageSelector`), and
  `SystemFilePaths` (app assets: icons, backgrounds, docs, statistics). All three
  are bootstrapped by the Kivy-free `bootstrap_reader_environment`
  (`core/reader_setup.py:25`), shared by the app and CLI scripts.

---

## 9. End-to-end traces

Three short traces that stitch the sections together. Follow them with the
section references open.

### Trace A — the app starts and shows the intro

`python main.py` → `config_info` sets `KIVY_HOME` (§2.1) → `main()` sizes the
hidden window (§2.2) → `reader_main` builds `ComicsDatabase` (§3) and
`BarksReaderApp` → `build()` loads `.kv` and `_build_screens()` (§2.2 step 9) →
tree build is deferred → loop starts → `AppInitializer` renders
`ViewStates.INITIAL` through the **view pipeline** (§5): `ViewRenderer.render_state`
→ `ViewPipeline` computes a `ViewSnapshot` with a fixed intro background →
`SnapshotApplicator` loads that texture off-thread (§5.5) → ~2s later
`Window.show()` reveals the frame (§2.2 step 11).

### Trace B — the user browses to a title and reads it

Click a series node → `TreeViewManager.on_node_expanded` (§4.3) → lazy-populate
its title rows → `renderer.render(SeriesDestination)` → `NavigationModel`
resolves `ON_SERIES_*` → pipeline paints a series background (§5.3). Click a
title row → `on_title_row_button_pressed` → `nav.select_title` →
`renderer.render_title` → the **bottom title view** shows with its portal image
(§7.2). Press the portal → `NavigationCoordinator._read_comic` →
`ComicReaderManager` (§6.1) → `prepare_comic_for_reading` builds the layout →
`ComicBookReader.read_comic` resolves the archive and starts `ComicBookLoader`
(§6.3) → the opening page loads first (§6.1 step 7) → `_show_page` uploads its
texture → the comic reader screen is now on top (§7.1). Close it →
`tracker.end` persists the last-read page (§6.4) → `render_state` restores the
previous main-screen view.

### Trace C — a background image appears (and why decryption matters)

Any main-screen render asks `ImageSelector.get_random_image` (§5.4) for a panel
file → `SnapshotApplicator` hands it to a `PanelTextureLoader` →
`PanelImageLoader._worker` reads it on a daemon thread through the **allow-listed**
`load_panel_pil` (§6.2), which is permitted to call the panel decryptor → the
decrypted PIL image is marshaled back via the `Scheduler` port (§5.5 step 3) →
uploaded to a texture on the UI thread. If a caller *not* on the allow-list (like
the old wiki provider) tries the same, the decryptor returns empty bytes and the
load fails — the bug fixed in commit 605788f (§6.2).

---

## Where to go next

- **Change navigation targets:** §4.4 (the `Destination` + `NavigationModel` +
  `NodeSpec` recipe).
- **Change what the main screen shows:** §5.3 (the view-state sets and dispatch
  list in `core/view_pipeline.py`).
- **Change comic loading/decryption:** §6.2–6.3 (mind the decryptor allow-list).
- **Add a screen:** §7.1, §7.3 (top-level vs. sub-screen; the `ScreenSwitchers`
  pattern).
- **Add a host capability to `core`:** §8.1 (define a port, add a Kivy adapter,
  wire it at the composition root), then run `uv run lint-imports`.
