# ruff: noqa: PLC0415

"""Error popup content widget with severity levels, copy, save, and expandable details."""

import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from barks_fantagraphics.comics_consts import ROBOTO_FONT
from loguru import logger

from .kivy_standalone_show_message import divider_line

DEFAULT_ERROR_POPUP_SIZE = (800, 1000)


def show_error_popup(
    title_bar_text: str,
    title: str,
    message: str,
    log_path: str,
    timeout: float = 0,
    severity: str = "error",
    details: str = "",
    show_details: bool = False,
    size: tuple[int, int] = DEFAULT_ERROR_POPUP_SIZE,
    background_image_file: Path | None = None,
) -> None:
    """Show an error popup with severity levels and action buttons.

    Args:
        title_bar_text: Text to appear on popup titlebar
        title: Text for severity banner
        message: Main error message to display
        log_path: Path to log file
        timeout: Auto-close after this many seconds (0 = wait for user)
        severity: Error severity level: "critical", "error", "warning", "info"
        details: Additional detailed information (collapsible)
        show_details: If True, drop down the details box
        size: Size of popup window
        background_image_file: Image to put behind everything

    """
    from barks_reader.core.popup_frame import FrameButton
    from barks_reader.core.reader_utils import get_centred_position_on_primary_monitor

    from .kivy_standalone_show_message import show_standalone_popup

    x, y = get_centred_position_on_primary_monitor(*size)

    # Set the window pos and size now to avoid moving window flicker.
    from kivy import Config

    Config.set("graphics", "left", x)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "top", y)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "width", size[0])  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "height", size[1])  # ty: ignore[unresolved-attribute]

    content = _get_error_content(
        title=title,
        message=message,
        log_path=log_path,
        severity=severity,
        details=details,
        show_details=show_details,
    )

    show_standalone_popup(
        title=f"{title_bar_text} {severity.title()}",
        content=content,
        fill_window=True,
        buttons=(
            FrameButton("OK", lambda: None),
            FrameButton("Save to File", content.save_to_file, closes=False),
            FrameButton("Copy to Clipboard", content.copy_to_clipboard, closes=False),
        ),
        timeout=timeout,
        background_image_file=background_image_file,
    )


