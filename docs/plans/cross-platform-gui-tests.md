# Plan: GUI and window coverage on Windows and macOS

> Status: **approved in discussion 2026-09-23**, not started. Four steps, each useful on its
> own and each committed green; stop after any of them and the earlier ones still pay.

## Context

The GUI path suite (`src/barks-reader/tests/gui/`, `docs/plans/gui-test-suite.md`) runs only
on Linux under X11: `scripts/gui-probe.sh` starts the app on a nested Xephyr or Xvfb
server and injects keys with `xte`. The window geometry code has Windows-specific paths
(`ui/platform_window_win32.py`: `ctypes`/`user32` calls, fullscreen-exit timing, a
recovery path for a failed move) that are tested only with mocks. So the class of bug the
suite exists to catch, a window that shrinks after a reader close or a fullscreen round
trip, is invisible on the platforms where most of that code runs. CI's Windows and macOS
legs run the unit tests and `scripts/smoke-test-build.sh` (a build boots as far as the
installer's missing-data-pack popup). That shows a build starts, not how its window
behaves.

**Where tests can run.** The reader runs on an Ubuntu desktop, a touchscreen Ubuntu laptop,
a touchscreen Windows laptop, a Windows VM and a Windows PC. The Windows VM and laptop and
the Linux laptop are available for regular runs. macOS is not tried yet and can't be tested
regularly, so CI's macOS leg is its only regular coverage. CI has no data pack (Git LFS
quota, see the cpi.db rule), so a full suite runs only on those machines.

**The input path must stay real.** Keys injected at the OS level found bugs that keys fed
in inside the app would have hidden:
- with the virtual keyboard on, hardware keys never reached a focused search box;
- the main screen's guard read only the system keyboard's target, so Return in a search
  box also drove the tree;
- a key sent before the window was shown was lost, which is why `MAIN_WINDOW_SHOWN` exists.

So each platform gets real OS-level injection wherever it allows it. A test-only input
channel inside the app is a last resort, allowed only where the OS forbids injection, and
labelled in the results as not covering the input path.

## Step 1: fill in the window-geometry markers

Already there (`barks_reader.core.log_markers`): `WINDOW_RESIZED` (every resize event,
size only), `ENTERED_FULLSCREEN` / `ENTERED_WINDOWED`, `MAIN_WINDOW_SHOWN`. The harness's
`AppBoot.assert_window_size_kept` (`tests/gui/barks_gui/harness.py:421`) compares the X window's
geometry and the logged resize sizes at teardown.

