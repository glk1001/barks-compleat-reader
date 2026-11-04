# GUI path tests

Run with `bash scripts/run_gui_tests.sh`, or `--headless` on Xvfb with no window or desktop
session, which also runs four workers in parallel on displays :2 to :5, about eight minutes
for the suite (some 150 tests); on Windows and macOS,
`uv run python scripts/run_gui_tests.py`, one worker on the real desktop, through
`scripts/gui_probe.py`'s backend for each, `gui_probe_win32.py` and `gui_probe_darwin.py`;
macOS plan: `docs/plans/macos-gui-tests.md`.

The marker text is written once, in `barks_reader.core.log_markers`
(`okf_reader.core.log_markers` for the wiki viewer): the app logs it with `.format`, a
GUI test waits on it with `pattern()`. Plan and status: `docs/plans/gui-test-suite.md`.
`--soak` runs the random walk instead (off by default); `--notes-fit` runs the walk that
checks every story's notes show all their lines, also off by default (`test_notes_fit.py`;
about 2.5 minutes a screen, and the overnight `notes-fit` stage does six); `--app PATH` runs the suite
against a Nuitka build; `--prebuilt`, `--png-images` and `--ini` move a run to other
settings; `--screen WxH` picks another nested screen size; `--keep-logs` saves every
passing test's artifacts too (logs, profile, final frame), as a failure's;
`bash scripts/run_gui_matrix.sh` runs the suite once per settings variant (the two
themes, the virtual keyboard, no title info, the censorship fixes, the two-page spread on
its landscape screen;
`--list`, `--only NAME`). Every boot is held to the layout its ini names
(`harness.layout_problem`): the harness pins the single page, and one test boots on the
default, "Match the screen", whose layout the run's screen shape decides.

`test_taps.py` taps instead, by what a widget shows, never by pixel: the app lists
its tappable widgets on request (`barks_gui.taps`, `barks_reader.core.tap_targets`).
A tap is a click; `--touch` makes it a real touch too, on a virtual touchscreen, and
needs the udev rule in `scripts/udev/` once, and the user in the `input` group (select
with `-k test_taps`: one worker).
The leak tests (`-k leave_no`) ask the app the same way what it holds after a full
garbage collection (`barks_gui.memory`, `barks_reader.core.memory_census`): widgets and
textures may not climb over repeated round trips. The app's resident size is no leak
signal here: garbage waits long for a full collection, and glibc keeps freed memory.
Plan: `docs/plans/touch-gui-tests.md`.

Every duration the app logs is held to a loose budget at teardown
(`tests/gui/barks_gui/timings.py`): this machine's, once `--calibrate` has written
`.benchmarks/gui-timings.json`, else the committed ones; skipped when the load exceeds
what the cores and the run's workers account for; `BARKS_GUI_NO_BUDGETS=1` turns it off.
A new timed line is a marker with an `{elapsed}` field, added to `TIMED` and `BUDGETS`
there. Every page the comic reader settles on is held centred across the window at
teardown too (`assert_page_centred`, from the `PAGE_PLACED` line the reader logs when a
page moves; a placement replaced within a second is a frame on the way and not judged).
