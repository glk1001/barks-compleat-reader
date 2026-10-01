# Plan: the GUI suite on macOS

<!-- cspell:ignore dyld killpg pgrep caffeinate screencapture CGEvent CFDictionary CFArray CFNumber CGWindow softgl libsoftgl osascript frontmost CGHID pgid creationflags FONTSCALE -->

> Status: **planned 2026-10-01, not started.** Written on the macOS 12.6 VirtualBox guest
> (2 cores, 4 GB, no GPU driver), where the unit suite now runs on Apple's software OpenGL
> (71900174). Milestones A to C, each committed green; stop after any of them and the
> earlier ones still pay.

## Why

The GUI suite runs on Linux (`run_gui_tests.sh`, Xephyr or headless Xvfb) and on Windows
(`run_gui_tests.py`, real `SendInput` on the desktop), but on macOS nothing drives the
real app: CI's macOS leg skips every UI unit test (no OpenGL on its runners), and there is
no macOS backend for `scripts/gui_probe.py` (it stops with "no gui_probe.py backend for
darwin"). The app has no macOS window code of its own (`platform_window_win32.py` has no
counterpart; `IS_MACOS` is used only in `config_info.py`), so its fullscreen and
window-restore paths on macOS are SDL's and Kivy's defaults, never yet tested.

The first blocker is gone: `scripts/macos/with-soft-gl.sh` lets Kivy draw on a guest with
no GPU (its SDL2 asked for an accelerated visual; see `scripts/macos/softgl.c`). What is
left is the probe.

## Shape

The same as Windows: one worker, in a visible window on the real desktop, through
`scripts/gui_probe.py` over a platform backend. There is no headless mode on macOS: no
display like Xvfb exists, and Kivy's SDL2 draws through Cocoa, not X11, so an XQuartz Xvfb
would not be used. Leave the machine alone while it runs, as on Windows.

## Milestone A: the backend, and one test green

1. **`scripts/gui_probe_darwin.py`**, a `gui_probe.Backend` (the protocol at the top of
   `gui_probe.py`), modelled on `gui_probe_win32.py`. Use `ctypes` against the system
   frameworks (CoreGraphics, CoreFoundation, ApplicationServices), as the Win32 backend
   does against user32, so no new dependency; keep the pure parts (key table, picking a
   window out of the window list, the drawable-area arithmetic) importable and testable
   on every platform, as Win32's are. If parsing `CFArray`/`CFDictionary` by hand gets
   out of hand, `pyobjc-framework-Quartz` under a `sys_platform == 'darwin'` marker in the
   dev group is the fallback.

   | Method | macOS |
   |---|---|
   | `find_window` | `CGWindowListCopyWindowInfo(OnScreenOnly \| ExcludeDesktopElements)`; pick the layer-0 window whose `kCGWindowOwnerPID` is the app's (the probe's pid file, and that process's children: `uv run` starts Python under it). Match by owner, not title: window titles need Screen Recording permission, and an editor showing the app's name would match. Return `kCGWindowNumber`. |
   | `client_geometry` | `kCGWindowBounds` is the frame in points, title bar included. Measure what the drawable area is against the app's own `WINDOW_GEOMETRY` boot line (as Windows needed, 1ec76c4c) before deciding the arithmetic; see "Open questions". |
   | `bring_to_front` | Activate the owning app (`NSRunningApplication.activateWithOptions_`, or `osascript` on System Events if `ctypes` into AppKit is awkward, which needs Automation permission), then poll the window list until the app's window is frontmost, 2s, as Win32 does. |
   | `move_pointer`, `click` | `CGEventCreateMouseEvent` (moved; left down and up) posted with `CGEventPost(kCGHIDEventTap, ...)`. |
   | `send_key` | `CGEventCreateKeyboardEvent` down and up, posted to the HID tap after `bring_to_front`. A table of X11 keysym names to macOS virtual key codes, covering `VIRTUAL_KEYS`' names: Escape 53, Return 36, Tab 48, BackSpace 51, space 49, Up 126, Down 125, Left 123, Right 124, Delete 117, Home 115, End 119, Prior 116, Next 121. |
   | `send_char` | A key event with `CGEventKeyboardSetUnicodeString`, as Win32's Unicode fallback. |
   | `capture` | Pillow's `ImageGrab.grab(bbox=...)`, which calls `screencapture` on macOS, as Windows uses it. Without Screen Recording permission it captures the wallpaper, not the app, and the blank-frame check fails, which is the right failure. |
   | `process_alive` | `os.kill(pid, 0)`, and reap a zombie child first. |
   | `kill_tree` | Start the app in a session of its own (below) and `os.killpg(pgid, SIGKILL)`, then wait up to `max_secs`, as gui-probe.sh's forced end. |
   | `doctor_checks` | macOS version; `AXIsProcessTrusted()` (FAIL: no Accessibility, no input); `CGPreflightScreenCaptureAccess()` (FAIL: no Screen Recording, blank captures); the screen not locked (`CGSessionCopyCurrentDictionary`); no Barks Reader window open; Pillow; and the renderer: on a machine whose only OpenGL renderer is the software one, FAIL unless the run uses soft GL (step 3). |

2. **The probe's process start.** `Backend.creation_flags` is a Windows idea; `_launch`
   passes it to `Popen(creationflags=...)`, which POSIX ignores, so the app would share
   the probe's process group and get its Ctrl+C. Replace it with a backend method or
   attribute giving `Popen` keyword arguments (`creationflags` on Windows,
   `start_new_session=True` on macOS). Windows' behaviour stays as is.

