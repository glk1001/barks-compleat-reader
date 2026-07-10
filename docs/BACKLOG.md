# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-07-10.

---

## Wiki reader (OKF integration)

The wiki is integrated as a top-level app screen. Remaining polish:

- [x] **In-wiki search** (commits 1540f77, ad28850, 1ac48bf) — wiki page search
      (title + heading) in the OKF reader, with result-list persistence and
      index-build failure recovery (`okf_reader/core/search.py`).
- [ ] **Escape-back inside the wiki screen** — currently only mouse4 works while
      embedded; the app owns keyboard keys, so Escape doesn't navigate back.
- [ ] **Async panel textures** — load large panel-background images off the UI
      thread to avoid stalls.
- [x] **Shared kv action-bar extraction** (2026-07-10) — one `ReaderActionBar`
      skeleton (`ui/action_bar.py` + `ui/action_bar.kv`, content-redirect
      pattern) now serves the main, comic, *and* document screens (the document
      bar dropped its stock-Kivy `ActionBar` idiom); screens declare only their
      own `BarButton`s. Style constants single-sourced in
      `core/reader_consts_and_types.py`. The wiki bar (generic okf-reader,
      Python-built) can't consume barks kv — instead its mirrored constants
      moved onto `TopBarSpec` style fields and `wiki_top_bar_spec` passes the
      shared values in, with tests pinning both ends against drift.

Known limitation (intentional, not a reader fix): links under the bundle's
`source/web` tier (inducks) don't navigate — they are raw scraped `.html`, not
`.md`. That's bundle curation, owned by the read-only `../barks-wiki` repo.

## Data completeness (`barks_fantagraphics`)

- [ ] **Regenerate unauthored dates** — ~107 `_TODO = (0, 0, 0)` placeholder
      entries in `comic_book_info.py` mark stories with unknown authored dates.
      Regenerate from the bibliography source (`experiments/bibliography/`).
- [ ] **Reconcile date discrepancies** — ~24 dates flagged as differing from
      Barrier's bibliography when `barks_bibliography.py` was generated.
- [ ] **Tag data validation** — resolve the `TODO: NEED TO CHECK THESE` markers
      in `barks_tags_data.py` (incomplete data validation).

## Naming consistency (cross-repo — deferred)

> ⚠️ **Not low-risk.** These names are public API consumed by the sibling repos
> `../barks-ocr` and `../barks-comic-building` (~36 files). A rename is a
> coordinated, breaking, 3-repo change — do it deliberately, all at once, not
> piecemeal.

- [ ] **`srce` → `source`** — 462 in-repo occurrences, baked into public
      `ComicsDatabase` / file-path resolver method names.
- [ ] **Normalize `upscayl` spelling** — `upscayl` / `upscayled` / `upscaled`
      used inconsistently. Note: "Upscayl" is a real tool, so `upscayled`
      ("processed by Upscayl") may be a deliberate coinage — confirm intent
      before flattening to `upscaled`.

## Fullscreen / window management (robustness — deferred)

> Surfaced while adding monitor-safe fullscreen sizing to the wiki reader
> (`WikiReaderScreen._apply_viewer_sizing`). The wiki fix deliberately avoids
> these patterns (no second `WindowManager`, no cross-object state reach); the
> pre-existing hazards below remain in the main/comic screens and want a
> separate consolidation pass.

- [x] **Two `WindowManager` instances over one global `Window`** (2026-07-09) —
      unified onto a single shared `WindowManager` instance, constructed in
      `barks_reader_app._build_screens` and injected into both `MainScreen` and
      `ComicBookReaderScreen`. Per-transition completion callbacks moved from the
      constructor to a `WindowModeCallbacks` bundle passed on each `goto_*` call,
      so one manager can serve both screens. With one shared geometry store, the
      cross-object seeding coupling is **gone**: `seed_`/`clear_windowed_restore_geometry`
      (screen + `ComicReaderManager` passthroughs + `MainScreenWindowHelper` calls)
      were deleted. See the design in `docs/plans/windowmanager-unification.md`.
      Remaining: the "Duplicated / drifted toggle policy" item below (Fragility #4).
- [x] **Cross-object window-state coupling** (2026-07-09) — investigated: it is
      *load-bearing*, not a bug. `MainScreenWindowHelper` seeds the comic reader's
      `WindowManager` with the current windowed geometry before the main screen
      goes fullscreen, so a comic opened while the window is already fullscreen can
      still restore the window on a comic→windowed toggle. Renamed the methods to
      `seed_`/`clear_windowed_restore_geometry`, documented the contract at both
      ends, and pinned it with tests. True decoupling (a single shared geometry
      source) is folded into the WindowManager-unification item below.
- [x] **Restore assertions can crash** (2026-07-09) — `restore_saved_size_and_position`
      asserted non-sentinel size/pos; reached without a prior save (app started
      already fullscreen) it raised, and silently restored garbage under `-O`.
      Now guards via `WindowState.is_unsaved()`: skips the geometry restore and
      just finishes the windowed transition. Tested in `test_window_manager.py`.
- [x] **Duplicated / drifted toggle policy** (2026-07-09) — the toggle scaffolding
      (`toggle_screen_mode`, the goto + scheduling logic) is extracted into a shared
      `WindowModeController` (`platform_window_utils.py`); both `MainScreenWindowHelper`
      and `ComicBookReaderScreen` construct one and delegate, keeping only their own
      completion callbacks. The `"Fullscreen"`/`"Windowed"` button label + icon swap is
      centralized in `set_fullscreen_button` (`action_bar_helpers.py`). Note: the
      remaining `"Fullscreen"` literals in the `.kv` files are static initial values;
      `FullscreenEnum` (the geometry-state enum) is a distinct concern, left as-is.
      Covered by `TestWindowModeController` + `TestSetFullscreenButton`.

## Architecture / testability

- [ ] **Architecture deep-dive** — run the `improve-codebase-architecture`
      exploration to find shallow modules to deepen and untested seams to
      surface across the codebase.

---

## Done (recent)

- [x] **Strengthen weak generic type annotations** (2026-07-08, commit 430e04c) —
      all 37 bare `dict`/`list`/`tuple` annotations parameterized; also fixed 3
      latent type issues the stronger types exposed.
- [x] **Search consolidation RFC** — `comic_search.py` facade + `search_ports.py`
      protocols isolating Whoosh; screens migrated; `fake_search.py` test adapter.
- [x] **`barks_fantagraphics` high/medium-impact refactors** — god-module splits,
      panel geometry extraction, `ComicsDatabase` slimming, broad test coverage.
