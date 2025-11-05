import sys
import os
import traceback
import logging
import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.base import runTouchApp, stopTouchApp, EventLoop
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


# ----------------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app_crash.log", encoding="utf-8", mode="a"),
    ],
)


# ----------------------------------------------------------------------------
# Popup creation utilities
# ----------------------------------------------------------------------------


def _make_popup(message: str, restart_callback=None) -> Popup:
    """Build an error popup with optional Restart button."""
    layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
    label = Label(text=message, halign="center", valign="middle")

    layout.add_widget(label)

    btn_row = BoxLayout(size_hint_y=None, height=50, spacing=10)
    btn_close = Button(text="Close", on_release=lambda *_: stopTouchApp())

    if restart_callback:
        btn_restart = Button(text="Restart", on_release=lambda *_: restart_callback())
        btn_row.add_widget(btn_restart)

    btn_row.add_widget(btn_close)
    layout.add_widget(btn_row)

    return Popup(
        title="Application Error",
        content=layout,
        size_hint=(0.8, 0.6),
        auto_dismiss=False,
    )


def _restart_app():
    """Restart this same Python process cleanly."""
    python = sys.executable
    args = sys.argv
    logger.warning(f"Restarting app: {python} {' '.join(args)}")
    os.execl(python, python, *args)  # replaces current process


def _show_popup_in_running_app(message: str):
    """Show popup inside running Kivy loop."""

    def _show(*_):
        popup = _make_popup(message, restart_callback=_restart_app)
        popup.open()

    Clock.schedule_once(_show, 0)


def _show_popup_with_temporary_loop(message: str):
    """Start temporary Kivy loop to show popup even if main loop is dead."""

    def _show(*_):
        popup = _make_popup(message, restart_callback=_restart_app)
        popup.bind(on_dismiss=lambda *_: stopTouchApp())
        popup.open()

    try:
        logger.warning("Starting temporary Kivy loop for standalone popup...")
        Clock.schedule_once(_show, 0)
        runTouchApp()
    except Exception as e:
        logger.critical(f"Failed to start temporary loop: {e}")
        print(f"[CRITICAL] {message}", file=sys.stderr)


def show_error_popup(message: str) -> None:
    """Show popup using running loop, or start temporary one if needed."""
    try:
        app = App.get_running_app()
        if app and EventLoop.status == "started":
            _show_popup_in_running_app(message)
        else:
            _show_popup_with_temporary_loop(message)
    except Exception as e:
        logger.critical(f"Popup system failed: {e}")
        print(f"[CRITICAL] {message}", file=sys.stderr)


# ----------------------------------------------------------------------------
# Global exception hooks
# ----------------------------------------------------------------------------


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Catch and display any uncaught exception (main thread)."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    message = f"Uncaught exception:\n{exc_value}\n\n{tb_str}"
    logger.critical(message)
    show_error_popup(message)


sys.excepthook = handle_uncaught_exception


def handle_thread_exception(args):
    """Handle background thread exceptions."""
    handle_uncaught_exception(args.exc_type, args.exc_value, args.exc_traceback)


threading.excepthook = handle_thread_exception


# ----------------------------------------------------------------------------
# Example Kivy App to demonstrate the system
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    from kivy.uix.label import Label
    from kivy.clock import Clock

    class MyApp(App):
        def build(self):
            Clock.schedule_once(lambda dt: 1 / 0, 2)  # deliberate crash
            return Label(text="Hello — will crash in 2s!")

    try:
        MyApp().run()
    except Exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        handle_uncaught_exception(exc_type, exc_value, exc_traceback)
        sys.exit(1)
