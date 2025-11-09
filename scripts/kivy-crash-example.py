# ruff: noqa: PGH004

import sys
import os
import platform
import traceback
import json
import logging
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label


# =============================================================================
# CONFIGURATION
# =============================================================================

APP_NAME = "barks_reader"
LOG_DIR = Path.home() / f".{APP_NAME}"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"
CRASH_DIR = LOG_DIR / "crash_reports"
CRASH_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(ch)

from logging.handlers import RotatingFileHandler

fh = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=5, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(fh)

logger.info(f"Log file: {LOG_FILE}")


# =============================================================================
# CRASH REPORTING UTILITIES
# =============================================================================
def send_pending_crash_reports():
    pending = list(CRASH_DIR.glob("crash_*.json"))
    if not pending:
        return

    bundle = create_crash_bundle()
    logger.info(f"Would upload or email: {bundle}")

    # TODO: send via email or HTTPS POST
    # Example: requests.post("https://yourserver.com/api/crash", files={"file": open(bundle, "rb")})

    # Clean up after sending
    for f in pending:
        f.unlink(missing_ok=True)
    bundle.unlink(missing_ok=True)


def _get_system_info():
    """Collect basic platform info for crash reports."""
    return {
        "app_name": APP_NAME,
        "timestamp": datetime.now().isoformat(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
    }


def save_crash_report(thread_name, exc_type, exc_value, exc_traceback) -> Path:
    """Write a structured JSON crash report to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = CRASH_DIR / f"crash_{timestamp}_{thread_name}.json"

    data = {
        "system": _get_system_info(),
        "thread": thread_name,
        "exception_type": str(exc_type.__name__),
        "exception_message": str(exc_value),
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
    }

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.critical(f"Crash report saved to {report_path}")
    except Exception as e:
        logger.error(f"Failed to write crash report: {e}")

    return report_path


def create_crash_bundle(max_reports=5) -> Path:
    """Bundle recent crash reports and logs into a zip archive."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = LOG_DIR / f"{APP_NAME}_crash_bundle_{timestamp}.zip"

    files = sorted(CRASH_DIR.glob("crash_*.json"), key=os.path.getmtime, reverse=True)[:max_reports]
    files += list(LOG_DIR.glob("app.log*"))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)

    logger.info(f"Crash bundle created: {zip_path}")
    return zip_path


# =============================================================================
# POPUP & GLOBAL EXCEPTION HOOKS
# =============================================================================


def show_error_popup(message: str):
    """Show a Kivy popup for user-friendly errors."""

    def _show(*_):
        Popup(
            title="Application Error",
            content=Label(text=message),
            size_hint=(0.6, 0.4),
            auto_dismiss=True,
        ).open()

    Clock.schedule_once(_show, 0)


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Uncaught exception (main thread):", exc_info=(exc_type, exc_value, exc_traceback)
    )
    report = save_crash_report(exc_type, exc_value, exc_traceback, "main")
    show_error_popup(f"Unexpected error:\n{exc_value}\n\nReport: {report.name}")


def handle_thread_exception(args):
    logger.critical(
        f"Uncaught exception in thread {args.thread.name}:",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    report = save_crash_report(args.exc_type, args.exc_value, args.exc_traceback, args.thread.name)
    show_error_popup(f"Background thread error:\n{args.exc_value}\n\nReport: {report.name}")


sys.excepthook = handle_uncaught_exception
threading.excepthook = handle_thread_exception


# =============================================================================
# OPTIONAL: ASYNCIO HANDLER
# =============================================================================

try:
    import asyncio

    def handle_asyncio_exception(loop, context):
        err = context.get("exception")
        logger.critical("Asyncio exception:", exc_info=err)
        save_crash_report(type(err), err, err.__traceback__, "asyncio")
        show_error_popup(f"Async error: {err}")

    asyncio.get_event_loop().set_exception_handler(handle_asyncio_exception)
except Exception:
    pass


# =============================================================================
# DEMO KIVY APP
# =============================================================================


class MyApp(App):
    def build(self):
        Clock.schedule_once(lambda dt: self.raise_error(), 3)
        return Label(text="Hello! (Will simulate crash in 3s)")

    def raise_error(self):
        raise RuntimeError("Simulated Kivy crash!")


def main():
    logger.info("Starting app...")
    MyApp().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.critical("Fatal startup error", exc_info=True)
        save_crash_report("startup", *sys.exc_info())
        sys.exit(1)
