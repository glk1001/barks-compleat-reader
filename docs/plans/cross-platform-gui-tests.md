# Plan: GUI and window coverage on Windows and macOS

> Status: **approved in discussion 2026-09-23**; steps 1-4 done, a laptop run left. Four steps, each useful on its
> own and each committed green; stop after any of them and the earlier ones still pay.
>
> - Step 1: DONE 2026-09-23 (e592d825, ae79cb16). `WINDOW_GEOMETRY` is logged at the five
>   places a window change ends (boot, and each screen's fullscreen and windowed finish);
>   the Win32 restore needed no site of its own, since it finishes through the windowed
>   callback. `assert_window_size_kept` holds the last settled size to the boot one. On the
>   nested display a reader fullscreen round trip logs 782x1225+59+10, 900x1300+0+0, then
>   782x1225+59+10 again. Full GUI suite green (62 tests).
> - Step 2: DONE 2026-09-23 (219b7f4b), green on the first Windows CI run (six tests).
>   `test_platform_window_win32_live.py` drives the backend against a window it makes:
>   lookup, move and resize, save, a scheduled restore, and the recovery path, forced by a
>   size below Windows' minimum track size (an off-screen move, as first planned, simply
>   succeeds). Two changes the plan did not foresee: the backend takes an optional `hwnd`,
>   since on a dev machine Kivy's own SDL window can be in the same process; and a
>   `needs_no_opengl` marker, since headless CI skips every module that imports UI code.
>   This was the backend's first test of any kind.
> - Step 3, milestone A: DONE 2026-09-23 (b980354e, 7bc2f439, e38e8e30). `gui_probe.py`
>   (commands and output as `gui-probe.sh`) over a Win32 backend (`SendInput`, window by
>   title, foreground before every key, DPI-aware), `run_gui_tests.py`, the driver picking
>   the probe per platform. On the Windows VM (Windows 10, console session, the exe's
>   profile via `.env.runtime`) `test_main_screen_fullscreen_round_trip` passes with every
>   teardown check. The first run found one X11 assumption in the harness: the window's
>   first resize event is not its boot size on Windows (no resize at boot there), so the
>   size check now measures against the app's boot geometry line.
>   **Windows finding, open:** leaving fullscreen, the window's drawable area briefly
>   measures 794x1258 before settling at 778x1219. The difference, 16x39, is the window
>   frame: the restore momentarily gives the client area the saved outer size, and the
>   app's aspect correction puts it right. Worth a look in `platform_window_win32.py`
>   (`save_state` keeps `GetWindowRect`, the outer rectangle).
> - Step 3, milestone B: DONE 2026-09-23. The whole suite on the Windows VM is green: 61
>   passed and 1 skipped (the prebuilt-archives test; no prebuilt comics there) of the 62
>   tests, in 13m56s, with 7100c3fd (the wiki chip test no longer needs a prebuilt comics
>   directory). What the first whole runs found, in the order found:
>   - **App bug (4c173998):** reaching History or Reading crashed the reader on Windows with
>     the JPG panels zip: the node's picture was named `Path(title) / "129-3.jpg"`, a
>     backslash inside a zip member name. Seven tests.
>   - **App log (2d2ae4fb):** leaving fullscreen, a Windows window passes for ~0.3s through
>     its size plus a frame at a position above the screen; the monitor lookup logged that
>     as an ERROR though every caller copes. Now a warning.
>   - **Harness and probe, Windows-only assumptions:** no resize event at boot (7bc2f439);
>     loguru colours a file when TERM is set, as Git Bash sets it (ccc3d4f3); the console's
>     cp1252 cannot print the log's box drawing (6c4fade8); pytest's output buffered in the
>     runner's pipe (5bd73fe2); taking the foreground by tapping Alt sent a key to another
>     window (8a3f606c).
>   - **The VirtualBox VM itself, not the reader:** its OpenGL pass-through stops creating the
>     drawing buffers the reader needs after a boot or two, so the suite runs with `--angle` (Direct3D,
>     3d0177e8, guarded by deebe061); with 3D acceleration on, Direct3D still went through
>     VirtualBox's 3D layer and the display went black, so 3D acceleration is off (WARP, the
>     software renderer); and with discard on, the dynamic .vdi stalled on TRIM until the
>     guest froze, so discard is off on its disk. With all three, the whole suite runs clean.
>   On Windows: `uv run python scripts/run_gui_tests.py --angle` on the VM (a real machine
>   needs no `--angle`), `--calibrate` once per machine.
> - Step 4: DONE 2026-09-24 (c8aa0234, all four build legs green). Every build: Linux and
>   Windows (through ANGLE) reach the installer's popup, take a real Escape through the OS
>   and exit by themselves; macOS's runners cannot open a Kivy window (no OpenGL), so it
>   reports that instead. Details, and the Windows cache fix, under Step 4 below.
>
> **What is left:**
> 1. The whole GUI suite once on the Windows laptop, without `--angle`: the reader's normal
>    OpenGL drawing on real hardware, which neither the VM (ANGLE, software) nor CI (no
>    OpenGL 2.0 on Windows runners) covers. `uv run python scripts/run_gui_tests.py`, then
>    `--calibrate` once for the laptop's timing budgets.
> 2. macOS window and input coverage needs a real Mac; CI's runners cannot draw.
> 3. The open Windows finding above: leaving fullscreen, the client area briefly takes the
>    outer size (a 16x39 frame step) before settling.

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
first-run installer's missing-data-pack popup (as `smoke-test-build.sh` already does on
every build leg), press a key through the platform's real injection, and check that the
popup closes and the program exits cleanly. This extends the smoke test from "it starts"
to "it takes keys", on every build leg, which makes it the only regular macOS coverage.

