# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-07-25.

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

## Windows distribution (end-user friction)

> Surfaced by the first tester download (2026-07-21): Defender flagged the
> v1.0.0-alpha.2 exe mid-download as `Program:Win32/Wacapew.C!ml` — the
> classic low-confidence ML false positive on Nuitka onefile binaries. The
> website Troubleshooting tab documents the user-side workaround (Protection
> history → Allow); these are the producer-side fixes.

- [ ] **Submit each release exe to Microsoft as a false positive** —
      https://www.microsoft.com/en-us/wdsi/filesubmission ("Software
      developer"), attaching `barks-reader-win.exe` and citing: Nuitka-compiled
      open-source Python app, repo link. Cleared verdicts ship to all Defender
      users via cloud updates within days. Per-file-hash, so this is a
      **per-release chore** until the exe is code-signed — candidate for a
      step in the README Deployment checklist once it proves routine.
      Optional aid: check/upload the exe on VirusTotal first and cite the
      result in the submission.
- [ ] **Windows code signing** — the real fix, same shape as the macOS item
      below: an OV certificate still has to accrue SmartScreen reputation,
      an EV certificate (a few hundred US$/yr) largely bypasses it
      immediately. Would also unlock signing in CI. Decide alongside the
      macOS signing item if the tester pool grows.

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
- [ ] **Make wide signatures keyword-only** — 49 functions take more than 5
      positional params (PLR0917, surfaced when ruff 0.16.0 stabilized the rule;
      now ignored in `.ruff.toml` alongside PLR0913). The rule's implied fix —
      bundling params into config objects — is the *wrong* one here: the hits are
      overwhelmingly dependency-injection constructors, and many collaborators is
      the pattern we chose. The right fix is a bare `*` in the signature, making
      them keyword-only at zero design cost. Do it incrementally, worst first:
      the 14 signatures with 8+ positional params, i.e. `NavigationCoordinator`
      (10), `show_error_popup` (10), `OKFViewer` (10, okf-reader),
      `MainScreen` (9), `MainScreenWindowHelper` (9),
      `scripts/make_one_pager_mosaic.py` (9). Then fix any positional call sites
      the `*` breaks. Most already pass by keyword (`NavigationCoordinator` is
      all-keyword in both prod and tests), but `MainScreen` is constructed
      positionally with 9 args at `barks_reader_app.py:396` — the concrete
      transposition hazard, and the best place to start.
      Re-list current hits with `uv run ruff check . --select PLR0917`.
- [ ] **GUI acceptance harness + deterministic dev mode** — turn the
      remote keyboard-driving recipe (`.claude/skills/verify/SKILL.md`) into a
      repeatable Claude-in-the-loop smoke layer. Highest-leverage first step:
      pin the app's run-to-run variation (seeded `ImageSelector` RNG, fixed
      window geometry, hermetic config dir, page-settled log signal) — same
      binary, env-gated. Full design discussion:
      `docs/plans/gui-testing-deterministic-mode.md`.

## Testing (property-based & mutation)

> Infra landed: Hypothesis dev/ci settings profiles (root `conftest.py`), the
> first property tests on `story_slug` (`test_wiki_integration.py`), and mutmut
> mutation testing (`scripts/mutmut.sh`, backlog in `docs/mutation-testing.md`).
> Remaining is broadening property-based coverage and burning down the mutmut
> survivors — the two reinforce each other: properties assert *behaviour*, so
> they kill far more mutants than example tests.

- [ ] **Shared Hypothesis strategies** (`tests/strategies.py`) — reusable
      `@st.composite` builders for the domain types so property tests can reach
      past plain strings: `titles()` (`st.sampled_from(list(Titles))`),
      `year_ranges()` (ordered pairs in the Barks span), `fanta_info()` /
      `comic_book_info()` via `st.builds(...)`, page/panel specs, `intspan`
      page ranges. This is the main investment; everything below draws on it.
- [ ] **Round-trip property tests** — the easy, high-value wins after strategies
      exist: `hyphen_break_engine` (`build_markup(parse_marked_text(x))` round-
      trips; joining hyphenated parts reconstructs the word), the year-range
      `get_range_str` format/parse round-trip, `reader_formatter`, comic-layout
      math, `cpi_calculator` (monotonic/bounded inflation).
