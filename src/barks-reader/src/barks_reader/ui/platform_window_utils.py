from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.core.platform_info import PLATFORM, Platform
from barks_reader.core.screen_metrics import SCREEN_METRICS

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget

# Small timeout for non-Windows platforms to let the window system settle.
_RESTORE_GEOMETRY_TIMEOUT = 0.05


class FullscreenEnum(Enum):
    FULLSCREEN = "fullscreen"
    WINDOWED = "windowed"


@dataclass(frozen=True, slots=True)
class WindowModeCallbacks:
    """The per-screen completion callbacks for one window-mode transition.

    Passed to ``WindowManager.goto_fullscreen_mode`` / ``goto_windowed_mode`` on
    each call rather than baked into the manager, so a single shared
    ``WindowManager`` can serve multiple screens.
    """

    on_windowed_first_resize: Callable[[], None]
    on_finished_windowed: Callable[[], None]
    on_finished_fullscreen: Callable[[], None]


@dataclass(slots=True)
class WindowState:
    screen: FullscreenEnum = FullscreenEnum.WINDOWED
    size: tuple[int, int] = (0, 0)
    pos: tuple[int, int] = (-1, -1)

    def save_state_now(self) -> None:
        self.screen = FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED
        self.size = Window.size
        self.pos = (Window.left, Window.top)

    def is_saved_state_same_as_current(self) -> bool:
        return Window.size == self.size and (Window.left, Window.top) == self.pos

    def is_unsaved(self) -> bool:
        """Return True while no geometry has been captured (still the defaults).

        ``goto_fullscreen_mode`` skips its save when the window is *already*
        fullscreen (e.g. at app start), so a later windowed restore can be
        reached with nothing to restore. Restoring the sentinel would apply a
        nonsense size/position, so the restore guards on this.
        """
        return self.size == (0, 0) or self.pos == (-1, -1)

    @staticmethod
    def get_current_screen_mode() -> FullscreenEnum:
        return FullscreenEnum.FULLSCREEN if Window.fullscreen else FullscreenEnum.WINDOWED


