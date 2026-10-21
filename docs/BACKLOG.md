# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-10-16.

**Other to-do lists** (counts as of 2026-10-13; each list is the source of truth):

- `docs/pyrefly-annotation-debt.md` — 15 open: type findings grandfathered in
  `pyrefly-baseline.json`, fixed when you are in the file.
- `docs/design-review-2026-07.md`, "Still open" — 4 design leftovers: the wiki's fixed
  focus colours, colours that are not theme roles, the tree view's caption contrast, the
  Material glyphs not yet redrawn.
- `docs/mutation-equivalents.toml`, `[[untriaged]]` — 105 entries: mutation survivors each
  needing a test or a reason it is harmless (`docs/mutation-testing.md`).
- `src/barks-fantagraphics/data/fixes-todo.txt` — about 155 page-image fixes (indicia,
  lettering glitches, colour), made in the image pipeline, not in this app.

---

## Search

Advanced word and tag search landed 2026-09-29/30 (typed queries, word forms, wildcards,
suggestions, picked words and tags, era and tag filters; `docs/plans/advanced-search.md`).
Found along the way, not yet done:

- [x] **The clear button by remote** — in Word and Tag search, once the list had chips, no
      arrow key reached the × beside the box, and clearing is also how the picked words/tags
      and the era are reset. Now Right at the end of the box's text is the ×, in every mode
      (Right again, the results).
- [x] **Narrow tag panel** — in the app's tall desktop window (the GUI tests' too) the + beside
      each tag chip made 44 of the 220 tag names wrap, up from 24. The tag list's column is now
      40% of the panel (35% in the other modes): 22 wrap. At 1920x1080 and 4K none wraps either
      way. Trimming the count margin instead was measured too, but a 3-digit count would then
      touch the name.
- [x] **Typed tags with years** — typed tags take `year:` and `vol:` ranges too
      (`scrooge + gyro year:1950-55 vol:7`); each shows as a chip in the picked-tags row
      ("years 1950-55", "vol 7") that Enter takes out, and narrows the stories along with
      the era row.
- [x] **Word-query speed** — an AND's later parts search only the stories found so far,
      and Whoosh built that filter from an OR of title terms by walking it document by
      document: `duck money` took ~1s. The engine now reads each title's documents from its
      postings, once, and filters by that set: `duck money` 66ms, `gold mine` 32ms, a
      four-part query ~130-180ms (the rest is reading the bubbles found). Guarded by
      `tests/benchmarks/test_find_bubbles_benchmark.py` (50ms budget; ~21ms now).

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

- [ ] **Regenerate unauthored dates** — ~31 `_TODO = (0, 0, 0)` placeholder
      entries in `comic_book_info.py` mark stories with unknown authored dates
      (107 before the 2026-07-17 INDUCKS backfill, `b1dde680`).
      Regenerate from the bibliography source (`experiments/bibliography/`).
- [ ] **Reconcile date discrepancies** — 14 dates flagged as differing from
      Barrier's bibliography (27 when `barks_bibliography.py` was generated;
      listed in `experiments/bibliography/PLAN-one-to-one.md`).
- [x] **Tag data validation** — the last `NEED TO CHECK THESE` marker in
      `barks_tags_data.py` went with the Gyro split (`579da591`, 2026-10-08).

## Speakers (cross-repo follow-ups in `../barks-ocr`)

The reader now carries the vision pass's speaker call (`SpeechText.speaker`,
`speech_speakers.py`, a `speaker` field + `speakers.json` sidecar in the Whoosh
index) and shows it on bubbles and as a word-search filter. What is left lives
in the OCR repo, which is read-only from here:

- [x] **Rebuild the shipped Whoosh index** (2026-09-19, `barks-ocr-whoosh-index
      main --volume 1-27 --ocr-index 1 --skip-missing-pages`): the index now
      carries the `speaker` field and `speakers.json`; the word-search GUI
      tests' row coordinate moved down 95px for the speaker chip stack.
      Skipped for having no prelim OCR at all: *Camp Counselor* (vol 9,
      pages 110-117), *Donald's Grandma Duck* (vol 9, 096-109), *Letter to
      Santa* page 078, *The Mines of King Solomon* page 035.
