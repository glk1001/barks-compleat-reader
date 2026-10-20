from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from loguru import logger

from barks_reader.core.crash_report import crash_report

if TYPE_CHECKING:
    from pathlib import Path


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
    message, details = crash_report(exc_type, exc_value, exc_traceback)

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
    from .kivy_standalone_error_popup import show_error_popup  # noqa: PLC0415

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
