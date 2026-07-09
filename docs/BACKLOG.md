# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-07-09.

---

## Wiki reader (OKF integration)

The wiki is integrated as a top-level app screen. Remaining polish:

- [ ] **In-wiki search** — find pages within the OKF bundle from the wiki screen.
- [ ] **Escape-back inside the wiki screen** — currently only mouse4 works while
      embedded; the app owns keyboard keys, so Escape doesn't navigate back.
- [ ] **Async panel textures** — load large panel-background images off the UI
      thread to avoid stalls.
- [ ] **Shared kv action-bar extraction** — the main screen, comic reader, and
      wiki screen each define near-identical action bars; extract one shared
      `.kv` bar.

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

- [ ] **Two `WindowManager` instances over one global `Window`** — `MainScreen`
      and `ComicBookReader` each own a `WindowManager` that mutates the single
      global `Window.fullscreen`; correctness relies on only one being active at
      a time, with no cross-checking. Unifying them onto a single shared geometry
      source is also what would let the (now-documented) cross-object seeding
      above go away.
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
- [ ] **Duplicated / drifted toggle policy** — the toggle + finish-callback logic
      is near-duplicated between `MainScreenWindowHelper` and
      `ComicBookReaderScreen` and has already drifted; the mode strings
      (`FullscreenEnum`, `"Fullscreen"`/`"Windowed"`) are repeated in ~3 places.

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