- [ ] **OCR the four gaps above** so they can join the index.
- [x] **`FRAGMENTS_TO_SUPPRESS` drift** -- `castoria`, `treatem` and
      `swelldorf` no longer occurred in the index (only `swelldorf-castoria` does),
      so barks-ocr's `--do-checks` failed before reaching the newer checks. Pruned
      2026-10-13. The list lives in this repo (`barks_fantagraphics/whoosh_barks_terms.py`);
      barks-ocr only imports it. Against the shipped index (2026-09-19) the fragment
      check now passes, and the run goes on to the next item's failure.
- [ ] **More term-list drift** -- the same run: `check_all_caps` fails on `u-235`, and
      `check_barksian_terms` logs `Treatem Nyce` as not found (it logs rather than
      fails). Neither is in the index as a term; find how the story spells them
      (a tokenizer split, or OCR text) before choosing between fixing the list and
      fixing the index. Also in `whoosh_barks_terms.py`.
- [x] **`vision_schema.py` imports the vocabulary** (barks-ocr `c79f181`) (roster, sentinels,
      `other:` prefix, key names, cap-colour and identified-by options) from
      `barks_fantagraphics.speech_speakers` instead of defining its own copy.
- [x] **`tools/speech_script.py` reads `speech.speaker`** (barks-ocr `396b383`) and drops its
      raw-JSON workaround for the speaker.
- [ ] **Filter on `other:` speakers** — the long tail (1,000+ values) is not
      offered as chips; the top N by count could be.

## Naming consistency (cross-repo — deferred)

> ⚠️ **Not low-risk.** These names are public API consumed by the sibling repos
> `../barks-ocr` and `../barks-comic-building` (~36 files). A rename is a
> coordinated, breaking, 3-repo change — do it deliberately, all at once, not
> piecemeal.

- [ ] **`srce` → `source`** — about 1,200 in-repo occurrences, baked into public
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

## Title view layout

- [ ] **Title over the info lines on a narrow, tall window** — seen 2026-10-11 while
      checking the goto-page row (4f640223): at 700x1300 on the nested probe display,
      the story title (`main_title_label`) is drawn over the "1st Issue / Submitted /
      Payslip / Source" lines (`title_info_label`), for both Lost in the Andes! and The
      Firebug. At 900x1300 and 900x1000 they do not touch. The font sizes are chosen by
      window height alone (`font_manager.update_font_sizes`: the large group above
      1090 px), not width, so a narrow window over that height gets the large fonts in
      too little width; that is the likely cause, not yet confirmed. To reproduce: boot
      the probe with `BARKS_PROBE_SCREEN=700x1300` onto any story. No GUI test runs that
      size.

## Architecture / testability

- [ ] **Architecture deep-dive** — run the `improve-codebase-architecture`
      exploration to find shallow modules to deepen and untested seams to
      surface across the codebase.
- [ ] **Make wide signatures keyword-only** — 62 functions take more than 5
      positional params (PLR0917, surfaced when ruff 0.16.0 stabilized the rule;
      now ignored in `.ruff.toml` alongside PLR0913). The rule's implied fix —
      bundling params into config objects — is the *wrong* one here: the hits are
      overwhelmingly dependency-injection constructors, and many collaborators is
      the pattern we chose. The right fix is a bare `*` in the signature, making
      them keyword-only at zero design cost. Do it incrementally, worst first:
      the 15 signatures with 8+ positional params, i.e. `NavigationCoordinator`
      (10), `show_error_popup` (10), `OKFViewer` (10, okf-reader),
      `MainScreen` (9), `MainScreenWindowHelper` (9),
      `scripts/make_one_pager_mosaic.py` (9). Then fix any positional call sites
      the `*` breaks. Most already pass by keyword (`NavigationCoordinator` is
      all-keyword in both prod and tests), but `MainScreen` is constructed
      positionally with 9 args at `barks_reader_app.py:406` — the concrete
      transposition hazard, and the best place to start.
      Re-list current hits with `uv run ruff check . --select PLR0917`.
- [x] **GUI acceptance harness + deterministic dev mode** — built 2026-09-15 as
      the GUI suite (`tests/gui/`, `scripts/gui_driver.py`, `run_gui_tests.sh`):
      seeded RNG (`BARKS_READER_RANDOM_SEED`), a pinned nested screen, a scratch
      profile per test and the app's log markers as the oracle; only the
      in-process autopilot rung was dropped as unneeded. Plan and what was built:
      `docs/plans/gui-testing-deterministic-mode.md`.

