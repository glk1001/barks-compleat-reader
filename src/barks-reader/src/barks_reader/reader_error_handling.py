import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


def handle_app_fail_with_traceback(
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
    details = f"""Full Traceback:
    {stack}

    System Information:
    - Python: {sys.version}
    - Platform: {sys.platform}
    - Time: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}
    """

    _handle_app_fail(message, details, log_path, log_the_error, background_image_file)


def _handle_app_fail(
    message: str,
    details: str,
    log_path: str,
    log_the_error: bool,
    background_image_file: Path | None,
) -> None:
    from barks_reader.kivy_standalone_error_popup import show_error_popup  # noqa: PLC0415

    show_error_popup(
        title_bar_text="App",
        title="Barks Reader",
        message=message,
        log_path=log_path,
        severity="error",
        details=details,
        show_details=False,
        timeout=0,
        background_image_file=background_image_file,
    )

    if log_the_error:
        from barks_reader.reader_formatter import get_text_with_markup_stripped  # noqa: PLC0415

        logger.critical(f"An app error occurred: {get_text_with_markup_stripped(message)}.")
        logger.critical(get_text_with_markup_stripped(details))

    sys.exit(1)