class WindowBackend(Protocol):
    """Platform-specific save/restore for the application window."""

    def save_state(self, state: WindowState) -> None:
        """Populate ``state`` with the current window geometry."""
        ...

    def schedule_restore(
        self,
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> Callable[[], None]:
        """Schedule a restore of the window to ``state``'s saved geometry.

        ``on_first_resize`` is invoked once the resize has been issued (used by callers
        to apply size hints), and ``on_done`` is invoked once the restore has settled.

        Returns a zero-arg cancel: called while the restore is still pending it
        stops the resize and its callbacks (a fullscreen transition superseding
        the windowed one); calling it after the restore has fired is a no-op.
        """
        ...


class KivyWindowBackend:
    """Default backend that uses Kivy's ``Window`` properties.

    Used on Linux/Mac and as a fallback when Win32 initialization fails.
    """

    @staticmethod
    def save_state(state: WindowState) -> None:
        state.save_state_now()

    @staticmethod
    def schedule_restore(
        state: WindowState,
        on_first_resize: Callable[[], None],
        on_done: Callable[[], None],
    ) -> Callable[[], None]:
        def restore(*_args) -> None:  # noqa: ANN002
            Window.size = state.size
            Window.left, Window.top = state.pos
            on_first_resize()
            on_done()

        return Clock.schedule_once(restore, _RESTORE_GEOMETRY_TIMEOUT).cancel


def set_titlebar_drag_region(drag_region: Widget) -> None:
    """Point the OS window-drag hit test at ``drag_region``.

    With the OS titlebar replaced (``Window.custom_titlebar``), SDL asks per
    click whether the point falls inside the registered widget — using that
    widget's live window coordinates regardless of which Screen is showing.
    A screen whose top bar lays out differently from the registered one gets
    phantom drag zones that swallow clicks over its own buttons, so every
    top-level screen must register its own drag region when it takes over the
    window, and the region must be swapped back when it leaves.

    A no-op when the custom titlebar isn't active (the OS titlebar survived).
    """
    if not Window.custom_titlebar:
        return
    if not Window.set_custom_titlebar(drag_region):
        logger.warning("Window: setting the custom-titlebar drag region failed.")


def _create_window_backend() -> WindowBackend:
    """Return the best available backend for the current platform."""
    if PLATFORM == Platform.WIN:
        # Lazy import to keep the Win32 module out of import graphs on other platforms.
        from .platform_window_win32 import Win32WindowBackend  # noqa: PLC0415

        win32_backend = Win32WindowBackend()
        if win32_backend.is_available():
            return win32_backend
        logger.warning("Win32 backend unavailable; falling back to Kivy backend.")
    return KivyWindowBackend()


class WindowManager:
    """Owns fullscreen/windowed transitions and the saved windowed geometry.

    One instance is shared by all screens (a single geometry store). Each
    ``goto_*`` call carries the calling screen's ``WindowModeCallbacks``, and
    every Clock-deferred step of the transition captures that bundle by
    closure — so a transition always completes with the callbacks of the
    screen that started it, even if another screen starts a transition while
    this one's chain is still in flight.
    """

    def __init__(self) -> None:
        # Number of windowed transitions whose geometry restore has not yet
        # settled. While non-zero the current Window geometry is transitional
        # (typically still monitor-sized), so it must not be saved as the
        # windowed geometry.
        self._pending_restores = 0

        # Heading of an in-flight transition (True = fullscreen), None when
        # settled. The actual ``Window.fullscreen`` flip lands a frame after a
        # ``goto_*`` call, so during that frame the actual state still reads as
        # the *old* mode; anything deciding a direction (``toggle``) must ask
        # ``is_fullscreen_target`` instead. The sequence number lets an older
        # overlapped transition finish without erasing a newer command's heading.
        self._target_fullscreen: bool | None = None
        self._transition_seq = 0

        # Cancel handles for backend restores that are scheduled but have not
        # fired. A fullscreen transition cancels these so a stale restore
        # cannot resize the now-fullscreen window; a restore that completes
        # normally removes its own entry (see restore_saved_size_and_position).
        # Each entry is a one-element list: the holder is registered before the
        # backend call, so a backend that completes synchronously can still
        # find and remove it.
        self._scheduled_restore_cancels: list[list[Callable[[], None]]] = []

        self._saved_window_state = WindowState()
        self._backend: WindowBackend = _create_window_backend()

    @staticmethod
    def is_fullscreen_now() -> bool:
        return Window.fullscreen

    def is_fullscreen_target(self) -> bool:
        """Return the mode the window is heading to.

        The in-flight transition's target when one is pending, else the actual
        current mode. This is the read ``toggle`` needs: two rapid presses must
        resolve as "go, then come back", not twice in the first direction.
        """
        if self._target_fullscreen is not None:
            return self._target_fullscreen
        return self.is_fullscreen_now()

    def _begin_transition(self, *, target_fullscreen: bool) -> int:
        """Record a new transition's heading; returns its sequence token."""
        self._transition_seq += 1
        self._target_fullscreen = target_fullscreen
        return self._transition_seq

    def _end_transition(self, seq: int) -> None:
        """Clear the heading once the window state reflects it — latest command only."""
        if seq == self._transition_seq:
            self._target_fullscreen = None

    @staticmethod
    def get_screen_mode_now() -> str:
        return WindowState.get_current_screen_mode().value

    def save_state_now(self) -> None:
        self._backend.save_state(self._saved_window_state)
        logger.info(
            f"Saved window state: size = {self._saved_window_state.size}, "
            f"pos = {self._saved_window_state.pos}"
        )

    def goto_fullscreen_mode(self, callbacks: WindowModeCallbacks) -> None:
        """Enter fullscreen mode, saving the windowed geometry first.

        Args:
            callbacks: The calling screen's completion callbacks for this
                transition.

        """
        if self.is_fullscreen_target():
            if self.is_fullscreen_now():
                callbacks.on_finished_fullscreen()
            else:
                # Already heading fullscreen: land the finish after the pending
                # flip (Clock callbacks run FIFO) instead of starting a duplicate.
                Clock.schedule_once(lambda _dt: callbacks.on_finished_fullscreen(), 0)
            return

        if self._pending_restores > 0:
            # A windowed restore is still in flight, so the current geometry is
            # transitional. The store already holds the real windowed geometry;
            # saving now would overwrite it with the un-restored values.
            logger.warning("Windowed restore still in flight; keeping saved geometry.")
            # This fullscreen transition supersedes those restores: cancel any
            # already scheduled at the backend so a stale restore cannot fire
            # later and resize the fullscreen window. Restores not yet at the
            # backend retire themselves via restore_saved_size_and_position's
            # target check.
            self._cancel_scheduled_restores()
        else:
            self.save_state_now()

        seq = self._begin_transition(target_fullscreen=True)

        def do_fullscreen() -> None:
            Window.fullscreen = "auto"  # Use 'auto' for best platform behavior
            self._end_transition(seq)
            Clock.schedule_once(lambda _dt: callbacks.on_finished_fullscreen(), 0)

        Clock.schedule_once(lambda _dt: do_fullscreen(), 0)

    def goto_windowed_mode(self, callbacks: WindowModeCallbacks) -> None:
        """Exit fullscreen and restore the saved windowed geometry.

        Args:
            callbacks: The calling screen's completion callbacks for this
                transition.

        """
        if not self.is_fullscreen_target():
            if not self.is_fullscreen_now():
                callbacks.on_finished_windowed()
            else:
                # Already heading windowed: land the finish after the pending
                # flip (Clock callbacks run FIFO) instead of starting a duplicate.
                Clock.schedule_once(lambda _dt: callbacks.on_finished_windowed(), 0)
            return

        self._pending_restores += 1
        seq = self._begin_transition(target_fullscreen=False)

        def do_windowed() -> None:
            Window.borderless = False  # safest thing to do for MS Windows
            Window.fullscreen = False
            self._end_transition(seq)
            Clock.schedule_once(lambda _dt: self.restore_saved_size_and_position(callbacks), 0)

        Clock.schedule_once(lambda _dt: do_windowed(), 0)

    def restore_saved_size_and_position(self, callbacks: WindowModeCallbacks) -> None:
        """Restore the saved geometry, then finish the windowed transition.

        Args:
            callbacks: The transition's completion callbacks.

        """
        if self.is_fullscreen_target():
            # A fullscreen transition superseded this windowed transition before
            # its restore reached the backend (goto_fullscreen_mode cancels the
            # scheduled ones, but this step can still be sitting in the Clock
            # queue behind it). Resizing now would fight the fullscreen window,
            # so retire the transition without a windowed completion — the same
            # policy as _finish_restore's fullscreen guard.
            logger.warning("Window heading fullscreen; skipping superseded restore.")
            self._pending_restores = max(0, self._pending_restores - 1)
            return

        state = self._saved_window_state
        if state.is_unsaved():
            # Nothing was captured before going fullscreen (the app started
            # already fullscreen, so goto_fullscreen_mode's save was skipped).
            # Restoring the sentinel would move the window to a nonsense
            # size/position, so leave the current geometry untouched and just
            # finish the windowed transition: apply the windowed size hints and
            # fire the completion callback, as the settled restore path does.
            logger.warning(
                f"No saved window state to restore "
                f"(size = {state.size}, pos = {state.pos}); leaving current geometry."
            )
            self._pending_restores = max(0, self._pending_restores - 1)
            callbacks.on_windowed_first_resize()
            Clock.schedule_once(lambda _dt: callbacks.on_finished_windowed(), 0)
            return

        logger.info(f"Restoring window: target size = {state.size}, pos = {state.pos}")
        logger.info(
            f"At the start of restoring window state,"
            f" Window.size = {Window.size}, pos = ({Window.left}, {Window.top})."
        )

        # Registered before the backend call so a synchronously-completing
        # backend's on_done can already find (and remove) its own entry.
        cancel_holder: list[Callable[[], None]] = []
        self._scheduled_restore_cancels.append(cancel_holder)

        def on_done() -> None:
            if cancel_holder in self._scheduled_restore_cancels:
                self._scheduled_restore_cancels.remove(cancel_holder)
            self._finish_restore(callbacks)

        cancel_holder.append(
            self._backend.schedule_restore(state, callbacks.on_windowed_first_resize, on_done)
        )

    def _cancel_scheduled_restores(self) -> None:
        """Cancel every backend restore still pending; the transitions retire here.

        Each cancelled restore's callbacks will never run, so its windowed
        transition is accounted for now (the ``max`` guards against a stale
        ``on_done`` from a backend event that had already fired by the time it
        was cancelled — _finish_restore's fullscreen check absorbs those).
        """
        for cancel_holder in self._scheduled_restore_cancels:
            if cancel_holder:
                cancel_holder[0]()
            self._pending_restores = max(0, self._pending_restores - 1)
            logger.info("Cancelled a scheduled windowed restore (superseded by fullscreen).")
        self._scheduled_restore_cancels.clear()

    def _finish_restore(self, callbacks: WindowModeCallbacks) -> None:
        """Log final state and call the windowed-mode completion callback."""
        self._pending_restores = max(0, self._pending_restores - 1)

        if self.is_fullscreen_now():
            # A fullscreen transition interrupted this restore and owns the
            # window now; reporting a windowed completion would leave the
            # calling screen's mode state inverted.
            logger.warning("Window went fullscreen during restore; skipping windowed finish.")
            return

        log_func = (
            logger.info
            if self._saved_window_state.is_saved_state_same_as_current()
            else logger.warning
        )

        log_func(
            f"Window restore complete: size = {Window.size},"
            f" pos = ({Window.left}, {Window.top}); "
            f"Target was size = {self._saved_window_state.size},"
            f" pos = {self._saved_window_state.pos}"
        )

        Clock.schedule_once(lambda _dt: callbacks.on_finished_windowed(), 0)


class WindowModeController:
    """Per-screen fullscreen/windowed toggle scaffolding over a shared WindowManager.

    Both the main screen and the comic reader drive their mode switches through
    one of these, so the toggle policy (which direction to go) lives in one
    place. The screen-specific completion behaviour stays on the screen,
    delivered via the injected ``callbacks`` bundle; ``client`` only labels the
    logs.
    """

    def __init__(
        self,
        client: str,
        window_manager: WindowManager,
        callbacks: WindowModeCallbacks,
    ) -> None:
        self._client = client
        self._window_manager = window_manager
        self._callbacks = callbacks

    def toggle(self) -> None:
        """Switch to the opposite mode.

        Reads the manager's *target* mode, not the settled one: the actual
        ``Window.fullscreen`` flip lands a frame after a ``goto_*``, so a
        second rapid press reading the settled state would repeat the first
        press's direction instead of toggling back. No deferral here: the
        manager already defers the actual ``Window`` mutation to the next
        frame, so an extra hop would only let the mode read go stale.
        """
        if self._window_manager.is_fullscreen_target():
            self.goto_windowed()
        else:
            self.goto_fullscreen()

    def force_fullscreen(self) -> None:
        """Enter fullscreen, regardless of current mode."""
        self.goto_fullscreen()

    def goto_fullscreen(self) -> None:
        """Enter fullscreen via the shared manager, with this screen's callbacks."""
        logger.info(f"{self._client}: Entering fullscreen mode.")
        self._window_manager.goto_fullscreen_mode(self._callbacks)

    def goto_windowed(self) -> None:
        """Exit to windowed mode via the shared manager, with this screen's callbacks."""
        logger.info(f"{self._client}: Exiting fullscreen mode.")
        self._window_manager.goto_windowed_mode(self._callbacks)


def log_screen_metrics() -> None:
    from kivy.metrics import cm, dp, inch, sp  # noqa: PLC0415

    logger.info("--- Detailed Monitor Metrics ---")

    for info in SCREEN_METRICS.SCREEN_INFO:
        logger.info(
            f"Display {info.display}: {info.width_pixels} x {info.height_pixels} pixels"
            f" at ({info.monitor_x}, {info.monitor_y})."
        )
        logger.info(
            f"  -> Physical Size: {info.width_mm}mm x {info.height_mm}mm"
            f" ({info.width_in:.2f}in x {info.height_in:.2f}in)."
        )
        logger.info(f"  -> Calculated DPI: {info.dpi:.2f}.")
        logger.info(f"  -> Primary: {info.is_primary}.")

    logger.info(f"1 cm = {cm(1):.1f} pixels.")
    logger.info(f"1 in = {inch(1):.1f} pixels.")
    logger.info(f"100 dp = {dp(100):.1f} pixels.")
    logger.info(f"100 sp = {sp(100):.1f} pixels.")

    logger.info("--------------------------------")


if __name__ == "__main__":
    log_screen_metrics()
