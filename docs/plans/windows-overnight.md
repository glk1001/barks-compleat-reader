# Plan: an overnight run on Windows

> Status: **planned 2026-09-30, not started.** Saved here so it survives across machines
> and sessions; do it on the Windows laptop. Tick a step off here, with its commit, as it
> lands.
>
> - Step 1 the runner, by hand: TODO
> - Step 2 keeping the machine awake and fit to run: TODO
> - Step 3 the nightly schedule: TODO
> - Step 4 the validate stage, once the data is there: BLOCKED (the prebuilt comics)

## Context

`scripts/run_overnight.sh` is Linux-only: it runs its GUI stages on Xvfb, keeps the
machine awake with `systemd-inhibit`, and is bash. On Windows, CI already covers, on every
push: the unit suite without the data pack, the Nuitka build, and a smoke test of that
build that presses Escape (`smoke-test-build.sh`, twice: OpenGL and ANGLE). What CI
cannot cover is the real data pack, the real OpenGL drawing on real hardware, the built
executable doing real work, and long runs.

The GUI suite already runs on Windows by hand: `scripts/run_gui_tests.py`, through
`gui_probe.py`'s Win32 backend (real keys by `SendInput`), one worker in a visible
window, about 13 minutes (`docs/plans/cross-platform-gui-tests.md`, step 3, and
`docs/plans/gui-test-suite.md`, 2026-09-23 and 24). Its first runs found Windows-only bugs
no Linux run could: History and Reading crashed the reader with the JPG panels zip (a
backslash inside a zip member name, 4c173998), a log marker named its page with
backslashes (abe1aa4d), and the fullscreen exit drew the window frame for ~255ms
(1ec76c4c). That class of bug is what a nightly Windows run is for.

**Machine: the Windows laptop**, not the VM. The laptop draws through the reader's normal
OpenGL; the VirtualBox VM needs `--angle` (Direct3D), which does not test that path. The
laptop is also a touchscreen, for later (below).

## The stages

In this order, each logged to `build/overnight/<stamp>/<stage>.log`:

| Stage | What it runs | Why on Windows | Time |
|---|---|---|---|
| `update` | `git pull --ff-only`, `uv sync --locked` | The run tests what is on `main` that night. | 1 min |
| `pytest` | `uv run pytest` with the data pack | CI's Windows leg skips every test that needs it. | 1 min |
| `fetch-build` | CI's `barks-reader-win.exe` for **this checkout's commit** | The built-app stage must test the same code as the others. | 1 min |
| `gui` | `run_gui_tests.py`, the workspace app | Real OpenGL and Windows paths through every screen. | 13 min |
| `built-app` | `run_gui_tests.py --app <exe>` | CI only checks the build starts; packaging bugs (DLLs, onefile paths, zip members) show only when it reads comics. | 13 min |
| `soak` | `run_gui_tests.py --soak`, one seed | A long random walk: crashes, stuck screens, file handles. | 5-10 min |
| `validate` | `validate-barks-reader-files.py --full-load-check --strict-wiki` | The whole library through Windows paths and zip reading. Skips itself until step 4. | 5 min |

About 40-45 minutes, in one visible window.

- **`fetch-build`** is `scripts/get-win-build.sh`'s logic in Python, with one change: that
  script takes the newest Build Verification run on `main`, but this stage wants the run
  whose head is `git rev-parse HEAD` (`gh run list --commit <sha> --workflow "Build
  Verification"`), waiting for it if it is still building. When there is none, or it
  failed, `fetch-build` fails and `built-app` skips itself, saying why. The artifact goes
  under `build/overnight/<stamp>/`, not over the last night's.
- **The soak seed** comes from the day of the year, as the Linux run's do, but one a night
  rather than three, since one worker runs them one after another
  (`BARKS_OVERNIGHT_SOAK_SEEDS` overrides); 1000 keys (`BARKS_OVERNIGHT_SOAK_STEPS`).
- **A settings variant**, maybe later: one of `run_gui_matrix.sh`'s variants a night
  (virtual keyboard, double page, ...), by weekday, through `--ini key=value`. The whole
  matrix is six more 13-minute suites; one a night covers it in a week.

**Left to Linux, CI or the main machine**, since they behave the same on every platform
or cannot run here: lint, ty, pyrefly, cspell, the wiki checks, random order, dependency
drift, audit, mutation testing, coverage and graphify; `build-check` and the sibling repos'
tests (the main machine's build tree and pipelines); `smoke` (CI's); the GUI timing drift
(the budgets are still held per test by `--calibrate`, step 2).

## Step 1: the runner, by hand