## Testing (property-based & mutation)

> Infra landed: Hypothesis dev/ci settings profiles (root `conftest.py`), a
> `test_properties.py` in each of the reader (comic layout, saved page, year ranges,
> hyphen engine, log markers, the Kivy escapers, the Statistics and history JSON,
> the goto offer, image history, the search baskets, scroll reveal, index text),
> barks-fantagraphics (speech markup, tag queries, alpha split, panel geometry, the
> tokenizer) and comic-utils (panel reading order, inflation) packages, as of
> 2026-10-21, plus `test_wiki_integration.py` (`story_slug`) and
> `test_search_query.py`, and mutmut mutation testing (`scripts/mutmut.sh`,
> backlog in `docs/mutation-testing.md`).
> Every item below is done (2026-10-21); what remains is keeping the properties
> and the mutmut survivors moving together: properties assert *behaviour*, so
> they kill far more mutants than example tests.

- [x] **GUI and window coverage on Windows and macOS** — the GUI suite was X11-only and
      the Win32 window code tested only with mocks, so the window-shrink class was
      invisible where most of that code runs. Four steps, each useful alone, all done
      2026-09-23: geometry markers, real Win32 calls in Windows CI, the GUI suite on the
      Windows VM with real `SendInput` injection, and a data-pack-free key-and-window
      check on every CI build leg (macOS's only regular coverage). Plan and what remains:
      `docs/plans/cross-platform-gui-tests.md`. The GUI suite on macOS (a `gui_probe.py`
      backend, run on the VirtualBox guest with software OpenGL; whole suite clean
      2026-10-01, a real Mac untried): `docs/plans/macos-gui-tests.md`.

- [x] **Shared Hypothesis strategies** — **DONE (2026-10-21)**:
      `src/barks-reader/tests/unit/strategies.py`, reached through the unit tests'
      `conftest.py` putting their directory on `sys.path`: `titles()`,
      `comic_titles()`, `article_titles()`, `fanta_infos()` (the real table), `tags()`,
      `tag_groups()`, `tag_categories()`, `year_ranges()` (ordered pairs in the Barks
      span), `page_maps()` (the one copy; `test_properties.py` and the tracker machine
      draw on it) and `destinations()`, one of every `Destination` kind.
      `test_navigation_properties.py` fails when a kind is added and not built there.
      Not done, nothing needs them yet: `comic_book_info()` and `intspan` page ranges.
- [ ] **Round-trip property tests** — the easy, high-value wins after strategies
      exist. Done in `test_properties.py`: `hyphen_break_engine` (markup with no
      hyphens unchanged; gaps are exactly the breaks), comic-layout math and the
      saved page's JSON; and since 2026-10-21 `reader_formatter` (the three escapers
      agree), `cpi_calculator` (there and back, monotonic), `statistics_series` and
      `reading_history` (their JSON), `tag_query` (described then parsed) and
      `speech_markup` (escape, spans). The year-range `get_range_str` has no parser
      to round-trip against; nothing is left here.
- [ ] **Stateful testing pilot** — a Hypothesis `RuleBasedStateMachine` that
      generates *sequences* of operations and checks invariants after each.
      Done for `reading_history` (2026-10-21): `test_reading_history_stateful.py`, a
      `RuleBasedStateMachine` over the tracker, the store and its file, run from a
      module-level function by `run_state_machine_as_test` (the generated `TestCase`
      is class-scoped, the mutmut trap below; three `pytest.main` runs in one process
      pass). The same for `last_read_page_tracker` (2026-10-21):
      `test_last_read_page_tracker_stateful.py`, comics opened on drawn layouts and
      closed on drawn pages in either page mode, the page saved always one of the
      layout's and in the pair shown, offered back normalised, on disk as saved.
      `image_history` has a generated operation list in `test_properties.py`.
      `NavigationModel` turned out stateless (four static methods), so it got
      properties instead (2026-10-21): `test_navigation_properties.py`, every
      destination resolving to a view state, the tag context the request carries, a
      year range in the one field its kind uses, auto-select and the kept top view.
      `reader_settings` / `json_settings_manager` (2026-10-21):
      `test_settings_properties.py`, a value of every field's kind written as the
      panel writes it reading back typed, here and through the ini file, the three
      setters too; and the JSON store as a machine, pages per title, the selected
      node with its state (the History path migrating), the sizes warned about, a
      manager loaded from the file answering as the live one. Nothing is left here.
