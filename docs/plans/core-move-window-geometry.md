# Plan: the window geometry sums into `core`

> Status: **proposed 2026-11-22**, nothing started. One of four plans from the
> `ui` review of that date (see `core-move-navigation-coordinator.md`).

## Context

`AppWindowGeometryHelper` (`ui/app_window_geometry.py`, about 760 lines) keeps the
main window in the layout's shape: the aspect-ratio correction after a resize, the
refit when the layout changes, the minimum size, the move to another monitor, the
rotation. It reads Kivy's `Window` or `SCREEN_METRICS` in over fifty places, and
its arithmetic is written between those reads.

The arithmetic takes only numbers:

| Method | The sum inside it |
|---|---|
| `_layout_fit_at` | the layout's width and height at a height, raised to the minimum, and its left when centred on the monitor |
| `_enforce_aspect_ratio` | from a resize event in pixels: the size in window units, whether it is degenerate, the corrected size, whether a correction is needed |
| `_raise_to_minimum` | a size with only its short sides raised |
| `_on_monitor_position`, `_centred_if_over` | where a window stays on its monitor, a side centred only if it passes the end |
| `_pixels_per_size_unit`, `_in_size_units`, `_chrome_in_size_units` | pixels to `Window.system_size` units (two to one on a Retina Mac) |
| `_handle_rotation` | the fitted size and centre on the rotated monitor |

Two regressions were sums of this kind and were found on other machines, late:

- the Retina doubling (2026-10-14): a correction worked out in pixels and set in
  points;
- the Windows frame growth (2026-11-17): each correction worked out from a height
  the frame had already enlarged.

Both are now pinned by tests in `tests/unit/test_app_window_geometry.py`, which
patch `Window`, `Clock` and `SCREEN_METRICS` to reach the sum.

Related, and small: "fit the content under a bar" is written out in six places as
`get_win_dimensions(height - bar, max_width, ratio)` then `content_h + bar`
(`ui/app_window_geometry.py` twice, `ui/main_screen_window.py`,
`ui/wiki_reader.py`, and twice in `core/screen_metrics.py`);
`ui/comic_book_reader.py` has the first half.

## Goal

The sums are pure functions in `core`, each tested by numbers alone, including the
two regressions above as plain cases. `AppWindowGeometryHelper` keeps the reads of
`Window`, the scheduling, the guards and the flags, and calls the functions.
Behaviour does not change.

## Approach

### 1. One function for "under a bar"

In `core/main_layout.py`:

```python
def size_under_bar(height: int, max_width: int, bar_height: int, aspect_ratio: float) -> tuple[int, int]
```

It returns the whole width and height. The six places call it. This is a commit of
its own, before the rest, and the least risky.

### 2. A value for what the sums read

New `core/window_geometry.py` with a frozen `WindowFacts`: the window's size in
pixels and in system units, its left and top, and the monitor it is on (a
`ScreenInfo`, or None when off every monitor). The helper builds one from `Window`
and `SCREEN_METRICS` at the top of each handler. Nothing in `core` reads `Window`.

### 3. The sums, one at a time

In `core/window_geometry.py`, each moved with its comment and given direct tests:

- `pixels_per_size_unit`, `in_size_units`
- `centred_if_over`, `on_monitor_position`
- `raised_to_minimum` (short sides only)
- `layout_fit_at` (height, monitor, chrome, ratio, minimum)
- `aspect_correction`, returning one of: nothing to do, degenerate (skip), or the
  size to set. The helper keeps the debounce, the "window moved on since" check
  and the font update.
- `rotation_fit`

The helper's methods of the same names become one-line calls, or go where they had
no other caller.

### 4. Tests

The existing helper tests stay: they pin the sequencing (the guard, the debounce,
the pending refit). The cases in them that exist to reach a sum move to
`tests/unit/test_window_geometry.py` as tables of numbers, the Retina and
frame-growth cases first.

## Commits

1. `size_under_bar` and its six callers.
2. `WindowFacts`, the units and the monitor-position functions.
3. `layout_fit_at` and `raised_to_minimum`.
4. `aspect_correction`.
5. `rotation_fit`.

Each is green on its own.

## Verification beyond the gates

The unit and GUI suites on this PC cover X11 only. After commits 3 and 4:

- the overnight round's Windows and macOS machines run the GUI suite and the soak,
  where both regressions were first seen; read their results before going on
- by hand on this PC: resize by a corner, toggle fullscreen in each layout, move to
  the other monitor

No commit of this plan should go out on a day when the overnight round is not
going to run.

## Not in this plan

`WindowManager` and the Win32 backend (`ui/platform_window_utils.py`,
`ui/platform_window_win32.py`). Their state is already a value in
`core/window_state.py`; what remains there is sequencing against the platform, not
sums.

## Questions

1. `aspect_correction` returning a three-way result: a small enum plus a size, or
   `None` / a sentinel? An enum reads better in the helper's log lines.
2. Is one commit a night acceptable for 3 to 5, so each gets its own overnight
   result on Windows and macOS?