`scripts/run_overnight_windows.py`, Python rather than bash: Git Bash sets `TERM`, which
has loguru colour a log file (ccc3d4f3), and its console is cp1252. The shape follows
`run_overnight.sh`:

- `--list`, `--only`, `--skip`, `--app PATH` (use that exe; no `fetch-build`);
- `build/overnight/<stamp>/summary.txt` in the Linux format, rewritten after every stage
  (passed, FAILED, WARNED, skipped or stopped, and the time), so the two machines' results
  read alike;
- every file read and written names UTF-8 (the harness learnt this the hard way,
  6c05532c);
- a stage that fails does not stop the others, except that nothing runs after a failed
  `update`;
- exit status 0 only when no stage failed.

Before the GUI stages it runs `gui_probe.py doctor` and stops them, with its reasons, if
the screen is locked, the session is a minimized remote one, or the app's window is
already open. `SendInput` reaches none of those.

Done when a run by hand, from PowerShell, passes every stage but `validate` and writes a
summary a Linux run's reader would recognise. Unit tests for the stage table and the
summary format, like `scripts/tests/`'s for the Linux helpers.

## Step 2: keeping the machine awake and fit to run

- **Awake.** During the run, `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED
  | ES_DISPLAY_REQUIRED)`: the Windows `systemd-inhibit`, and the display too, since
  `SendInput` needs a screen that is on and unlocked. Cleared when the run ends, however
  it ends.
- **Unlocked.** The screen must not lock during the night (Settings, Accounts, Sign-in
  options: "If you've been away, when should Windows require you to sign in again?" set
  to Never), and no screen saver with a password. `doctor` catches a locked screen at the
  start; a lock mid-run fails the GUI stage that meets it.
- **Left alone.** A key or a click from anyone goes to the app and fails the test (the
  teardown's STRAY INPUT check names it).
- **Windows Update.** Active hours to cover the run, so it does not restart the machine
  under it.
- **Calibrated.** `run_gui_tests.py --calibrate` once, so the timing budgets are the
  laptop's own.

Add these to `docs/setup.md`'s Windows section as the machine's one-off setup.

## Step 3: the nightly schedule

A Task Scheduler task, nightly (02:00, say), running the runner through `uv run`, set to
**"Run only when user is logged on"**: `SendInput` needs the interactive desktop, which a
task run without a logged-on user does not have. "Wake the computer to run this task" on,
and "Stop the task if it runs longer than" 2 hours, in case a stage hangs. A
`scripts/windows/` export of the task (XML) or a PowerShell line that registers it, so a
second machine is set up the same way.

The results stay on the laptop. Reading them from the main machine (ssh into the laptop,
or the summary pushed somewhere both can see) is a later choice.

## Step 4: the validate stage, once the data is there

`validate-barks-reader-files.py --full-load-check` does not read the comic build tree
(about 330 GB; only `build-check` does), but it does need what `copy-to-overnight-host.sh`
sends a Linux host, about 34 GB:

| Data | Size | Needed by |
|---|---|---|
| The prebuilt comics (`Books/Carl Barks/The Comics`) | 18 GB | Phase 7, always on: every title's prebuilt CBZ must exist |
| The Fantagraphics volumes (the profile's `fanta_dir`) | 9.2 GB | Phase 9, `--full-load-check`: decodes every page |
| The PNG panels | 3.8 GB | the panel phases |
| `Reader Files` | 2.8 GB | everything |

The laptop's GUI run skipped its prebuilt-archives test, so it likely lacks the prebuilt
comics: Phase 7 would fail on every title. Until they are copied over, the stage skips
itself, saying which folder is missing, rather than failing every night. (A
`--no-prebuilt` switch for `validate` that skips Phase 7 would let the rest run sooner;
decide when this step comes up.)

## Later, not in this plan

- **Touch on Windows.** The laptop is a touchscreen, but the Linux touch tests inject
  through `uinput`. Windows would need touch injection (`InjectSyntheticPointerInput`),
  which is new work: see `docs/plans/touch-gui-tests.md`.
- **The settings matrix** in full, beyond one variant a night.

## Verification

- Step 1: a run by hand passes every stage but `validate`; `summary.txt` matches the Linux
  format; the unit tests pass in CI on all three platforms.
- Step 2: a run with the lock screen due mid-run finishes; `powercfg /requests` shows the
  runner's request while it runs and none after.
- Step 3: two scheduled nights in a row, results read the next morning; one night with a
  deliberately failing test shows FAILED and keeps its artifacts.
- Step 4: once the data is copied, `validate` passes there as it does on the Linux host.
