# Plan: Unify the two WindowManager instances into one shared instance

> Status: **not started** — scoped design, saved for later execution.
> Related backlog item: `docs/BACKLOG.md` → "Two `WindowManager` instances over
> one global `Window`". Line numbers below are indicative and may drift.

## Context

Fullscreen/windowed toggling runs through `WindowManager`
(`ui/platform_window_utils.py`), which owns the toggle state machine, the saved
window geometry (`_saved_window_state`), and a platform backend. Today **two**
instances exist over the single global Kivy `Window`:

- `MainScreenWindowHelper` builds one (`ui/main_screen_window.py:48`).
- `ComicBookReaderScreen` builds another (`ui/comic_book_reader.py:735`).

Correctness relies on only one being "active" at a time, with **no
coordination**, and — because each has its **own** geometry store — the main
screen has to *seed* the comic reader's store with the current windowed geometry
before going fullscreen (the `seed_/clear_windowed_restore_geometry` coupling
documented in commit `30cd542`). That coupling exists **only** because the store
is per-instance.

**Goal:** one shared `WindowManager` instance, injected into both screens, so the
saved geometry lives in one place. This removes the uncoordinated-duplicate-state
hazard and lets the seeding coupling be deleted outright. Behaviour is unchanged.

**Scope: core unification only.** Fragility #4 (dedup the `"Fullscreen"`/`"Windowed"`
label strings + shared toggle/finish scaffolding) is a separate later pass, not
this change.

## Approach

The blocker to sharing one instance is that the 3 finish callbacks are baked in at
construction and **differ structurally per screen** (main: font updates +
host-height clamp + `show_action_bar`; comic: `is_fullscreen` property +
`_update_widget_states` + `_is_closing`/`_finish_closing_comic` + `pos_hint`). So:
move the callbacks from the **constructor** to **per-operation** arguments.

### 1. `WindowManager` API change (`ui/platform_window_utils.py`)

- Add a small bundle:
  ```python
  @dataclass(frozen=True)
  class WindowModeCallbacks:
      on_windowed_first_resize: Callable[[], None]
      on_finished_windowed: Callable[[], None]
      on_finished_fullscreen: Callable[[], None]
  ```
- Constructor drops the 3 callback params → `WindowManager(client: str)`. Keeps
  `_saved_window_state` and `_backend` (still the single geometry store — now
  shared).
- `goto_fullscreen_mode(callbacks)` / `goto_windowed_mode(callbacks)` take the
  bundle. Stash it transiently (`self._active_callbacks = callbacks`) at the start
  so the existing `Clock`-chained internal steps (`do_windowed` →
  `restore_saved_size_and_position` → `_finish_restore`) read from it instead of
  `self._on_finished_*`. Safe because transitions are single-in-flight on the UI
  thread (already guarded by the `is_fullscreen_now()` early-returns). The
  early-return paths call the passed bundle's matching callback.
- The unsaved-geometry guard added in `1ddfd4b` (`is_unsaved()` path) uses the
  same `self._active_callbacks`.
- Statics `is_fullscreen_now()` / `get_screen_mode_now()` read the global `Window`
  — unchanged; their many call sites (`reader_navigation.py`, `wiki_reader.py`,
  both screens) are untouched.

### 2. Own + inject one instance (`ui/barks_reader_app.py`)

Construct `self._window_manager = WindowManager("Reader")` **before** building the
screens (before `barks_reader_app.py:362`), then inject the same instance into
both:

- **Main:** add a `window_manager` param to `MainScreen.__init__`
  (`ui/main_screen.py`), thread it into `build_main_screen_components(host, window_manager)`
  (`ui/main_screen_components.py:103`), and pass it to `MainScreenWindowHelper(window_manager=...)`.
  `MainScreenWindowHelper` stops calling `WindowManager(...)` and instead stores
  the injected instance, plus builds one `WindowModeCallbacks(self._set_hints_for_windowed_mode,
  self._on_finished_goto_windowed_mode, self._on_finished_goto_fullscreen_mode)`
  it passes on each `goto_*` call.
