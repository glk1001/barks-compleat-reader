import platform
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

from comic_utils.os_utils import get_os_name, is_virtual_machine
from loguru import logger

from barks_reader._version import VERSION


def handle_app_fail_with_traceback(
    app_type: str,
    msg_title: str,
    exc_type,  # noqa: ANN001
    exc_value,  # noqa: ANN001
    exc_traceback,  # noqa: ANN001
    log_path: str,
    log_the_error: bool = True,
    background_image_file: Path | None = None,
) -> None:
    stack = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    # Main error message (brief)
    message = f"{exc_type.__name__}: {exc_value}"

    # Detailed information (collapsible)
    details = dedent(f"""Full Traceback:
{stack}

System Information:
  - Version: {VERSION}
  - OS: {get_os_name()}
  - System: {platform.system()}
  - System Release: {platform.release()}
  - System Version: {platform.version()}
  - Processor: {platform.processor()}
  - Python Version: {platform.python_version()}
  - Virtual Machine: {is_virtual_machine()}
  - Cwd: {Path.cwd()}
  - Time: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}
""")

    handle_app_fail(
        app_type, msg_title, message, details, log_path, log_the_error, background_image_file
    )


def handle_app_fail(
    app_type: str,
    msg_title: str,
    message: str,
    details: str,
    log_path: str,
    log_the_error: bool,
    background_image_file: Path | None,
    show_details: bool = False,
) -> None:
    from barks_reader.ui.kivy_standalone_error_popup import show_error_popup  # noqa: PLC0415

    show_error_popup(
        title_bar_text=app_type.capitalize(),
        title=msg_title,
        message=message,
        log_path=log_path,
        severity="error",
        details=details,
        show_details=show_details,
        timeout=0,
        background_image_file=background_image_file,
    )

    if log_the_error:
        from barks_reader.core.reader_formatter import (  # noqa: PLC0415
            get_text_with_markup_stripped,
        )

        logger.critical(f"An {app_type} error occurred: {get_text_with_markup_stripped(message)}.")
        logger.critical(get_text_with_markup_stripped(details))

    sys.exit(1)