Missing: position, and the state after a restore finishes. Add one marker,
`WINDOW_GEOMETRY = "Main window geometry ({reason}): {width}x{height}+{left}+{top}."`,
logged once the window settles after:
- boot (after `MAIN_WINDOW_SHOWN`);
- entering and leaving fullscreen (after `ENTERED_*`);
- the comic reader closing;
- a Win32 restore finishing (`Win32WindowBackend.schedule_restore`'s `sync_and_finish`).

Log it from the one place that already knows the mode changed, not from every widget, and
add a `loguru_sink` unit test per call site, as the suite's marker contract requires.

**Why first:** from then on, any run on any machine shows a shrink or a move in its log:
the suite, a CI boot, or ordinary use on the Windows PC. The harness's size check can use
the same markers, which also replaces the "no window manager" caveat in
`assert_window_size_kept` with the app's own view.

## Step 2: real Win32 calls in Windows CI

A new unit test module, `tests/unit/test_platform_window_win32_live.py`, skipped unless
`sys.platform == "win32"`. It creates a real top-level window on the `windows-latest`
runner with plain `ctypes` (`RegisterClassW` + `CreateWindowExW`, no Kivy, no data pack)
and runs `Win32WindowBackend` against its HWND:
- `_find_hwnd_by_enum_windows` finds it by class name;
- `_set_window_rect` moves and resizes it, and `GetWindowRect` reads back what was set;
- a move to an off-screen position goes through `_recover_from_failed_move`;
- `save_state` then restore returns to the same rect.

The backend's lookup may need an injectable class name or HWND to find a test window
rather than SDL's. If so, that is a small constructor seam, not a behaviour change.

The existing mocked tests stay; they cover the branches a live window can't force.

**Why:** the code that has only ever been mocked gets exercised against the real OS on
every push, with no data pack.

## Step 3: the GUI suite on Windows, with real key injection

**The seam.** `scripts/gui_driver.py` calls the probe only through `probe()`, and the
probe's subcommands are a fixed set: `doctor`, `start`, `stop`, `stop-xserver`,
`geometry`, `shot`, `settle`, `click`, `key`, `type`, `wait`. The port is a second
implementation of exactly that set, as a Python script, `scripts/gui_probe_win.py`, with
the same arguments, output formats and exit codes. `probe()` picks it on Windows. Nothing
in the tests changes.

| Subcommand | Linux (`gui-probe.sh`) | Windows (`gui_probe_win.py`) |
|---|---|---|
| `start` | Xephyr/Xvfb, `setsid` the app, wait for the ready marker | `subprocess.Popen` the app (new process group), same env vars (config dir, data dir, seed), wait for `MAIN_WINDOW_SHOWN` in the log, then bring the window to the foreground |
| `key` / `type` | `xte key` | `SendInput` via `ctypes` (virtual-key codes for the six remote keys plus the few desktop keys the waiver list allows; its Unicode flag for `type`) |
| `click` | `xte mousemove/mouseclick` | `SendInput` mouse events in absolute coordinates |
| `geometry` | `xwininfo` | `GetWindowRect` on the app's HWND, printed as `WxH+X+Y` |
| `shot` | `import -window` | `PIL.ImageGrab.grab(bbox=<window rect>)` (Pillow is already a dependency) |
| `settle` | wait for the log to go quiet | same logic, shared |
| `wait` | grep the log | same logic, shared |
| `stop` | kill the process group | kill the app's process tree by PID |
| `doctor` | tool checks | checks for an interactive, unlocked desktop session and a foreground-able window |

Log waiting and settling are ordinary Python. Move them into a small shared module both
probes use, so they can't drift apart.

**Constraints on Windows:**
- `SendInput` goes to the foreground window. The probe brings the app to the front after
  `start` and before each key burst, and `doctor` fails on a locked or disconnected
  session (a minimized RDP client, a locked VM console).
- One worker, visible: there is no nested display to run workers side by side. Expect
  roughly 10 to 15 minutes for the suite.
- Tests that depend on X-specific behaviour (the "no window manager" note on fullscreen
  in `assert_window_size_kept`) take their Windows branch from the step 1 markers.
- The remote-key gate (`scripts/check_gui_keys.py`) is unchanged: `SendInput` maps the
  same six names.

**Running it:** `run_gui_tests.sh` stays the Linux entry point. A small
`scripts/run_gui_tests.py` (or a PowerShell wrapper) runs pytest on `tests/gui` with the
Windows probe selected and supports `--app PATH`, so a Nuitka build can be the target.
Run it on the Windows VM and laptop, as the settings matrix is run on Linux.

**First pass expectations:** the first Windows run will fail in ways that are the point.
Record each finding in `docs/plans/gui-test-suite.md`'s status list, as the Linux matrix
findings were.

## Step 4: a small cross-platform suite in CI, with no data pack

What CI can check on all three OSes without the data pack: boot the build to the
installer's missing-data-pack popup, check `MAIN_WINDOW_SHOWN` and the step 1 geometry
marker, press Return and Escape through the platform's real injection, and check that
the popup reacts and the app exits cleanly. This extends `smoke-test-build.sh` from
"it starts" to "it takes keys and keeps its window". It also runs on every build leg,
which makes it the only regular macOS coverage.

**macOS injection:** real keys need `CGEventPost` (Quartz, through `ctypes` or
`pyobjc`), which needs the Accessibility permission for the process posting them. Try it
on the `macos-latest` runner first. If the runner refuses the permission, and only then,
fall back for this one CI check to an in-app channel: an env-var-gated file the app reads
on its clock and dispatches as Kivy key events. Label that leg's result "input path not
covered". The channel stays out of the build unless the env var is set, and it is never
used where OS injection works.

**Linux:** the same check through the existing probe, headless.

## Later, not in this plan: touch

Three of the machines are touchscreens, and every GUI test presses keys, so the touch
path has no coverage at all. `SendInput` has a touch-injection sibling
(`InitializeTouchInjection` / `InjectTouchInput`) on Windows, and Kivy can record and
replay motion events. Once step 3 exists, a `tap` subcommand with the same seam is the
natural next step. It's out of scope here so the key port lands first.

## Verification

- Step 1: unit tests for each marker; a Linux GUI run shows the markers in every test's
  app log, and `assert_window_size_kept` reads them.
- Step 2: the Windows CI leg runs the live module (it is skipped elsewhere) and passes.
- Step 3: the full GUI suite on the Windows VM; its failures are triaged as app bugs or
  harness gaps and recorded. Then the same run with `--app` on a Nuitka build.
- Step 4: every build leg runs the check, and each leg's summary says whether its input
  path was real.
