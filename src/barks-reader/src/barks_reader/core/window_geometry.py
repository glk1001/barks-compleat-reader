"""The window geometry's sums: sizes and positions worked out from numbers alone. Kivy-free.

`ui.app_window_geometry` reads Kivy's window and the monitors into the two values
here (`WindowUnits`, how the window measures; `WindowPlace`, where it is) and asks
what follows from them. They are two so that a sum that only converts units costs no
monitor lookup.

Kivy reads the window's size (and gives resize events) in pixels, but takes a size
set on it in ``Window.system_size`` units, the units screeninfo gives the monitors in.
They differ on a Retina Mac, two pixels to a point: a correction worked out in pixels
and set as points doubled the window, again on each correction after (2026-10-14). So
the geometry is worked out in ``system_size`` units; elsewhere the factor is 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .main_layout import size_under_bar

if TYPE_CHECKING:
    from .screen_metrics import ScreenInfo


@dataclass(frozen=True, slots=True)
class WindowUnits:
    """The window's size in its two units, taken at one moment."""

    size_pixels: tuple[int, int]
    """The window's size as Kivy reads it (``Window.size``), in pixels."""

    system_size: tuple[int, int]
    """The window's size in the units a size is set in (``Window.system_size``)."""

    @property
    def pixels_per_size_unit(self) -> float:
        """Pixels to one ``system_size`` unit: 2 on a Retina Mac, 1 elsewhere."""
        system_width = self.system_size[0]
        return self.size_pixels[0] / system_width if system_width > 0 else 1.0

    def in_size_units(self, width: int, height: int) -> tuple[int, int]:
        """Return a size given in pixels (a resize event's) in ``system_size`` units."""
        scale = self.pixels_per_size_unit
        return round(width / scale), round(height / scale)

    def length_in_size_units(self, pixels: int) -> int:
        """Return a length given in pixels (the chrome's height) in ``system_size`` units."""
        return round(pixels / self.pixels_per_size_unit)


@dataclass(frozen=True, slots=True)
class WindowPlace:
    """Where the window is, taken at one moment."""

    left: int
    top: int

    monitor: ScreenInfo | None
    """The monitor the window's top left is on; None when it is on none (off-screen)."""


