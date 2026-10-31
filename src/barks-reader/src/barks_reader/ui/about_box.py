import textwrap
from collections.abc import Callable
from pathlib import Path

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader._version import COPYRIGHT_YEARS, VERSION
from barks_reader.core import log_markers
from barks_reader.core.popup_frame import PopupSize
from barks_reader.core.reader_consts_and_types import APP_TITLE, FANTAGRAPHICS_BARKS_LIBRARY
from barks_reader.core.reader_palette import theme

from .font_manager import FontManager
from .kivy_standalone_show_message import show_standalone_popup
from .popup_frame import popup_fonts

ABOUT_POPUP_TITLE = "About the Barks Reader"
# Air under the app's name, between the version lines and the licence text.
HEADING_GAP = dp(14)


def _fit_height_to_text(label: Widget, texture_size: tuple[float, float]) -> None:
    label.height = texture_size[1]


def _fitted(label: Label) -> Label:
    """Return `label` as tall as its text, so the box (and the popup) are as tall as theirs."""
    label.bind(texture_size=_fit_height_to_text)
    return label


def show_about_box(
    font_manager: FontManager,
    about_background_path: Path,
    on_dismiss: Callable[[], None] | None = None,
    data_pack_text: str = "",
) -> None:
    """Show the About box.

    Args:
        font_manager: The fonts for its text.
        about_background_path: Its background picture.
        on_dismiss: Called once the box has closed, after its dismissal is logged.
        data_pack_text: The installed data pack's line (`core.data_pack`), under the
            version; none when empty.

    """
    title_text_color = list(theme().text_display)  # bright cover-yellow hero
    version_text_color = list(theme().app_title)  # coin gold
    other_text_color = list(theme().text_secondary)  # newsprint cream
    # Its title and version lines are its own; the rest is the popups' message text.
    text_font_size = popup_fonts().text
    # --- Main container for the About dialog ---
    # Each line is as tall as its text and the box as tall as its lines: the frame
    # takes its height from the box (``fit_body_height``), leaving no gap under them.
    content = BoxLayout(
        orientation="vertical",
        spacing="12dp",
        padding=("30dp", "24dp"),
    )
    content.bind(minimum_height=content.setter("height"))

    # --- App name ---
    content.add_widget(
        _fitted(
            Label(
                text=APP_TITLE,
                size_hint=(1, None),
                padding=(0, 0, 0, HEADING_GAP),
                bold=True,
                color=title_text_color,
                font_size=round(font_manager.about_box_title_font_size),
                font_name=font_manager.about_box_title_font_name,
                halign="center",
                valign="middle",
            )
        )
    )

    # --- Version line ---
    content.add_widget(
        _fitted(
            Label(
                text=f"Version {VERSION}",
                color=version_text_color,
                bold=True,
                font_size=round(font_manager.about_box_version_font_size),
                halign="center",
                valign="middle",
                size_hint=(1, None),
            )
        )
    )

    # --- Data pack line ---
    if data_pack_text:
        content.add_widget(
            _fitted(
                Label(
                    text=data_pack_text,
                    color=version_text_color,
                    font_size=round(text_font_size),
                    halign="center",
                    valign="middle",
                    size_hint=(1, None),
                )
            )
        )

    # --- Copyright / Credits ---
    source_code_font_size = round(text_font_size)
    fan_font_size = round(text_font_size - 1)

    source_licence_text = textwrap.fill(
        textwrap.dedent(
            """
        Source code is open and available under the Apache 2.0 License.
        However, artwork, images, characters, and story data included within or
        displayed by this application are the proprietary intellectual property
        of their respective owners and are STRICTLY EXCLUDED from the open-source license.
        """
        ),
        width=80,
    )
    fan_project_text = textwrap.fill(
        textwrap.dedent(
            f"""
        This project is a fan-made reader utility for the "{FANTAGRAPHICS_BARKS_LIBRARY}."
        It is not affiliated with, endorsed by, or sponsored by The Walt Disney Company or
        Fantagraphics Books. Donald Duck, Uncle Scrooge, and related characters are trademarks of
        The Walt Disney Company.
        """
        ),
        width=80,
    )

    licence_text = (
        "[b]This software is licensed under the Apache License, Version 2.0.\n\n"
        f"© {COPYRIGHT_YEARS} Greg Kay.\n\n\n"
        f"[size={source_code_font_size}]{source_licence_text}[/size][/b]\n\n\n"
        f"[size={fan_font_size}][i]{fan_project_text}[/i][/size]"
    )
    content.add_widget(
        _fitted(
            Label(
                text=licence_text,
                color=other_text_color,
                markup=True,
                font_size=text_font_size,
                halign="center",
                valign="top",
                size_hint=(1, None),
                padding=(0, HEADING_GAP, 0, 0),
            )
        )
    )

    # --- Give the content to the popup ---
    logger.debug(log_markers.ABOUT_BOX_OPENED)
    show_standalone_popup(
        title=ABOUT_POPUP_TITLE,
        content=content,
        size=PopupSize.LARGE,
        fit_body_height=True,
        background_image_file=about_background_path,
        on_dismiss=lambda: _dismissed(on_dismiss),
    )


def _dismissed(on_dismiss: Callable[[], None] | None) -> None:
    logger.debug(log_markers.ABOUT_BOX_DISMISSED)
    if on_dismiss is not None:
        on_dismiss()