def _get_error_content(  # noqa: C901
    title: str,
    message: str,
    log_path: str,
    severity: str = "error",
    details: str = "",
    show_details: bool = False,
) -> Any:  # noqa: ANN401
    from barks_kivy_ui.scrolling import ReaderScrollView
    from kivy.clock import Clock
    from kivy.core.clipboard import Clipboard
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    from kivy.metrics import sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_formatter import get_text_with_markup_stripped
    from barks_reader.core.reader_palette import theme

    from .popup_frame import BUTTON_BACKGROUND, popup_fonts

    # The banner and the headings are its own; the text and the Show Details button
    # are the popups' (the window is sized before this).
    fonts = popup_fonts()
    banner_header_font_size = sp(19)
    section_header_font_size = sp(16)
    info_text_font_size = fonts.text
    button_font_size = fonts.button
    text_color = list(theme().text_secondary)

    class _ErrorContent(BoxLayout):
        """The error popup's body, on the frame's dark card; its buttons are the frame's."""

        def __init__(  # noqa: PLR0915
            self,
            error_title: str,
            error_message: str,
            the_log_path: str,
            error_severity: str = "error",
            error_details: str = "",
            show_error_details: bool = False,
        ) -> None:
            super().__init__(orientation="vertical", padding=0, spacing=10)
            self.title = error_title
            self.message = error_message
            self.log_path = the_log_path
            self.details = error_details
            self.full_message = get_text_with_markup_stripped(
                f"{self.message}\n\n{self.details}" if self.details else self.message
            )
            self.popup_ref = None
            self._base_title = ""
            self.severity = error_severity.lower()
            self.details_visible = False

            # ========== SEVERITY BANNER ==========
            self.colors = {
                "critical": {"bg": [0.8, 0.1, 0.1, 1], "text": [1, 1, 1, 1]},
                "error": {"bg": [0.9, 0.3, 0.3, 1], "text": [1, 1, 1, 1]},
                "warning": {"bg": [0.9, 0.7, 0.2, 1], "text": [0, 0, 0, 1]},
                "info": {"bg": [0.2, 0.6, 0.9, 1], "text": [1, 1, 1, 1]},
            }
            color_scheme = self.colors.get(self.severity, self.colors["error"])

            severity_banner = Label(
                text=f"{self.title} {self.severity.capitalize()}",
                size_hint_y=None,
                height=60,
                font_size=banner_header_font_size,
                bold=True,
                color=color_scheme["text"],
                font_name=ROBOTO_FONT,
            )

            with severity_banner.canvas.before:  # ty: ignore[unresolved-attribute]
                Color(*color_scheme["bg"])
                # Rounded corners on *all* sides for capsule-like look
                self.severity_bgnd = RoundedRectangle(
                    pos=severity_banner.pos,
                    size=severity_banner.size,
                    radius=[(12, 12), (12, 12), (12, 12), (12, 12)],
                )

            severity_banner.bind(pos=self._update_severity_bgnd, size=self._update_severity_bgnd)
            self.add_widget(severity_banner)

            # --- Scrollable content ---
            self.scroll_view = ReaderScrollView(size_hint=(1, 1))
            scroll_content = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=10,
                padding=(0, 0, 0, 10),
            )
            scroll_content.bind(minimum_height=lambda inst, val: setattr(inst, "height", val))
            self.scroll_content = scroll_content

            # --- Helper for text wrapping ---
            def update_text_size(instance: Widget, value: int) -> None:
                instance.text_size = (value - 40, None)
                instance.texture_update()
                instance.height = instance.texture_size[1]

            # --- Heading label with tinted background ---
            def tinted_heading(text: str) -> Label:
                heading = Label(
                    text=f"[b]{text}[/b]",
                    font_size=section_header_font_size,
                    markup=True,
                    size_hint_y=None,
                    height=32,
                    color=list(theme().text_title),
                    halign="left",
                    valign="middle",
                    padding=[10, 0],
                )
                heading.bind(width=lambda inst, val: setattr(inst, "text_size", (val - 20, None)))
                with heading.canvas.before:  # ty:ignore[unresolved-attribute]
                    Color(1, 1, 1, 0.06)  # a faint band in the dark card
                    heading.bg_rect = Rectangle(size=heading.size, pos=heading.pos)
                heading.bind(size=lambda inst, val: setattr(inst.bg_rect, "size", val))
                heading.bind(pos=lambda inst, val: setattr(inst.bg_rect, "pos", val))
                return heading

            # --- Error Message section ---
            scroll_content.add_widget(tinted_heading("Error Message"))
            self.label_msg = Label(
                text=self.message,
                font_size=info_text_font_size,
                markup=True,
                size_hint_y=None,
                halign="left",
                valign="top",
                color=text_color,
                padding=[0, 10],
            )
            self.label_msg.bind(width=update_text_size)
            scroll_content.add_widget(self.label_msg)
            scroll_content.add_widget(divider_line())

            # --- Log File section ---
            scroll_content.add_widget(tinted_heading("Log File"))
            log_msg = (
                f'Check the log for more info:\n\n[b]"{self.log_path}".[/b]'
                if self.log_path
                else "No log file available."
            )
            self.label_log_path = Label(
                text=log_msg,
                font_size=info_text_font_size,
                markup=True,
                size_hint_y=None,
                halign="left",
                valign="top",
                color=text_color,
            )
            self.label_log_path.bind(width=update_text_size)
            scroll_content.add_widget(self.label_log_path)
            scroll_content.add_widget(divider_line())

            # --- Error Details (added dynamically) ---
            self._error_details_divider_line = divider_line()
            self.heading_details = tinted_heading("Error Details")
            self.label_details = Label(
                text=self.details.strip(),
                font_size=info_text_font_size,
                markup=True,
                size_hint_y=None,
                halign="left",
                valign="top",
                color=text_color,
            )
            self.label_details.bind(width=update_text_size)
            self.label_details.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1]))

            # Add scroll content to ScrollView
            self.scroll_view.add_widget(scroll_content)
            self.add_widget(self.scroll_view)

            # --- Details toggle button ---
            if self.details:
                btn_toggle = Button(
                    text="Show Details",
                    font_size=button_font_size,
                    size_hint_y=None,
                    height=40,
                    background_normal="",
                    background_color=list(BUTTON_BACKGROUND),
                    color=text_color,
                    font_name=ROBOTO_FONT,
                )
                btn_toggle.bind(on_press=self.toggle_details)
                self.add_widget(btn_toggle)
                self.btn_toggle = btn_toggle
                if show_error_details:
                    self.toggle_details()

        # --- Helper methods ---
        def _flash_title(self, text: str, seconds: float) -> None:
            """Show `text` in the popup's title bar for a moment, then its title again."""
            if not self.popup_ref:
                return
            self._base_title = self._base_title or self.popup_ref.title
            self.popup_ref.title = text
            base = self._base_title
            Clock.schedule_once(lambda _dt: setattr(self.popup_ref, "title", base), seconds)

        def _update_severity_bgnd(self, instance: Widget, _) -> None:  # noqa: ANN001
            """Keep severity banner background aligned with label."""
            self.severity_bgnd.pos = instance.pos
            self.severity_bgnd.size = instance.size

        def toggle_details(self, *_args) -> None:  # noqa: ANN002
            """Toggle visibility of detailed error information."""
            self.details_visible = not self.details_visible
            if self.details_visible:
                if self.label_details.parent is None:
                    idx = self.scroll_content.children.index(self.label_log_path)
                    self._error_details_divider_line = divider_line()
                    self.scroll_content.add_widget(self._error_details_divider_line)
                    self.scroll_content.add_widget(self.heading_details, index=idx)
                    self.scroll_content.add_widget(self.label_details, index=idx)
                self.btn_toggle.text = "Hide Details"
            else:
                if self.label_details.parent is not None:
                    self.scroll_content.remove_widget(self.label_details)
                if self.heading_details.parent is not None:
                    self.scroll_content.remove_widget(self.heading_details)
                if self._error_details_divider_line:
                    self.scroll_content.remove_widget(self._error_details_divider_line)
                self.btn_toggle.text = "Show Details"

            # Scroll back to top
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: setattr(self.scroll_view, "scroll_y", 1), 0.15)

        def save_to_file(self, *_args) -> None:  # noqa: ANN002
            """Save error message to a file."""
            # noinspection PyBroadException
            try:
                # Create error logs directory.
                log_dir = Path(self.log_path).parent if self.log_path else Path.cwd()

                # Generate filename with timestamp
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                error_msg_file = log_dir / f"barks-reader-error-details-{timestamp}.txt"

                # Write error to file.
                with error_msg_file.open("w", encoding="utf-8") as f:
                    f.write("Barks Reader Error Report\n")
                    f.write(f"{'=' * 60}\n")
                    f.write(f"Timestamp: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Severity: {self.severity.upper()}\n")
                    f.write(f"{'=' * 60}\n\n")
                    f.write(self.full_message)

                logger.info(f'Error saved to "{error_msg_file}".')

                self._flash_title(f'Saved to "{error_msg_file}"', 3.0)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to save error to file:")
                self._flash_title("Save failed", 2.0)

        def copy_to_clipboard(self, *_args) -> None:  # noqa: ANN002
            """Copy error message to clipboard."""
            # noinspection PyBroadException
            try:
                Clipboard.copy(self.full_message)
                logger.info("Error message copied to clipboard")
                self._flash_title("Copied to clipboard", 2.0)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to copy to clipboard:")

    return _ErrorContent(title, message, log_path, severity, details, show_details)


