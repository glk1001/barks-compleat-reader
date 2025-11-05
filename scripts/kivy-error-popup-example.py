import sys
import traceback
from datetime import datetime

from kivy_error_popup import show_error_popup


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    """Example excepthook that uses standalone popup fallback."""
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    # Main error message (brief)
    message = f"{exc_type.__name__}: {exc_value}"

    # Detailed information (collapsible)
    details = f"""Full Traceback:
{tb}

System Information:
- Python: {sys.version}
- Platform: {sys.platform}
- Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    show_error_popup(
        message=message,
        severity="critical",
        details=details,
        timeout=0,
    )


sys.excepthook = handle_uncaught_exception


# Test
if __name__ == "__main__":
    show_error_popup(
        message="This is a test error",
        severity="error",
        details="Additional details here...",
    )