- [x] **Burn down the mutmut survivor backlog** — **DONE (2026-07-26)**: ~1523 →
      363 survivors across all 37 modules, every remainder triaged as not worth
      killing (log/message wording, recorded equivalents, dead code, and
      `comic_book_loader`'s timing-only scheduling mutants). No known killable gap
      is left in `core/`. Ten modules are at zero. Full write-up, per-pass tables and
      equivalence tables in `docs/mutation-testing.md`.
      **The 363 was derived** — a sum of seven separately-scoped runs, not one
      measurement; the full sweep below measured 361. The no-test mutants (436 then)
      are untouched by this and are the GUI suite's ground (`BARKS_PROBE_COVERAGE`).
      Five real bugs came out of it: a `dedent` that silently did nothing once the
      interpolated path wrapped, a dead `SettingsNotifier._on_change` field, an
      unreachable `story_page_title` branch, and two swallowed-error bugs in
      `comic_book_loader` (archive-open errors escaping the loader thread, and the
      *unexpected* `IndexError` never reported).
      The passes, all triaged down to equivalents-only:
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
      - **`view_pipeline` pass** (2026-07-26): **111→23** over 429 mutants
        (94.6% of checked mutants killed) — **done**, all 23 triaged (20 log
        wording, 2 `__init__` values overwritten within `__init__`, 1 argument
        that duplicates the dataclass default). The plumbing pass called this one
        "spread thin across ~20 methods with no single lever"; the shape was right
        but the lever existed. All those methods hang off **one ordered
        `(predicate, handler)` dispatch**, and an ordered dispatch is invisible to
        per-handler tests: flip a predicate's `==` to `!=` and an earlier entry
        matches instead, so the handler still runs and every existing test still
        passes. Stubbing each image source to a distinguishable filename and
        comparing all 47 `ViewStates` against a literal state→image table killed 30
        at once. **Generalise: when control flow is an ordered table, test the
        table, not its rows.** No source changes were needed, but it found several
        untested behaviours — the whole covers→"All Covers" redirect, the
        `ON_HISTORY_NODE` visibility flag, both of `render`'s flags
        (`preserve_top_view`, `force_fresh_fun_image`), and the search screen's
        anti-repeat reroll loop.
      - **`comic_book_loader` pass** (2026-07-26): **156→97** over 407 mutants
        (75.8% of checked mutants killed) — **done**, all 97 triaged. The lowest
        score of any finished module, and honestly so: **78 of the 97 are log or
        exception-message wording**, because this module narrates a whole background
        load. Of the rest, 14 are prefetch-scheduling mutants that are *timing-only*
        — the shared `load_iter` resumes where it left off and `submitted` enforces
        exactly-once, so `continue`→`break` costs one submission slot for one round
        and self-heals; pinning them would mean asserting a thread schedule. **Two
        real bugs came out of it, both "the error never reaches the user":**
        `image_source.open()` sat outside the guarded block, so a missing or
        truncated volume raised straight out of the loader thread — no
        `on_load_error`, no dialog, just a comic stuck loading; and the `IndexError`
        handler set `load_error` only in its `else`, so the *unexpected* index error
        (the one worth surfacing) was logged and silently swallowed. The second was
        found by a new test failing against the first fix. Also extracted
        `_retained_image_stats()` out of the `[mem]` log line, taking that cluster
        15→1 without pinning any wording.
      **The mutmut backlog is finished.** Every module has been swept and every
      remaining survivor triaged. Worth noting for future rounds: *neither* of the
      two modules predicted to "need a test-harness build" actually did.
      `view_pipeline`'s lever was its ordered dispatch and `comic_book_loader`'s was
      its untested error matrix; in both cases the predicted blocker (threading,
      scheduling) turned out to be the part that genuinely cannot be asserted
      without brittleness, while the real gaps sat in plain sequential code beside
      it. The patterns that do the work — structural snapshots (of constructed
      initial state and of an ordered dispatch), exact tables for literal tables,
      scripted clocks for benchmarks, error matrices parametrised over
      exception × state, moving arithmetic out of log lines, and
      `assert_called_once_with` wherever the return value is a mock — are written up
      in the doc.
- [x] **Run a full `core/` mutmut sweep** — **DONE**: the overnight mutation stage
      has mutated all of `core/` every night since 2026-10-07 (`run_overnight.sh`,
      `mutation_core`, a fresh `mutants/` each run). The 2026-10-13 run measured
      6995 mutants in 6m30s: 6464 killed, 361 survived, 166 with no covering test,
      4 timeouts, so ≈94.7% of checked mutants killed against the ~94% the derived
      363 predicted: the burn-down held. Of the 361, 249 are equivalent and 112
      untriaged (`docs/mutation-equivalents.toml`). The outcome and per-module
      survivor tables are in `docs/mutation-testing.md`, "Where things stand".

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

## GUI suite on other platforms (open items from `docs/plans/`)

> The plans under `docs/plans/` are done (2026-10-16); these are the items they left
> open, gathered here so one list holds them. Each names the plan with the detail.

- [ ] **Touch on Windows** (`touch-gui-tests.md`) — the Windows probe's `tap` clicks
      and refuses `BARKS_PROBE_TOUCH`. Wanted: `InitializeTouchInjection` /
      `InjectTouchInput` behind it, after the tap tests have run on the Windows
      touchscreen laptop by click. A Windows touch also reaches Kivy as a touch
      (`wm_touch`), not only as a pointer press, so it can double a tap there.
- [ ] **A real Mac** (`macos-gui-tests.md`, "Open questions") — the VirtualBox guest
      proves the harness on software OpenGL only. Untried: GPU drawing without
      `with-soft-gl.sh`, and a Retina display's points against pixels in the probe's
      `client_geometry`. Also not yet: CI's macOS app in `run_overnight_desktop.py`
      (`fetch-build` and `built-app` skip on the guest, which has no GPU driver).
- [ ] **The wiki round trip test leans on the wiki copy's layout**
      (`macos-gui-tests.md`, milestone B) — the sidebar stays on the last page while
      the home page shows, so each round's two Downs walk to a new page and can open a
      branch, whose rows then count. Undecided: an `okf-reader` viewer bug (the
      sidebar should follow the page shown), or the test should go to the same page
      each round. It passes today because the current copy meets no branch in six
      rounds.
- [ ] **The wiki viewer's cost per row of a linked table** (`windows-overnight.md`,
      "Open") — about 1 GB per 1,000-1,700 rows (`cbl-contents`, `bibliography`);
      62a3dd08 made tables without links lazy. The linked tables' per-row cost is what
      is left, and it sets the soak's 6 GB ceiling.
