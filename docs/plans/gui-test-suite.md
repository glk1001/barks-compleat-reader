# Plan: a comprehensive GUI path test suite for the Barks Reader

> Status: **approved 2026-09-15**, in progress; each milestone is committed green on
> its own. Saved here so the plan survives across machines and sessions.
>
> - M0 harness: DONE (526d1f6). The helper package is `barks_gui/`, not `screens/`.
> - M1 strong-oracle families: DONE (33 GUI tests, 7m37s). Deviations from the matrix:
>   A7 (top goto arrow) and E3 (tag group) deferred to M3; I6 (Word dropdown) landed
>   early inside the statistics test; the overrides-row test boots with
>   `use_prebuilt_comics=0` because the row is hidden for prebuilt comics; the window
>   is 782x1225 (the recorder rounds to 1224 for the encoder). Found and fixed one app
>   bug on the way: Escape never reached the fun view's options menu (0feb4d4).
> - M2 app markers: DONE. Every marker in the list below landed with a unit test
>   (`loguru_sink` fixture in the unit conftest; `okf_reader.ui.trace` logs through
>   Kivy's logger, tested with a logging handler). One deviation: the About box logs
>   only its opening, since `show_standalone_popup` returns nothing to bind a dismiss
>   to. `Driver.wait_title_fade()` replaces the 4.5s holds in the recorder and the
>   search test. Full GUI run on the marker build: 33 passed.
> - M3 blocked families: DONE. 56 GUI tests, 12m46s, all green; `test_gui_paths.py`
>   migrated and deleted. Deviations: E3 (tag group in the main index) dropped for
>   want of a stable target; the wiki-node test does not assert the landing page,
>   because the node resumes the page saved in the wiki session file; the intro
>   document has one page, so the censorship document carries the page-turn test.
>   Learned: wait patterns are regexes, so a log line with parentheses must be
>   `re.escape`d; gate on `Screen '<name>' entered.` before sending keys to a screen
>   that just opened, or a fast Escape closes it mid-transition; the search box swallows
>   every key but Return and Escape, so Return (not Down) leaves it for the results.
> - M4 docs: DONE. All milestones complete.
> - Afterwards (2026-09-16): headless mode on Xvfb (`--headless`), parallel workers
>   (one probe run directory per display; pytest worker gw<k> gets display :2+k), and a
>   pacing study. Headless four-way: 56 tests in ~3m08s; visible serial at the same
>   pacing: 10m29s (was 12m46s). Key gap 0.15s / settle 500ms adopted; 0.05s/300ms flaked
>   and gained nothing. Kivy DropDowns eat an Escape until their deferred dismissal
>   runs, hence `DROPDOWN_DISMISS_PAUSE` after every dropdown pick.
> - Later that day: a fade superseded by the next title's fade never logs a finish,
>   so `wait_title_fade` watches only the latest fade; every read-portal press now waits
>   for the fade and confirms "entered nav focus at portal" before pressing again. The
>   wiki viewer opens its home page when there is no session (a fresh profile showed an
>   empty pane). One unexplained flake remains on file: after the word-search bubble
>   goto, a Return was once swallowed under four-way load and could not be reproduced
> - Later still (2026-09-16): every fixed `hold()` pause in the suite went. The app now
>   logs each keyboard focus move (`Nav focus on <widget>`, from `draw_focus_highlight`,
>   with the wiki's `OKFViewer: Focus ring on` / `Sidebar focus on` counterparts), every
>   dropdown dismissal (`Dropdown dismissed.`), the confirm popup closing, the search box
>   taking the keyboard, the goto-page row toggling, and Up on the first node when the
>   top arrow is inactive. `Driver.move_focus` steps and waits on those; the harness
>   builds `Driver(paced=False)`, and the camera gaps apply only to the recorder's paced
>   driver. `DROPDOWN_DISMISS_PAUSE` is gone. Headless four-way: 56 tests in ~2m50s over
>   three consecutive green runs (was ~3m10s); wall time is bound by boot and teardown.
>   by hand; the probe now timestamps every injected key (`input.log`, collected with
>   failure artifacts) and the main screen logs a key it yields to a focused text
>   field, so the next occurrence will say where the key went.

## Context

The demo recorder's driver was lifted into `scripts/gui_driver.py` and a three-test GUI
suite now lives at `src/barks-reader/tests/gui/` (commit 2881929). It proved the model:
drive the real app on a nested Xephyr display by injected keys, wait only on lines the app
logs, one boot per test, and a boot costs a few seconds (three tests ran in 84s). The user
asked for a plan to grow that into a comprehensive suite covering most GUI paths.

Exploration found the app's surface is five top-level screens (main, comic reader,
document reader, wiki reader, corpus stats), nine bottom-pane views (title view, fun view,
main/speech/names/locations indexes, statistics, history, search), a six-branch tree, and a
handful of popups. The tree, reader, search and index screens already log a once-per-action
line for nearly every transition. The wiki viewer (`okf_reader`), history tabs, all popups,
settings close, the double-page toggle and the title-view fade end log nothing.

Decisions already made by the user (2026-09-15):
- Add log-line markers in **both** barks-reader and okf-reader for the blind spots.
- Isolate state with a **scratch config directory per session** pointed at by
  `BARKS_READER_CONFIG_DIR`; never touch the live profile.
- Capture **screenshots on failure plus opt-in named checkpoints**.
- Include **fullscreen tests as a separate family**.

Design principles inherited from `docs/plans/gui-testing-deterministic-mode.md`: same
binary, no test build; every pin unset means today's behaviour; no retries, a flaky test is
a defect in its oracle.

## Verified facts that shape the design

- `main.py:53` calls `load_dotenv(".env.runtime")` with the default `override=False`, and
  `config_info.py:172` reads `os.environ["BARKS_READER_CONFIG_DIR"]` directly, so an
  exported variable wins. `gui-probe.sh` inherits the env into `uv run main.py`, but its
  own `config_file()` (`scripts/gui-probe.sh:73-78`) only greps `.env.runtime` and must
  learn the env-var precedence.
- Window geometry is already deterministic on Xephyr when `main_window_height=0` in the
  ini: `main.py` falls through to screen metrics of the nested 900x1300 display and the
  geometry helper only resizes on monitor change. No fixed-geometry env var is needed.
  Pixel-click constants in `record_demo.py:180-197` are valid only at that size, so the
  runner pins `BARKS_PROBE_SCREEN=900x1300` and pixel tests fence on the measured window.
- `main.py:127 redirect_kivy_logs()` forwards `kivy.logger.Logger` into loguru and thus
  the app log. `okf_reader.ui` may import kivy (import-linter contract 5 bars only
  `okf_reader.core`), so the wiki viewer can log through Kivy's Logger with no new
  dependency and no API change.
- All five top-level screens subclass `ReaderScreen` (`ui/reader_screens.py:40`), which
  has no `on_enter`. One override there gives a transition-complete marker for every
  screen; transitions are random among eight types, so this matters.
- `_on_panel_fade_finished` (`ui/bottom_title_view_screen.py:242`) is the fade-end hook;
  logging inside its `anim is self._panel_fade_anim` guard removes every 4.5s hold.
- `open_confirm_popup` + `_ConfirmPopupNav` (`ui/popup_widgets.py:70-138`) is the single
  funnel for quit confirm and clear-history confirm.
- The wiki resume file lived in the data dir when this was written; it moved into the
  profile on 2026-09-16, so a scratch-profile boot now has none unless a test writes one.
  Wiki tests boot via node or chip, which re-roots history, and never depend on it.
- History DELETE deletes a row with no confirmation (`ui/history_screen.py:658`); Clear
  confirms. Both are safe only because the suite runs on a scratch history file.

## Architecture

### Layout (`src/barks-reader/tests/gui/`)

```
conftest.py                 scratch config template, boot(), artifacts hook, geometry fence
fixtures/barks-reader.json  canned AAA_Settings (node rewritten per boot)
fixtures/barks-reader-history.json  canned 6 events / 2 days / 3 titles
screens/                    thin page objects: driver calls only, no logic worth unit-testing
  tree.py title_view.py reader.py search.py index.py history.py wiki.py settings.py docs.py
test_tree_and_main_screen.py  test_title_view.py  test_comic_reader.py  test_fullscreen.py
test_search.py  test_indexes.py  test_history.py  test_reading.py  test_wiki.py
test_docs_and_stats.py  test_settings_menu_quit.py  test_fun_view.py
```

The existing `test_gui_paths.py` tests migrate into their families in M3 and the file is
deleted. The directory stays outside pytest `testpaths`, so `uv run pytest` is untouched.

### Harness changes (no app change)

- `scripts/gui-probe.sh`: `config_file()` honours `BARKS_READER_CONFIG_DIR` from the
  environment before falling back to `.env.runtime`; new `geometry` subcommand printing the
  app window's `WxH+X+Y` (reuse the xwininfo grep in `park_pointer`, L236-250).
  `doctor` keeps checking the live config.
- `scripts/gui_driver.py` (stays stdlib-only, shared with `record_demo.py`; every
  addition gets a stub-driver unit test in `scripts/tests/test_gui_driver.py`):
  - `boot_app_at(..., config_dir=None)`: exports the env var before `probe("start")`;
    `config` defaults to `config_dir / "barks-reader.json"`.
  - `Driver.main_menu_button(name)`: main-screen action bar walk with the same sticky
    tracking as `_walk_menu_to`, order `icon, fullscreen, go_back (default), collapse,
    change_pics, menu, quit` (`ui/main_screen.py:139-150`). `go_back()` becomes a call to it.
  - `Driver.expect_no_new(pattern, window_s)`: the only sanctioned clock wait, for
    negatives such as "the quit fence must not quit".
  - `Driver.window_geometry()` and `Driver.shot(path)` wrappers.
- `conftest.py`:
  - session `scratch_template`: copy the live config dir once, then override in the ini:
    `confirm_quit=1`, `goto_fullscreen_on_app_start=0`, `goto_fullscreen_on_comic_read=0`,
    `alt_escape_key=0`, `goto_saved_node_on_start=1`, `is_first_use_of_reader=0`,
    `double_page_mode=0`, `record_reading_history=1` (hermetic, lets a test assert the
    append), `main_window_height=0`, `main_window_left=-1`, `main_window_top=-1`,
    `log_level=DEBUG`; copy `log-config.yaml`, `never-crop.txt`, `kivy/config.ini`
    verbatim (check it keeps `position = custom`).
  - function `boot(node, *, cues=None, ini=None, history=True)`: fresh copy of the template
    into `tmp_path/config`, write the canned json and history, apply ini overrides, then
    `gd.boot_app_at(node, config_dir=..., seed=SEED, cues=cues)`. One boot per test stays
    asserted. Teardown stops the app and pops the env var. The Driver carries `.scratch`
    so a test can read the json, history or ini after stop to assert persistence.
  - artifacts: `build/gui-tests/<timestamp>/` (build/ is gitignored). The makereport hook
    on a failed call phase saves `probe shot`, `probe tail 80` and the scratch dir's
    `kivy/logs/barks-reader.log`. `d.checkpoint("name")` saves a PNG only when
    `BARKS_GUI_SHOTS=1`.
  - geometry fence: `boot()` records `window_geometry()`; pixel-click helpers call
    `require_geometry(d)` which fails (not skips) unless it equals the hard-coded
    measured window (782x1224 today, next to the search row constants).
  - session teardown asserts the live `barks-reader.json` and history are byte-identical
    to their pre-run copies.
- `scripts/run_gui_tests.sh`: export `BARKS_PROBE_SCREEN=900x1300`; pass extra args through.

## Coverage matrix

Oracle strength: S = strong (new-occurrence marker via `expect`), W = weak (settle or
clock), B = blocked until the M2 marker lands (write as W, upgrade to S). PX = pixel click,
geometry-fenced. Node chains are leaf-to-root; after any run the scratch json holds the
chain the app saved, which is how to author a new one.

**A. Tree and main screen (8)**: expand/collapse The Stories (`Node expanded/collapsed:`);
Down x3 then Left collapses to parent (`New selected node: "1947-1950"`); Series > Covers
year range; menu mode Left/Right wrap ending on Go Back (`'Go back' menu item selected.`);
Escape+Return goes back to the previous node; **quit fence**: walk to Quit, Return, Escape
cancels, `expect_no_new("Closing app...", 2)`, app still answers Down (B until popup
markers); Up on first node reaches the top goto arrow (`Entered top-view goto arrow
focus.`) then Return `Goto title:`; Collapse button collapses the whole tree.

**B. Title view (5)**: fade finished (B; today a 4.5s hold); Return enters at portal,
Up to eye, toggle, Escape exits (`entered nav focus at portal` / `exited nav focus` /
`Exited bottom focus region.`); overrides checkbox on a censored-fixed story
(`Use overrides checkbox changed:`); goto-page row unchecked opens at the front
(`Load "..." and goto page`); row left checked opens at the cued page (`Showed page 34 in`).

**C. Comic reader (9)**: migrate browse/open/read/close; Left at first page (`Already on
the first page`, no new `Showed page`); Goto End then Right (`Last page: requested index`,
`Already on the last page`); Goto Start (`Showed page 0 in`); migrate goto_page(12) +
double page (B for `Double page mode toggled`); reopen the goto dropdown and step Up to
page 3 (`Showed page 3 in`, B for dropdown markers); Up enters menu mode, Escape exits, a
second Escape does not close the reader; one-pager collection ignores double page (B);
after close the scratch history has one new event (file assertion).

**Fullscreen family (`test_fullscreen.py`, 2)**: reader fullscreen on and off
(`Entered fullscreen mode on ComicBookReaderScreen.`, `Entered windowed mode on ...`),
window geometry restored afterwards; main screen fullscreen on and off (`Entered
fullscreen mode on MainScreen.`). No pixel click ever follows a fullscreen toggle in the
same boot; the family is its own module for that reason.

**D. Search (6)**: title search, PX click row 2 (`Search: selected "Vacation Time"`,
`Goto title: "VACATION_TIME"`); the same then wait fade, open, close, go back (new
`SearchScreen mode set to 'Title'`); tag search by keyboard (`Tag search: selected tag` /
`selected member`, PX fallback if Down from the input proves unreliable as record_demo
found); word search chip, PX balloon, PX bubble (`Word search: selected chip`, `Show
speech bubbles for: "..." and search`, `Word search bubble press:`); no-match query (B,
results-count marker); Escape blurs then Right clears (B).

**E. Indexes (7)**: Main Index builds (`Building index...`, `Index build complete`,
`Populated index page for letter 'A'`); Right into items, Return on a title (`Index item
pressed:`, `Handling title:`, `Goto title:`); expand a tag group (`Handling tag group:`);
empty letter (B; today only `Letter 'X' pressed.`); migrate speech index letters; speech
prefix bar, term, bubble popup, title from popup (`Pressed prefix button:`, `Handling
index term:`, `Show speech bubbles for: "..." and index terms`, `Handling title from
speech bubble browser:`); Names and Locations entity indexes via the base markers.

**F. History (5, canned 6 events)**: enter (`HistoryScreen: entered nav focus.`, B for
`built 'journal' view with 6 rows`); Titles tab (B); Return on a row (`Goto title:`);
Delete a row (B marker; file assertion: 5 events after stop); Clear with cancel then
confirm (B popup markers; file assertion: 0 events).

**G. Reading (3)**: Surprise me repopulates on re-expand (B, seeded so the second draw is
deterministic and different); Playlists > The Bravery Stories, Down skips the intro row
(`Updating background view state to ON_PLAYLISTS_NODE`); With Scrooge, open a title.

**H. Wiki (5, skipped when `wiki_bundle_dir` is unset)**: open from the Indexes node
(`Wiki reader screen is active.`, B for `OKFViewer: Showed page`); open from the title
chip via Return + Up x2 (`Wiki page button pressed.`); Left into sidebar, Down x2, Return
(B); Escape to top bar, Return goes Back (B); Escape, Right x2, Return goes to title
(`New selected node: "VOODOO_HOODOO"`). Never enter the title view with Right and walk
down: documented wedge (`record_demo.py:742-748`).

**I. Documents, corpus stats, statistics (7)**: intro document open, Right x2, Left,
Close (`Switching to document reader for`, B for page markers); censorship-fixes document;
By the Numbers open and Escape (`Switching to the By the Numbers page...`, B for an
active marker); By the Numbers close via menu; Statistics tabs (`Statistics: loading
image` x2); Word tab dropdown (`entered dropdown nav.`); Don Ault article opens the comic
reader (`All images loaded`).

**J. Settings, menu, About (5)**: open Settings via the dots menu (`Display settings
object.`, B for `Settings closed.`); toggle `show_fun_view_title_info` twice (`Config
change:` x2, ini value round-trips); About open and dismiss (B); How To opens the
document reader; quit confirm path (`Closing app...`, teardown tolerates an exited app).

**K. Fun view (3)**: Change Pics then Right/Left (`Set fun view title to`); options
menu and clear all (`Fun view options button pressed.`, `... clear all pressed.`); goto
arrow (`Goto title:`, `Entered bottom focus region at the title portal.`).

About 60 enumerated; fold the smallest adjacent tests together to land at 50-55.

## App-side changes (log lines only; each with a one-line unit test)

barks-reader (loguru), file paths under `src/barks-reader/src/barks_reader/`:
- `ui/bottom_title_view_screen.py:229,242`: `Title view fade started: {duration}s.` and,
  inside the guard, `Title view fade finished.`
- `ui/reader_screens.py:40`: `ReaderScreen.on_enter`/`on_leave` log `Screen '{name}'
  entered/left.` (transition complete for all five screens). Qualify the four identical
  `Main screen is active.` lines (188, 210, 229, 264) with their origin; the driver
  matches by substring so nothing breaks. Add `By the Numbers screen is active.` and
  `Document reader screen is active: "{title}".` for symmetry.
- `ui/popup_widgets.py:99-138`: `Confirm popup opened: "{title}".` and `Confirm popup
  "{title}": confirmed/cancelled.` (pass the title into `_ConfirmPopupNav`).
- `ui/main_screen.py:334-348`: `Quit requested: asking for confirmation.` / `no
  confirmation needed.`; funnel `_on_settings_closed` and `_close_settings` (444-455)
  through one method that logs `Settings closed.`
- `ui/about_box.py:115`: `About box opened.` and, bound to `on_dismiss`, `dismissed.`
- `ui/history_screen.py`: `_select_view` (310) `History: selected '{view}' view.`;
  `_finish_build` (388) `History: built '{view}' view with {n} rows.`; delete handlers
  (544, 549) `History: deleted event/title "..."`; `do_clear` (776) `History: cleared.`
- `ui/comic_book_reader.py:788`: `Double page mode toggled: {mode}.` and `Double page
  toggle ignored: single-page collection.`; `goto_page` (796) `Goto page dropdown
  opened.`; `on_page_selected` (820) `Goto page selected: "{page}".`
- `ui/index_screen.py` empty-letter early return (~896): `Populated index page for
  letter '{letter}': no items.`
- `ui/search_screen.py`: results population `Search results: {n} for '{mode}'.`; clear
  handlers `Search cleared.`
- `ui/tree_view_manager.py:296` `_clear_and_repopulate`: `Repopulated '{name}' with {n}
  children.`
- `ui/corpus_stats_screen.py:140,153` and `ui/document_reader.py:53,64,108`: opened /
  page shown / closing lines.
- `ui/wiki_reader.py:140,161,257`: `Wiki reader opened (page = "...")`, `closing`, `Wiki
  goto title: "{name}"`.

okf-reader (`src/okf-reader/src/okf_reader/ui/viewer.py`, via `from kivy.logger import
Logger`, forwarded to the app log by `main.py:127`): `OKFViewer: Showed page '{rel}'
(history depth {n}).` at the end of `_show`; `OKFViewer: Focus region {name}.` in
`_set_focus_region`; `OKFViewer: Back to '...'` / `Back at history root; exiting.` in
`go_back`; `OKFViewer: Tree settled on '{text}'` in the reveal-when-settled check (this is
the "page settled" signal the design doc asked for); `OKFViewer: Page action '{label}'.`

Unit tests: add a `loguru_sink` fixture to `src/barks-reader/tests/unit/conftest.py`
(`logger.add(records.append, level="DEBUG", format="{message}")`) and assert each marker
in the module's existing test file (`test_history_screen.py`, `test_main_screen.py`,
`test_reader_screens.py`, `test_comic_book_reader.py`, `test_index_screen.py`,
`test_search_screen.py`, `test_bottom_title_view_screen.py`, `test_corpus_stats_screen.py`,
a new `test_document_reader.py`, a `_ConfirmPopupNav` test). For okf-reader attach a
`logging.Handler` to Kivy's Logger in a fixture under `src/okf-reader/tests/`. New words
go into `cspell-words.txt` at their alphabetical position, never by sorting the file.