# Test usage
if __name__ == "__main__":
    test_log_path = Path("~/opt/barks-reader/app.log").expanduser()

    def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
        """Use excepthook as example of standalone popup fallback."""
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # Main error message (brief)
        message = f"{exc_type.__name__}: {exc_value}"

        # Detailed information (collapsible)
        details = f"""Full Traceback:
    {tb}

    System Information:
    - Python: {sys.version}
    - Platform: {sys.platform}
    - Time: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}
    """

        show_error_popup(
            title_bar_text="Installer",
            title="Barks Reader Installation",
            message=message,
            log_path=str(test_log_path),
            severity="critical",
            details=details,
            timeout=0,
            background_image_file=Path(
                "~/Books/Carl Barks/Compleat Barks Disney Reader/Reader Files/"
                "Various/error-background.png"
            ).expanduser(),
        )

    sys.excepthook = handle_uncaught_exception

    # raise RuntimeError("Deliberate test exception.")  # noqa: ERA001

    show_error_popup(
        title_bar_text="Installer",
        title="Barks Reader Installation",
        message="This is a test error with [b]some markup[/b]",
        log_path=str(test_log_path),
        severity="error",
        details="Stack trace [b]line 1[/b]\nStack trace [b]line 2[/b]\nStack trace line 3\n"
        "Stack trace line 4\nStack trace line 5\nStack trace line 6\n"
        "Stack trace line 7\nStack trace line 8\nStack trace [b]line 9[/b]...",
        show_details=False,
        background_image_file=Path(
            "~/Books/Carl Barks/Compleat Barks Disney Reader/Reader Files/"
            "Various/error-background.png"
        ).expanduser(),
    )