3. **Soft GL in the run.** `run_gui_tests.py --soft-gl`, beside `--angle`: build
   `build/macos/libsoftgl.dylib` (split `with-soft-gl.sh` so its build half can run alone,
   e.g. `--build-only`) and give it to the app. Not by exporting
   `DYLD_INSERT_LIBRARIES` for `uv run main.py` to pass on: uv since 0.12 is signed with
   the hardened runtime, and macOS strips `DYLD_*` as it starts, so the probe launches
   `uv run env DYLD_INSERT_LIBRARIES=... python main.py`, as `with-soft-gl.sh` does.
   The library only stops SDL insisting on a GPU (a Mac with one still draws on it), so
   it could simply always be on for macOS; have doctor say which renderer the app's log
   names. `--app` with soft GL is out of scope: a signed build may refuse injected
   libraries.

4. **Dispatch.** `gui_probe._backend()` returns the darwin backend; `gui_driver.PROBE`
   picks `gui_probe.py` on `darwin` as on `win32`; the session check in
   `tests/gui/conftest.py` (`sys.platform != "win32"`) lets macOS through as Windows;
   `run_gui_tests.py`'s docstring and usage say macOS too. `check_gui_keys.py` needs
   nothing: the six remote keys are the same.

5. **Unit tests**, in `scripts/tests/test_gui_probe_darwin.py`, running on every platform:
   the key table covers every name `VIRTUAL_KEYS` has (so the two never drift); window
   picking from a canned window list (owner, layer, off-screen, two windows); the
   drawable-area arithmetic; doctor's verdicts from faked checks. Plus the probe change in
   step 2 in `test_gui_probe.py`.

6. **One test green** on the VM: `uv run python scripts/run_gui_tests.py --soft-gl -k
   test_main_screen_fullscreen_round_trip`, with every teardown check (window size kept,
   no blank frame, timing budgets or their skip). Expect the first findings here, as on
   Windows: record each in `docs/plans/gui-test-suite.md`'s status list.

## Milestone B: the whole suite

- Run the suite here test by test, then whole (`--quiet`), and fix what is the harness's
  or the machine's. A real macOS app bug (likeliest: fullscreen and the windowed restore,
  which have no macOS backend in `WindowManager`) gets its own fix and test, not a skip.
- `--calibrate` once: software drawing on 2 cores is far slower than the committed
  budgets assume. If even calibrated budgets are noise here, say so and run this machine
  with `BARKS_GUI_NO_BUDGETS=1`.
- Skip what macOS cannot do, with the reason in the skip: touch (`test_taps.py --touch`
  injects through `uinput`); anything else found.
- The soak, once: `--soft-gl --soak`, watching memory (4 GB guest).

## Milestone C: docs and coverage

- `docs/setup.md`, macOS: the two permissions (System Settings, Privacy & Security,
  Accessibility and Screen Recording, for the program that runs the probe: the terminal
  app it is started from, since macOS asks of the responsible app, not of `python`),
  `caffeinate -d` or Energy Saver so the display does not sleep mid-run, and the command.
- `CLAUDE.md`'s GUI section and `docs/plans/cross-platform-gui-tests.md`'s "What is left",
  item 1 ("macOS window and input coverage needs a real Mac").
- Optional, later: a macOS stage in an overnight runner (as `run_overnight_windows.py`).

## Before starting, on the machine

- `.env.runtime` filled in, then `bash scripts/generate-panel-module.sh` and
  `bash scripts/build.sh` (the two generated modules; without them the app dies on an
  import at boot).
- The data pack under `BARKS_READER_DATA_DIR` ("Reader Files"), and the live profile the
  suite copies from (`barks-reader.ini` in `BARKS_READER_CONFIG_DIR`): the session fixture
  skips the suite without it. Run the app once by hand
  (`bash scripts/macos/with-soft-gl.sh python main.py`) to make the profile and see it
  draw.
- The two permissions above, granted once by hand.
- Unit tests green first: `CI=1 KIVY_DPI=96 KIVY_METRICS_DENSITY=1
  KIVY_METRICS_FONTSCALE=1 bash scripts/macos/with-soft-gl.sh pytest -n auto`.

## Open questions

- **Points and pixels.** `kCGWindowBounds` and CGEvent coordinates are in points; Kivy's
  window size and a `screencapture` image are in pixels. They are equal on the VM (no
  Retina), so milestone A works there; on a Retina Mac they differ by the backing scale.
  Decide which unit `client_geometry` reports (the one `WINDOW_GEOMETRY` logs) and scale
  the rest, before a run on real hardware.
- **The drawable area.** Whether Kivy's window on macOS has the system title bar or the
  app's own, and so what to subtract from the frame: measure, don't assume. First
  measurement (2026-10-01, the VM, from source on soft GL): the app's window in
  `CGWindowListCopyWindowInfo` was `716x1125+442+25`, exactly its log's "Main window
  geometry (boot): 716x1125+442+25", so nothing to subtract there. Its `kCGWindowName`
  came back empty, and a `screencapture` showed only the wallpaper, from a terminal
  without Screen Recording permission: as expected, so match by owner pid.
- **Focus.** Whether `CGEventPost` to the HID tap after activation is enough on every
  macOS version, or `CGEventPostToPid` is needed (which SDL may ignore when its window is
  not the key window). Try the HID tap first.
- **A real Mac.** The VM proves the harness; it does not test the GPU drawing users get.
  One run on real hardware (no `--soft-gl`) once milestone B is green.