## Phasing

- **M0, harness (no app change).** Probe env precedence and `geometry`;
  `boot_app_at(config_dir=)`; conftest scratch template, canned fixtures, artifacts hook,
  geometry fence, live-profile byte-identity assertion; `screens/` skeleton; the three
  existing tests green on the scratch dir. Runner pins the screen size.
- **M1, strong-oracle families (no app change, about 24 tests).** A1-A5, A7, A8, B2-B5,
  C1-C4, C7, C10, fullscreen x2, D1, D2, D4, E1-E3, E5-E7, I5-I7, J2, J4, K1-K3.
- **M2, markers.** Every app change above plus its unit tests, as its own commit.
  `record_demo.py` replaces `hold(TITLE_FADE_SECS)` with `expect("Title view fade
  finished")` and adopts `main_menu_button`.
- **M3, blocked families and upgrades (about 20 tests).** A6, B1, C5, C6, C9, D3, D5,
  D6, E4, F1-F5, G1-G3, H1-H5, I1-I4, J1, J3, J5. Migrate and delete
  `test_gui_paths.py`.
- **M4, docs.** Update `docs/plans/gui-testing-deterministic-mode.md` (variation sources
  1-4 done or decided, geometry env var not needed) and the CLAUDE.md run line.

Each milestone is committed independently green, following the repo's rule.

## Verification

- Run everything: `bash scripts/run_gui_tests.sh`. One family: `-k history` or the
  module path. Screenshots on demand: `BARKS_GUI_SHOTS=1 bash scripts/run_gui_tests.sh`.
  Budget: boot 3-5s; index, history and settings tests 8-12s; reader and search tests
  20-30s; about 55 tests in 15-20 minutes on the one nested display. Use `-x` while
  iterating; `--durations=0` is the pacing regression signal.
- Gates before every commit: `ruff check` and `ruff format --check`, `ty check`,
  `bash scripts/pyrefly.sh`, `uv run lint-imports`, `bunx cspell`, `uv run pytest`
  (unit plus `scripts/tests`), then the GUI run for the touched families. GUI tests never
  run in CI (real data dirs, `.env.runtime`, LFS `cpi.db`).
- After every GUI run the session teardown proves the live profile is untouched.
- Flakiness policy: no retries and no flaky marks. A test waiting on the clock, other than
  `expect_no_new` for negatives and the driver's functional key pacing, is a defect: wait
  on an existing marker or add one in M2. A failure's screenshot, log tail and
  `barks-reader.log` are the first things to read.