- [ ] **A free-memory guard mid-run, maybe** (`windows-overnight.md`, "Open") — the
      desktop runner has a 6 GB free-at-start check and holds the app to a fixed 6 GB
      ceiling. Whether to also stop the app when the machine's free memory drops below
      a reserve (2.5-4 GB) is to be decided from the soak's peak on a full run started
      by hand, outside Claude Code.
- [ ] **The full settings matrix overnight on Windows** (`windows-overnight.md`,
      "Later") — beyond the one variant a night the desktop runner takes.
- [ ] **Kivy 3.0: recheck the fullscreen frame step on Windows**
      (`cross-platform-gui-tests.md`, "What is left" 3; SDL3, expected January 2027) —
      run `--keep-logs -k fullscreen` and read the first "Main window resize event"
      after "Exiting fullscreen mode". At the saved size, delete `move_now` (the Win32
      backend's, the Kivy backend's no-op and its call in
      `WindowManager.goto_windowed_mode`); still 16x39 bigger, keep it.

---

## Done (recent)

- [x] **Strengthen weak generic type annotations** (2026-07-08, commit 430e04c) —
      all 37 bare `dict`/`list`/`tuple` annotations parameterized; also fixed 3
      latent type issues the stronger types exposed.
- [x] **Search consolidation RFC** — `comic_search.py` facade + `search_ports.py`
      protocols isolating Whoosh; screens migrated; `fake_search.py` test adapter.
- [x] **`barks_fantagraphics` high/medium-impact refactors** — god-module splits,
      panel geometry extraction, `ComicsDatabase` slimming, broad test coverage.