- [ ] **Stateful testing pilot** — a Hypothesis `RuleBasedStateMachine` that
      generates *sequences* of operations and checks invariants after each.
      Start with `reading_history` / `last_read_page_tracker` ("current page
      always in bounds", "no visited entry lost"), then `NavigationModel`
      ("every reachable destination resolves to a valid ViewState") and
      `reader_settings` / `json_settings_manager` (save→load round-trip).
- [ ] **Burn down the mutmut survivor backlog** — started at ~1523 survivors +
      436 no-test mutants (`docs/mutation-testing.md`). Triage with `mutmut show`,
      ignore the low-value ones (log/error strings), harden the assertions that
      matter — property tests above are the main lever. **Treat 1523 as an upper
      bound**: any module using `functools.cache` reports false survivors (see
      below), and both passes so far showed the real number is lower.
      Done so far, all triaged down to equivalents-only:
      - **Pure-logic pass** (2026-07-26, two rounds): `collection_page_groups`
        (53→0), `reader_utils` (50→4), `filtered_title_lists` (22→1),
        `hyphen_break_engine` (19→6), `reader_formatter` (56→9) — **200→20**.
      - **Big-cluster pass** (2026-07-26): `navigation.tree_spec` (184→1),
        `system_file_paths` (131→41), `comic_book_loader_platform_settings`
        (110→26), `image_selector` (104→35), `fantagraphics_volumes` (69→14) —
        **598→117** over 1851 mutants (93.6% of checked mutants killed). Of the
        117, 40 are one equivalence class in `system_file_paths.__init__` and 23
        are log wording; the rest are itemised as equivalents in the doc.
      - **Plumbing pass** (2026-07-26): `reader_settings` (41→6),
        `archive_page_image_source` (59→11), `screen_metrics` (27→8),
        `comic_reader_manager` (22→9), `reading_history` (17→10),
        `reader_file_paths` (37→21) — those six are **done** (203→65, the usual
        equivalents-and-log-wording floor). `comic_book_loader` (184→155) and
        `view_pipeline` (148→112) were only **partially** burned down.
      - **Never-swept pass** (2026-07-26): `platform_info` (45→3) and
        `wiki_integration` (44→10) — the two largest modules no round had
        touched, both now **done** with all 13 remaining triaged as equivalent.
        `platform_info`'s 45 were **entirely fake**: its tests used
        `patch.dict(os.environ, ..., clear=True)`, which strips mutmut's own
        `MUTANT_UNDER_TEST` so the trampoline always ran the original body —
        and also killed the pre-flight check, aborting any run scoped to that
        module. Recorded as trap 3 in the doc; **check it before believing any
        survivor count from a module whose tests touch `os.environ`.**
      - **Small-module tail pass** (2026-07-26): the last 17 backlog modules
        swept together — **99→28** over 1129 mutants (97.1% of checked mutants
        killed). Nine went to zero (`user_error_messages`,
        `reader_file_paths_resolver`, `image_pipeline`,
        `special_overrides_handler`, `reader_palette`, `config_info`,
        `comic_book_info`, `settings_notifier`, `navigation.navigation_model`);
        all 28 remaining are triaged in the doc. **This finishes the backlog
        table** — no module on it is unswept. Two source fixes came out of it: a
        `dedent` that silently did nothing once the interpolated path wrapped (so
        long Fantagraphics directories rendered every dialog line indented), and
        a dead `SettingsNotifier._on_change` field. The transferable trap:
        `pytest.raises(match=...)` is a *search*, so mutmut's `XX…XX` string
        mutants pass tests that look like exact matches — anchor with `^…$`.
      **Remaining work is `comic_book_loader` and `view_pipeline`** — 267
      survivors, only ~77 of them log wording, so most are real gaps. They were
      left partial for structural reasons, not effort: `comic_book_loader`'s two
      big clusters are a prefetch loop and its error handling on a worker thread,
      which need a deterministic executor harness (scripted `ThreadPoolExecutor`,
      stop flag, future-completion order) rather than better assertions;
      `view_pipeline`'s remainder is spread across ~20 small image-selection
      methods each needing its own per-view-state case. The five patterns that do
      the work when there *is* a lever — structural snapshots (including of
      constructed initial state), exact tables for literal tables, scripted clocks
      for benchmarks, and `assert_called_once_with` wherever the return value is a
      mock — are written up in the doc.

> Gotchas when writing more property tests: `@given` doesn't compose with
> function-scoped pytest fixtures (build inputs in-test or via `st.data()`);
> slow tests need `@settings(deadline=None)`; keep property tests in the
> Kivy-free `core` / `barks_fantagraphics` layer (same reason mutmut avoids the
> UI). **Keep `@given` tests at module level, never as test-class methods** — a
> class-scoped one trips Hypothesis's `differing_executors` health check under
> mutmut and aborts the entire mutation run.
>
> Gotcha when reading mutmut output: `functools.cache` makes mutants look like
> survivors (the memoised value outlives the mutant that produced it), so any
> test covering a cached entry point needs a `cache_clear()` autouse fixture
> before its survivor count means anything.

---

## Done (recent)

- [x] **Strengthen weak generic type annotations** (2026-07-08, commit 430e04c) —
      all 37 bare `dict`/`list`/`tuple` annotations parameterized; also fixed 3
      latent type issues the stronger types exposed.
- [x] **Search consolidation RFC** — `comic_search.py` facade + `search_ports.py`
      protocols isolating Whoosh; screens migrated; `fake_search.py` test adapter.
- [x] **`barks_fantagraphics` high/medium-impact refactors** — god-module splits,
      panel geometry extraction, `ComicsDatabase` slimming, broad test coverage.