**Checked 2026-09-24, before building it:**
- **The popup and keys:** the installer's popup is `show_standalone_popup` in its own
  temporary Kivy loop, not the main reader, so `MAIN_WINDOW_SHOWN` and the geometry
  marker never fire there (the plan first said to check them). Escape closes it (the
  reader's alternative Escape key too), and closing it stops the loop, so the installer
  then exits by itself. Return does nothing: only a click on its close button, which has
  no keyboard focus. It logs nothing on opening or closing (the About box gets its lines
  through `on_dismiss`; the installer passes none), so step 4 first needs markers for
  the popup opening and closing, and optionally Return as "OK".
- **macOS injection works on GitHub's runners**, both `macos-latest` and
  `macos-15-intel`: the job's process is trusted for Accessibility (`AXIsProcessTrusted`
  is true; the runner's TCC database pre-grants its tools), and keys posted through
  `CGEventPost` (the system event stream) and `CGEventPostToPid` both reached a Tk
  window. So macOS gets the real input path like the others, and the in-app key channel
  the plan held in reserve is not needed. (A throwaway branch ran the experiment; it is
  deleted.)

**The pieces:**
1. Log markers for the standalone popup opening and closing (with a `loguru_sink` unit
   test), in `barks_reader.core.log_markers`; Return closes it as Escape does.
2. A key sender per OS, small and stdlib-only: `xte` on Linux (under the smoke test's
   xvfb), `SendInput` on Windows (from `gui_probe_win32.py`), `CGEventPost` on macOS.
3. `smoke-test-build.sh --press-escape`: wait for the popup's opened line, send Escape,
   require the closed line and the program to exit by itself, instead of the 90s wait and
   kill. The existing launches stay as they are; this is one more.

**Built 2026-09-24** (1651af39, ae1a3778, 33e160e4, and the commit adding this):
`STANDALONE_POPUP_OPENED` / `_CLOSED` and Return-closes in `show_standalone_popup`,
`scripts/send_os_key.py`, and `smoke-test-build.sh --press-escape` as a Build step. What the
first runs showed about CI's runners, which changes the step's reach:
- **Linux:** passes. xdotool presses Escape on the smoke test's own Xvfb, the popup closes
  and the build exits by itself.
- **Windows:** the runner's OpenGL is `GDI Generic 1.1`, below Kivy's 2.0, so a default
  launch only ever reaches Kivy's "OpenGL 2.0 not found" message box - the older default
  smoke launch has been passing at that box, not at the app's popup. The Escape step
  runs through ANGLE there, which does reach the popup.
- **macOS:** the runners cannot create an OpenGL context at all (`Failed creating OpenGL
  pixel format`), so no Kivy window opens and the build exits in about two seconds; both
  macOS smoke launches pass on the installer's log and flag alone. Key injection works
  there (the Tk experiment), but there is no window to take the key, so the Escape step
  skips macOS. macOS window and input coverage has to come from a real Mac.
Every smoke launch now also says what it reached: the app's popup, Kivy's OpenGL error
box, or no window.

**Step 4: DONE 2026-09-24** (c8aa0234 all green). On every build: Linux and Windows (through
ANGLE) reach the app's popup, take a real Escape and exit by themselves; macOS reports that no
window can open on its runners. Two fixes on the way: the Windows key sender now finds the
installer's window by process and SDL class, since Kivy leaves it untitled (63b8b412); and
the Nuitka cache is saved straight after the build rather than at the end of the job
(c8aa0234), so a failing smoke test no longer discards it - after GitHub's Windows image
update every cached object missed, and each failing run had been recompiling for 33-43 min.

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
