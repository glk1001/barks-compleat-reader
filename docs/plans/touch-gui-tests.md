# Plan: GUI tests for a touchscreen laptop

> Status: **agreed 2026-09-25**, Linux done. Taps are by click everywhere, headless
> and in parallel. Real touch is a layer on top (`--touch`), green on Linux; Windows
> touch comes later.
>
> - Tap targets: DONE 2026-09-25. The app tells a test where its tappable widgets
>   are; nothing is tapped by a pixel the test worked out.
> - Tap tests: DONE 2026-09-25. `test_taps.py` has 11 tests, all green by click
>   (headless, 4 workers, 51s). The whole suite, 73 tests, passes with them.
> - Touch mode on Linux: DONE 2026-09-25, on the touchscreen Ubuntu laptop with the
>   udev rule installed. `bash scripts/run_gui_tests.sh --headless --touch -k test_taps`:
>   11 passed in 3m16s (one worker). The app registered the test touchscreen beside
>   the laptop's own panel; the margin taps turned one page each with the app
>   swallowing the touch events; the search box logged a touch tap and showed the
>   virtual keyboard. The default 0.05s touch lead needed no tuning. Select the tap
>   tests with `-k`: a path argument is added to the suite directory, not put in
>   its place, so it runs the whole suite on one worker (about 12 minutes).
>
> **What is left:**
> 1. Windows touch: `InitializeTouchInjection` / `InjectTouchInput` behind the
>    Windows probe's `tap`, which clicks for now and refuses `BARKS_PROBE_TOUCH`.
>    Unlike Linux, a Windows touch reaches the app as a touch (Kivy's `wm_touch`
>    provider), not only as a pointer press, so it can double a tap there. Run the
>    tap tests on the Windows touchscreen laptop, by click first.

## What the user asked for

Page-turn taps (the comic reader's margins, the fun view's, a document's halves);
the fullscreen top-margin tap that shows the hidden bar; the search box's virtual
keyboard, which shows only for a real touch; tap-to-navigate (tree nodes, menu
buttons, popups, and a tap leaving keyboard menu mode); and tapping items in the
main index and the speech-bubble index.

## How a touch reaches the app

The app treats touch as mouse input: every `on_touch_down` is a tap or a click, and
none tells the two apart. There is no swipe, pinch, long press or double tap.

- **Linux.** SDL turns a finger into a pointer press, so widgets see a click. The
  app reads touchscreens itself only with the virtual keyboard setting on
  (`touch_keyboard.py`): it registers Kivy's mtdev provider for each one, swallows
  their events before any widget sees them, and keeps the time of the last one. A
  press within 0.15s of a hardware touch is a tap, and only a tap shows the virtual
  keyboard. The swallowing is also what stops one touch acting twice, once as a
  touch and once as its pointer press.
- **Windows.** Kivy's config loads `wm_touch`, so a touch reaches widgets as a touch
  as well as whatever pointer press Windows makes of it. Not covered yet.

So on Linux a click is exactly what a touch is to the widgets, with the virtual
keyboard setting off. Touch mode adds the other path: the setting on, a real
touchscreen event, and the click after it.

## Tap targets

`barks_reader.core.tap_targets` (no Kivy) and `barks_reader.ui.tap_targets`:

- The probe sets `BARKS_READER_TAP_TARGETS_FILE` to `tap-request` in its run
  directory. Unset, which is every normal run, the app never looks.
- A test writes a request id there (`gui-probe.sh tap-targets ID`, written whole
  and renamed). The app polls ten times a second and answers with one log line:
  `Tap targets #ID: WxH [...]`. The JSON lists each target's class, text, kv id and
  window rectangle, with the origin top-left.
- **Targets:** buttons (tree nodes, index items and menu entries are all buttons),
  tree nodes, text inputs, the virtual keyboard, and an open popup's panel. A
  widget can also name regions of itself with `tap_target_regions()`: the reader's
  left, right and top margins (from `ReaderNavigation.tap_regions`, unit-tested
  against its own `is_in_*` checks), the fun view's margins, and a document's two
  halves.
- **Visible only.** A target is clipped to every scroll view above it and to the
  window. A hidden or disabled widget, and everything in it, is left out; so is
  everything under an open popup.
- **Answered when still.** The app answers only when two polls running took the
  same list, and never while `layout_settling()`. Two polls were not enough: the
  tree's scroll pinner corrects a few frames after an expand, and on a loaded
  machine (four workers) the uncorrected tree held still past two polls. A tap
  then landed a row off. The pinner now marks itself settling from the expand until
  its correction lands.
- **In the tests** (`barks_gui/taps.py`): `taps.tap(d, text=, kind=, kv_id=)`,
  `tap_then_wait`, and `tap_outside` for a popup that closes on an outside tap. A
  miss fails listing everything on screen, which is how the names in `test_taps.py`
  were found.

### Found on the way

- Kivy's window is its own `parent`, so a walk up the widget tree must stop there
  (the first version hung the app's clock).
- In fullscreen with no window manager, the probe's `geometry` keeps reporting the
  windowed size while the app reports the screen's. A tap scaled by that ratio
  missed its button, so taps use the app's pixels unscaled: they are the X
  server's.

## Touch mode (Linux)

- `scripts/gui_touch.py` (stdlib only) creates "Barks GUI Test Touchscreen" through
  `/dev/uinput`, before the app boots, and serves `down X Y` and `up` on a unix
  socket in the run directory.
- In touch mode `gui-probe.sh tap` sends a finger press, then the click SDL would
  have made of it, then the lift (the click's press and release around it).
- The tap tests boot with `use_virtual_keyboard=1` in touch mode, so the app reads
  the device. The margin test then checks one page per tap, with the swallowing
  path live.
- The device is system-wide, and every app reads it, so `--touch` runs one worker.
- `scripts/udev/70-barks-gui-touch.rules`, installed once:
  ```bash
  sudo cp scripts/udev/70-barks-gui-touch.rules /etc/udev/rules.d/
  sudo udevadm control --reload
  sudo udevadm trigger --action=change --sysname-match=uinput
  ```
  It lets the `input` group open `/dev/uinput`, and sets `LIBINPUT_IGNORE_DEVICE`
  on the test touchscreen, so the desktop never acts on its taps.
  `BARKS_PROBE_TOUCH=1 bash scripts/gui-probe.sh doctor` checks both. Anyone in the
  `input` group can already read every keyboard; the rule lets them make one too.

## The tests (`src/barks-reader/tests/gui/test_taps.py`)

| Test | What it taps |
|---|---|
| tree nodes | Chronological and 1947-1950 shut and open, then a title |
| margin taps | the reader's right then left margin: one page each, never two |
| menu mode | Escape into the reader's menu mode, then a margin tap leaves it |
| fullscreen | Fullscreen, the top margin to show the bar, then Windowed |
| fun view | Change Pics, then the fun view's left and right margins |
| document | a document's tree node, its right half, then its left half, then Close |
| About | the dots menu, About, then its X |
| Quit | Quit, then Stay: the app stays up |
| main index | the letter B, then an item: a B title, selected in the tree |
| speech index | B, a prefix, a term, a speech button, then outside the popup |
| search box | the box, with the virtual keyboard on: a click keeps the system keyboard, a touch shows the virtual one |

The search box test is the one that changes with the mode. The rest pass the same
either way, and in touch mode they also run with the app reading the touchscreen.
