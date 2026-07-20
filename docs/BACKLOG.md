# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-07-20.

---

## Wiki reader (OKF integration)

The wiki is integrated as a top-level app screen. Remaining polish:

- [x] **In-wiki search** (commits 1540f77, ad28850, 1ac48bf) — wiki page search
      (title + heading) in the OKF reader, with result-list persistence and
      index-build failure recovery (`okf_reader/core/search.py`).
- [x] **Escape-back inside the wiki screen** (commits fe1d7bc, 601dcb4) —
      `WikiReaderScreen._on_key_down` routes window keys to the viewer and falls
      through to back handling: Escape (and the user-configured alternate
      Escape) backs out of an active search, then navigates back, and at the
      history root exits to the Barks Reader; Alt+Left backs too. Pinned by the
      escape/go-back tests in `test_wiki_reader.py`.
- [ ] **Async panel textures** — still open (checked 2026-07-20): the wiki
      reuses the app's image *selection* (`BarksPanelsImageProvider` wraps
      `ImageSelector`) but not its async *loading* — `PanelTextureLoader`
      serves five barks screens while `OKFViewer._update_background` runs
      fully on the UI thread, worst on encrypted zips (decrypt + PIL decode +
      PNG re-encode in `background_for`, then CoreImage decodes it *again*).
      Blocker is the synchronous okf `ImageProvider` contract (okf-reader
      can't import barks code): the viewer needs an async-friendly background
      API (texture-via-callback), after which the app-side provider can go
      off-thread via `PanelImageLoader` and drop the double decode.
      **Priority: low** — no perceptible lag on the dev machine (Greg,
      2026-07-20); a latent hazard for slower disks/CPUs, not a felt problem.
      Revisit only if a real stall is observed.
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
- [x] **Double-press toggle resolves both presses the same way** (2026-07-20) —
      fixed via the scoped in-flight target-mode tracking: `WindowManager`
      records each transition's heading (`_begin_transition`/`_end_transition`,
      sequence-guarded so an older overlapped transition can't erase a newer
      command's target) and exposes `is_fullscreen_target()`; `toggle()` reads
      that instead of `is_fullscreen_now()`, and the `goto_*` guards use it too
      (a duplicate same-direction command defers its finish callback behind the
      pending flip rather than starting a second transition). Race pinned by
      `TestDoublePressToggle` in `test_window_manager.py` with a queued fake
      Clock modelling the one-frame flip delay.
- [x] **Stale backend restore still resizes the window** (2026-07-21) —
      `WindowBackend.schedule_restore` now returns a cancel handle (both
      backends; Win32's covers whichever of its two stages is pending), and
      `goto_fullscreen_mode` cancels every scheduled restore it supersedes,
      retiring their transitions so no phantom pending-restore blocks later
      geometry saves. A windowed transition the fullscreen command outruns
      *before* backend scheduling retires itself via an `is_fullscreen_target`
      check in `restore_saved_size_and_position` (which also stops the
      no-saved-state branch firing windowed callbacks at a fullscreen window).
      `_finish_restore`'s fullscreen guard stays as belt-and-braces for an
      event that fired before its cancel landed. Covered in
      `TestInterleavedTransitions`.

## macOS distribution (end-user friction — investigation)

> Surfaced by the Nuitka migration (2026-07-14). The macOS build ships a zipped
> `.app` (Nuitka `--mode=app`; onefile is impossible with pyobjc in the tree,
> and the bundle is correct for a GUI app anyway). The current install flow
> mirrors the Linux one — `.app` in its own folder, data zips beside it,
> Gatekeeper "Open Anyway" — which works but is un-Mac-like. See the
> "Installing the Standalone App on macOS" section of README.md for what users
> currently endure. Priority order if smoothing this for strangers:

- [ ] **Code-signing + notarization** — the single biggest friction remover:
      kills the Gatekeeper "Open Anyway"/`xattr` step. Needs an Apple Developer
      ID (~US$99/yr) plus `codesign` + `notarytool` steps in `scripts/build.sh`
      / CI. Independent of everything else.
- [ ] **Mac-native data locations + prompting installer** — anchor compiled-mode
      config/data in `~/Library/Application Support/barks-reader` instead of
      beside the `.app` (macOS branch of `get_app_exe_dir()` /
      `ConfigInfo._get_user_app_config_dir`), and have the first-run installer
      *prompt* for the data zips (or check `~/Downloads`) rather than requiring
      them pre-placed. Lets the `.app` live in `/Applications` like a normal
      app. The only item that touches app code; keep Linux/Windows behavior
      unchanged.
- [ ] **DMG packaging** — `hdiutil` in build.sh to produce the familiar
      drag-to-Applications disk image instead of a bare zip. Cosmetic; a few
      lines in CI; lowest priority.

## Architecture / testability

- [ ] **Architecture deep-dive** — run the `improve-codebase-architecture`
      exploration to find shallow modules to deepen and untested seams to
      surface across the codebase.
- [ ] **GUI acceptance harness + deterministic dev mode** — turn the
      remote keyboard-driving recipe (`.claude/skills/verify/SKILL.md`) into a
      repeatable Claude-in-the-loop smoke layer. Highest-leverage first step:
      pin the app's run-to-run variation (seeded `ImageSelector` RNG, fixed
      window geometry, hermetic config dir, page-settled log signal) — same
      binary, env-gated. Full design discussion:
      `docs/plans/gui-testing-deterministic-mode.md`.

---

## Done (recent)

- [x] **Strengthen weak generic type annotations** (2026-07-08, commit 430e04c) —
      all 37 bare `dict`/`list`/`tuple` annotations parameterized; also fixed 3
      latent type issues the stronger types exposed.
- [x] **Search consolidation RFC** — `comic_search.py` facade + `search_ports.py`
      protocols isolating Whoosh; screens migrated; `fake_search.py` test adapter.
- [x] **`barks_fantagraphics` high/medium-impact refactors** — god-module splits,
      panel geometry extraction, `ComicsDatabase` slimming, broad test coverage.