def centred_if_over(position: int, size: int, monitor_start: int, monitor_size: int) -> int:
    """Return `position`, or the centred one if a window of `size` passes the monitor's end.

    Args:
        position: The window's left or top.
        size: Its width or height.
        monitor_start: The monitor's left or top.
        monitor_size: The monitor's width or height.

    Returns:
        Where the side goes: where it is, or centred, and never before the monitor's
        start (a window larger than its monitor).

    """
    if position + size <= monitor_start + monitor_size:
        return position
    return max(monitor_start, monitor_start + (monitor_size - size) // 2)


def on_monitor_position(place: WindowPlace, width: int, height: int) -> tuple[int, int] | None:
    """Return where a window this size stays on its monitor, or None if it need not move.

    Raised or refitted where it stands, its far edge can pass the monitor's. Only a
    side that does is centred, as a rotation and a layout refit centre the window.

    Args:
        place: Where the window stands.
        width: The width the window is about to take.
        height: The height it is about to take.

    Returns:
        The new left and top, or None: nothing to move, or no monitor to stay on.

    """
    monitor = place.monitor
    if monitor is None:
        return None
    position = (
        centred_if_over(place.left, width, monitor.monitor_x, monitor.width_pixels),
        centred_if_over(place.top, height, monitor.monitor_y, monitor.height_pixels),
    )
    return None if position == (place.left, place.top) else position


def raised_to_minimum(size: tuple[int, int], minimum: tuple[int, int]) -> tuple[int, int]:
    """Return `size` with only its short sides raised to the minimum's.

    For a window that stands, or a resize on its way: the other side is still wanted,
    and the aspect correction then settles the shape.

    Args:
        size: A width and height.
        minimum: The smallest width and height allowed.

    Returns:
        The size, each side no less than the minimum's.

    """
    return max(size[0], minimum[0]), max(size[1], minimum[1])


def held_to_minimum(size: tuple[int, int], minimum: tuple[int, int]) -> tuple[int, int]:
    """Return a size to ask for: `size`, or the whole minimum when either side is below it.

    For a size worked out in the layout's shape: the minimum has that shape too, so a
    size short on one side is short on both, give or take the rounding, and the minimum
    is the size to ask for. SDL would hold the window there anyway.

    Args:
        size: A width and height in the layout's shape.
        minimum: The smallest width and height allowed, in the same shape.

    Returns:
        The size, or the minimum.

    """
    if size[0] >= minimum[0] and size[1] >= minimum[1]:
        return size
    return minimum


def layout_fit_at(
    height: int,
    monitor: ScreenInfo,
    chrome: int,
    aspect_ratio: float,
    minimum: tuple[int, int],
) -> tuple[int, int, int]:
    """Return the layout's width and height at `height`, and its left, centred.

    Args:
        height: The window height to fit, the chrome included.
        monitor: The monitor the window is on: no wider than it, and centred on it.
        chrome: The height of the chrome under the content, in the same units.
        aspect_ratio: The content's height over its width, for the layout.
        minimum: The smallest window allowed.

    Returns:
        The width, the height, and the left that centres that width on the monitor.

    """
    width, fitted_height = held_to_minimum(
        size_under_bar(height, monitor.width_pixels, chrome, aspect_ratio), minimum
    )
    left = monitor.monitor_x + (monitor.width_pixels - width) // 2
    return width, fitted_height, left


def is_degenerate_size(size: tuple[int, int], chrome: int) -> bool:
    """Whether a window size has no content: no width, or no height over the chrome.

    Sizes like ``(0, 45)`` come in events during the Windows fullscreen-exit resize
    storm. A correction worked out from one, and set, is clamped by Win32 to its
    hit-test minimum, and the window stays tiny.
    """
    return size[0] <= 0 or size[1] <= chrome


class AspectCorrectionKind(Enum):
    """What a resize event's size calls for."""

    IN_PROPORTION = auto()
    """The window has the layout's shape: nothing to set."""

    NO_TARGET = auto()
    """There is no size to correct to: the window is on no monitor, so no width is allowed."""

    RESIZE = auto()
    """The window is to be set to the correction's size."""


@dataclass(frozen=True, slots=True)
class AspectCorrection:
    """The answer to a resize event: what to do, and the size it is about."""

    kind: AspectCorrectionKind

    size: tuple[int, int]
    """The size the window should have; for `NO_TARGET`, the degenerate one worked out."""

    held_at_minimum: bool = False
    """Whether the size is the minimum, the layout's size at this height being below it."""


def aspect_correction(
    size: tuple[int, int],
    monitor_width: int,
    chrome: int,
    aspect_ratio: float,
    minimum: tuple[int, int],
) -> AspectCorrection:
    """Return what a window of `size` needs to have the layout's shape: its height drives.

    Every length is in ``Window.system_size`` units. Worked out in pixels and set in
    those units, the correction doubled a Retina window (2026-10-14).

    Args:
        size: The window's size, not degenerate (`is_degenerate_size`).
        monitor_width: The width of the monitor the window is on: the widest it may
            be. 0 when it is on none.
        chrome: The height of the chrome under the content.
        aspect_ratio: The content's height over its width, for the layout.
        minimum: The smallest window allowed.

    Returns:
        The correction: none wanted, none possible, or the size to set.

    """
    target = size_under_bar(size[1], monitor_width, chrome, aspect_ratio)
    if is_degenerate_size(target, chrome):
        return AspectCorrection(AspectCorrectionKind.NO_TARGET, target)

    held = held_to_minimum(target, minimum)
    kind = AspectCorrectionKind.IN_PROPORTION if held == size else AspectCorrectionKind.RESIZE
    return AspectCorrection(kind, held, held_at_minimum=held != target)