- **Comic:** add a `window_manager` param to `get_barks_comic_reader_screen(...)`
  (`comic_book_reader.py:1078`) and `ComicBookReaderScreen.__init__`; store it,
  drop the `WindowManager(...)` build at line 735, and pass its own
  `WindowModeCallbacks` per `goto_*` call.

Each screen keeps its existing 3 callback methods verbatim — only their delivery
changes (per-call bundle instead of constructor).

### 3. Delete the seeding coupling

With one shared store, the main screen's fullscreen `save_state_now()` is the same
geometry the comic reader restores, so the handoff is redundant. Remove:

- `seed_windowed_restore_geometry` / `clear_windowed_restore_geometry` on
  `ComicBookReaderScreen` (`comic_book_reader.py:891-909`) and their passthroughs
  on `ComicReaderManager` (`comic_reader_manager.py:78-94`).
- The two calls in `MainScreenWindowHelper._goto_fullscreen_mode` /
  `_goto_windowed_mode` (`main_screen_window.py`).
- `save_state_now()` becomes internal-only (called inside `goto_fullscreen_mode`);
  `clear_state()` loses its external caller but stays (tested; harmless).

### What stays per-screen (unchanged)

`_was_fullscreen_on_entry`, `_exit_fullscreen`, `is_fullscreen` BooleanProperty,
`_is_closing`, `can_benefit_from_fullscreen`, `_update_window_mode`, the main
screen's `_change_fullscreen_win_size` host sizing + `_update_fonts`, and every
resize-driven layout path. This refactor only unifies the *window-mode engine and
its geometry store*, not per-screen policy.

## Tests

- **`test_window_manager.py`** — update the `manager` fixture to build
  `WindowManager(client="test")` (no callbacks) and pass a `WindowModeCallbacks`
  (MagicMock members) into the `goto_*` calls; assert callbacks fire via the
  bundle. Keep the fake-backend + monkeypatched `Window`/`Clock` style. Keep the
  `is_unsaved` sentinel-skip regression (route through the bundle). Add a test
  framing the cross-screen guarantee: `goto_fullscreen_mode` saves geometry that a
  later `goto_windowed_mode` restores — i.e. the seeding scenario now works via the
  shared store with no explicit seed.
- **`test_main_screen_window.py`** — helper now receives an injected
  `WindowManager` (MagicMock) instead of patching the class. **Remove** the
  seed/clear assertions (`TestGotoFullscreenMode`/`TestGotoWindowedMode`/`TestExitFullscreen`).
  Assert `goto_*` is invoked on the injected manager with a `WindowModeCallbacks`.
- **`test_comic_book_reader.py`** — the `screen` fixture injects a mock
  `WindowManager` instead of patching the class; `test_toggle_screen_mode` updated
  accordingly.
- **`test_comic_reader_manager.py`** — no window refs today; confirm the deleted
  passthroughs aren't referenced.

## Verification

1. **Unit:** `uv run pytest` (targeted: `test_window_manager.py`,
   `test_main_screen_window.py`, `test_comic_book_reader.py`).
2. **Gates:** `uv run ruff check . && uv run ruff format .`, `uv run ty check`,
   `uv run lint-imports`, `bash scripts/git-cspell.sh`.
3. **Manual end-to-end (`uv run main.py`)** — behaviour must be unchanged; exercise
   the paths the unit tests can't drive (real `Window`):
   - **Seeding scenario (the one we're deleting):** enter fullscreen from the main
     screen → open a comic (enters already-fullscreen) → toggle the comic to
     windowed → the window must restore the **original windowed size/position**.
     This is the regression to watch — it now relies on the shared store.
   - Main screen Fullscreen ⇄ Windowed toggle; fonts/action-bar/geometry restore.
   - Comic auto-fullscreen on read (`goto_fullscreen_on_comic_read`) → close →
     returns to the entry mode.
   - App started already fullscreen → exit to windowed (the `is_unsaved` guard).
4. `graphify update .` after code changes; tick the "two WindowManager instances"
   item in `docs/BACKLOG.md`, noting the seeding coupling is now gone.

## Out of scope

Fragility #4 (dedup `"Fullscreen"`/`"Windowed"` label strings + extract shared
toggle/finish scaffolding) — separate pass. This change deliberately keeps each
screen's callback bodies byte-for-byte identical to isolate the unification.
