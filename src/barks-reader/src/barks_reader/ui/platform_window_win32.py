"""Win32-specific window save/restore backend.

Necessary on Windows because Kivy/SDL2's window-state APIs leave the window
collapsed at its hit-test minimum after fullscreen exit. This backend uses
``MoveWindow`` + ``GetWindowRect`` for atomic, reliable geometry restoration,
with an ``SDL_SetWindowSize``-based recovery path for the cases where
``MoveWindow`` silently no-ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.core.win32_window import (
    RECT,
    Win32Window,
    find_app_hwnd,
    hold_window_rect,
    release_window_rect,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .platform_window_utils import WindowState

# Windows needs longer than other platforms: SDL fullscreen-exit fires a resize
# storm that can starve the Kivy Clock and leave the window at its hit-test
# minimum before our scheduled restore runs.
_RESTORE_GEOMETRY_TIMEOUT_WIN = 0.25

# Frames move_now retries its MoveWindow for: the first is lost, the second holds.
_MOVE_NOW_ATTEMPTS = 5


class _ScheduledRestore:
    """One restore of the window to a saved state: its frame-by-frame look and delayed move.

    See `Win32WindowBackend.schedule_restore`.
    """

    def __init__(
        self,
        backend: Win32WindowBackend,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> None:
        self._backend = backend
        self._state = state
        self._on_first_resize = on_first_resize
        self._on_done = on_done
        x, y = state.pos
        width, height = state.size
        self._wanted = (x, y, x + width, y + height)
        self._finished = False
        self._looking = True
        self._pending: dict[str, Any] = {}

        # Lambdas, not bound methods: Kivy's Clock holds a bound method weakly, and
        # nothing else holds this object once the callbacks have run.
        self._pending["move"] = Clock.schedule_once(
            lambda _dt: self._move(), _RESTORE_GEOMETRY_TIMEOUT_WIN
        )
        self._pending["look"] = Clock.schedule_once(lambda _dt: self._look(), 0)
        # And at the window's next resize, which is where Kivy learns the exit's
        # size: finishing there, before the screens lay out for it, saves them
        # laying out twice, and a slow frame's wait for the look above.
        Window.bind(on_resize=self._on_window_resize)
        # And now: a window held at the rectangle through the exit is already there,
        # and Kivy has had its resize, inside the call that ended fullscreen.
        self._look(again=False)

    def cancel(self) -> None:
        """Stop whatever is still to come."""
        self._looking = False
        Window.unbind(on_resize=self._on_window_resize)
        for event in self._pending.values():
            event.cancel()

    def _on_window_resize(self, *_args) -> None:  # noqa: ANN002
        if not self._looking or self._finished:
            return
        if self._backend._is_window_at(self._wanted):  # noqa: SLF001
            logger.info(
                f"Win32: Window resized to {self._state.size}, {self._state.pos}:"
                f" finishing the restore at the resize."
            )
            self._finish()

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._looking = False
        self._pending["look"].cancel()
        Window.unbind(on_resize=self._on_window_resize)
        _ = Window.size  # Read to sync Kivy's internal values.
        self._on_first_resize()
        self._on_done()

    def _look(self, *, again: bool = True) -> None:
        if not self._looking:
            return  # the delayed move has taken over
        if self._backend._is_window_at(self._wanted):  # noqa: SLF001
            logger.info(
                f"Win32: Window already at {self._state.size}, {self._state.pos}:"
                f" finishing the restore without waiting."
            )
            self._finish()
        elif again:
            self._pending["look"] = Clock.schedule_once(lambda _dt: self._look(), 0)

    def _move(self) -> None:
        self._looking = False
        Window.unbind(on_resize=self._on_window_resize)
        if "look" in self._pending:
            self._pending["look"].cancel()
        x, y = self._state.pos
        width, height = self._state.size

        # The exit is over, or as over as it gets: what moves the window now is the app.
        self._backend.release_windowed_rect()

        if self._finished:
            # The callbacks ran early and their cancel is gone with them, so a
            # fullscreen transition since then has to be seen here.
            if not Window.fullscreen and not self._backend._is_window_at(self._wanted):  # noqa: SLF001
                logger.warning("Win32: Window moved after its early restore; moving it back.")
                self._backend._set_window_rect(x, y, width, height)  # noqa: SLF001
            return

        # Single atomic Win32 call to set position and size.
        self._backend._set_window_rect(x, y, width, height)  # noqa: SLF001
        # Let Kivy sync its internal state, then fire the callbacks.
        self._pending["finish"] = Clock.schedule_once(lambda _dt: self._finish(), 0)


# noinspection PyCallingNonCallable
class Win32WindowBackend:
    """Save/restore the window via direct Win32 calls."""

    def __init__(self, hwnd: int | None = None) -> None:
        """Bind to the app's window, found by lookup, or to ``hwnd`` when given.

        Args:
            hwnd: A window handle to drive instead of looking up the app's SDL
                window. Only a test passes one, so it drives a window it made
                even when Kivy's own window is open in the same process.

        """
        self._hwnd: int | None = None
        self._move_window: Any = None
        self._get_window_rect: Any = None
        self._get_client_rect: Any = None
        self._init(hwnd)

    def is_available(self) -> bool:
        """Return True if Win32 initialization succeeded and the backend can be used."""
        return self._hwnd is not None

    def save_state(self, state: WindowState) -> None:
        """Populate ``state`` from the current Win32 window rectangle."""
        try:
            window_rect = RECT()
            client_rect = RECT()
            self._get_window_rect(self._hwnd, window_rect)
            self._get_client_rect(self._hwnd, client_rect)

            state.pos = (window_rect.left, window_rect.top)
            state.size = (
                window_rect.right - window_rect.left,
                window_rect.bottom - window_rect.top,
            )

            logger.debug(
                f"Win32: Saved window rect size = ({window_rect.right - window_rect.left},"
                f" {window_rect.bottom - window_rect.top}),"
                f" pos = ({window_rect.left}, {window_rect.top}),"
                f" client size = ({client_rect.right}, {client_rect.bottom})."
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 save state failed, falling back to Kivy: {e}")
            state.save_state_now()

    def hold_windowed_rect(self, state: WindowState) -> None:
        """Keep the window at ``state``'s rectangle through the fullscreen exit to come.

        SDL's exit asks for the window a frame too big (see ``move_now``). The
        window's guard (``core.win32_window``) answers that request, and any other
        until the restore's delayed move, with the saved rectangle, so the wrong
        one is never shown or drawn into. With no guard on the window nothing is
        held, and ``move_now`` puts the window right a frame or two later, as it
        did before there was one.
        """
        if not self._hwnd:
            return
        if hold_window_rect(self._hwnd, (*state.pos, *state.size)):
            logger.debug(f"Win32: Holding the window at {state.size}, {state.pos}.")
        else:
            logger.debug("Win32: The window has no guard to hold it through the exit.")

    def release_windowed_rect(self) -> None:
        """Stop keeping the window at the rectangle held for a fullscreen exit."""
        if self._hwnd:
            release_window_rect(self._hwnd)

    def move_now(self, state: WindowState) -> None:
        """Put the window at ``state``'s rectangle as fullscreen ends, retrying each frame.

        SDL's fullscreen exit sizes the window as its client rectangle plus the
        frame the window style declares, but with the custom titlebar the client
        area fills the whole window (Kivy answers ``WM_NCCALCSIZE`` with 0), so
        the window comes back a frame too big (16x39 at 100% scaling) and shifted
        up by the caption. The first ``MoveWindow`` straight after the exit is
        lost (it blocks while the window finishes the exit, then leaves it where
        it was); the next frame's holds. Measured on a Windows 11 laptop, the
        wrong rectangle shows for ~70ms instead of until the scheduled restore
        (~255ms). No recovery here: the scheduled restore that follows settles it.

        Revisit on Kivy 3.0 (SDL3): if the first resize after "Exiting fullscreen
        mode" is already the saved size, SDL no longer pads the window and this
        can go (see docs/plans/cross-platform-gui-tests.md, "What is left").
        """
        if not self._hwnd:
            return
        x, y = state.pos
        width, height = state.size
        wanted = (x, y, x + width, y + height)

        if self._is_window_at(wanted):
            # Held there through the exit (hold_windowed_rect): a MoveWindow now
            # would only block while the window finishes the exit.
            logger.debug(f"Win32: Window at {state.size}, {state.pos} as fullscreen ends.")
            return

        def attempt(attempts_left: int) -> None:
            if Window.fullscreen or not self._hwnd:
                return  # a fullscreen transition has taken over
            # Best effort: raised into the fullscreen exit that calls this, a failed
            # call left the scheduled restore unscheduled and the transition open.
            try:
                _, rect = self._move_and_read_back(x, y, width, height)
            except Exception as e:  # noqa: BLE001
                logger.error(f"Win32 MoveWindow failed as fullscreen ended: {e}")
                return
            if (rect.left, rect.top, rect.right, rect.bottom) == wanted:
                logger.debug(f"Win32: Window at {state.size}, {state.pos} after fullscreen exit.")
            elif attempts_left > 1:
                Clock.schedule_once(lambda _dt: attempt(attempts_left - 1), 0)

        attempt(_MOVE_NOW_ATTEMPTS)

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> Callable[[], None]:
        """Schedule a restore of the window to ``state``'s saved size and position.

        The move waits out SDL's fullscreen exit (``_RESTORE_GEOMETRY_TIMEOUT_WIN``).
        But ``move_now`` has usually put the window right long before that, and
        until the callbacks run the screen is still laid out for fullscreen, with
        no action bar, in a window that is already the windowed size: on a Windows
        11 desktop that showed for about 260ms and then snapped. So each frame
        until the move is due, the window is looked at, and once it is at the saved
        rectangle the callbacks run. The delayed move is then only a check: it
        moves a window the exit has since shifted, and calls nothing.

        Returns a cancel that stops whichever stages are still pending: the
        frame-by-frame look, the delayed move, or the Kivy-sync step between the
        move and the callbacks. A no-op once the callbacks have run and the
        delayed move's check is done.
        """
        return _ScheduledRestore(self, state, on_first_resize, on_done).cancel

    # --- Private helpers ---

    def _init(self, hwnd: int | None) -> None:
        """Initialize Win32 handles for direct window manipulation."""
        try:
            found_hwnd = hwnd or find_app_hwnd()

            if not found_hwnd:
                logger.warning("Could not get Win32 handle for Kivy window.")
                return

            self._hwnd = found_hwnd

            # A fresh user32, typed for 64-bit handles (core.win32_window); the calls
            # are held here so a test can stand one of them in.
            window = Win32Window(found_hwnd)
            self._move_window = window.move_window
            self._get_window_rect = window.get_window_rect
            self._get_client_rect = window.get_client_rect

            logger.info(f"Win32 window handle initialized: {hex(self._hwnd)}.")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not initialize Win32 handles: {e}")
            self._hwnd = None

    def _is_window_at(self, wanted: tuple[int, int, int, int]) -> bool:
        """Return whether the window's rectangle is ``wanted``: left, top, right, bottom."""
        if not self._hwnd:
            return False
        try:
            rect = RECT()
            self._get_window_rect(self._hwnd, rect)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 GetWindowRect failed: {e}")
            return False
        return (rect.left, rect.top, rect.right, rect.bottom) == wanted

    def _move_and_read_back(self, x: int, y: int, width: int, height: int) -> tuple[Any, RECT]:
        """Call ``MoveWindow``, then ``GetWindowRect``: the move's result and where the window is.

        The move can return success and leave the window where it was, so every
        caller reads the rectangle back; what each makes of a mismatch is its own.
        """
        result = self._move_window(self._hwnd, x, y, width, height, True)  # noqa: FBT003
        rect = RECT()
        self._get_window_rect(self._hwnd, rect)
        return result, rect

    def _set_window_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Set window position and size using the Win32 ``MoveWindow`` API.

        On Windows, SDL2's fullscreen-exit path can fire a storm of resize events that
        starve the Kivy Clock and leave the window collapsed at its hit-test minimum
        (e.g. ``(136, 45)`` -- the action bar's minimum content size) before our scheduled
        ``MoveWindow`` even runs. In that state ``MoveWindow`` can return success but be
        a no-op.

        Recovery strategy when the post-``MoveWindow`` rect doesn't match the request:
          1. Set ``Window.size`` / ``Window.left`` / ``Window.top`` via Kivy. This goes
             through ``SDL_SetWindowSize`` and bypasses whatever sticky Win32 state was
             blocking ``MoveWindow``.
          2. Schedule a deferred ``MoveWindow`` retry on the next frame so the Win32
             outer rect matches the saved state once SDL has settled.
        """
        if not self._hwnd:
            return

        try:
            # Read back to verify the operation succeeded.
            result, actual_rect = self._move_and_read_back(x, y, width, height)
            actual_w = actual_rect.right - actual_rect.left
            actual_h = actual_rect.bottom - actual_rect.top

            mismatch = (actual_w, actual_h) != (width, height)
            log_func = logger.warning if mismatch else logger.info

            log_func(
                f"Win32: Requested size = ({width}, {height}); "
                f" Actual size = ({actual_w}, {actual_h}); "
                f" Requested pos = ({x}, {y});"
                f" Actual pos = ({actual_rect.left}, {actual_rect.top}), "
                f"Result = {result}."
            )

            if mismatch:
                self._recover_from_failed_move(x, y, width, height)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Win32 MoveWindow failed: {e}")

    def _recover_from_failed_move(self, x: int, y: int, width: int, height: int) -> None:
        """Fallback when ``MoveWindow`` returns success but the window stays at the wrong size.

        Uses Kivy's Window properties (which go through ``SDL_SetWindowSize``) to break
        the sticky state, then schedules a deferred ``MoveWindow`` retry to confirm the
        outer Win32 rect matches the saved state.
        """
        logger.warning(
            f"Win32 MoveWindow no-op detected; recovering via Window.size = ({width}, {height})."
        )
        try:
            Window.size = (width, height)
            Window.left = x
            Window.top = y
        except Exception as e:  # noqa: BLE001
            logger.error(f"Window.size recovery failed: {e}")

        def retry(_dt: float) -> None:
            if not self._hwnd:
                return
            _, actual_rect = self._move_and_read_back(x, y, width, height)
            logger.info(
                f"Win32 retry: Requested size = ({width}, {height}); "
                f" Actual size = ({actual_rect.right - actual_rect.left},"
                f" {actual_rect.bottom - actual_rect.top}); "
                f" Actual pos = ({actual_rect.left}, {actual_rect.top})."
            )

        Clock.schedule_once(retry, 0)
