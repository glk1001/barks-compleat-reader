import textwrap
from pathlib import Path

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from barks_reader._version import COPYRIGHT_YEARS, VERSION
from barks_reader.core.reader_consts_and_types import APP_TITLE, FANTAGRAPHICS_BARKS_LIBRARY
from barks_reader.core.reader_palette import theme

from .font_manager import FontManager
from .kivy_standalone_show_message import show_standalone_popup

ABOUT_POPUP_TITLE = "About the Barks Reader"

# Warm near-black scrim over the background art so the gold/cream text reads
# on-brand — the same "art under a dark scrim" language as the rest of the app,
# replacing the old white wash with black text.
ABOUT_WRAPPER_SCRIM = (0.14, 0.12, 0.10, 0.38)


def show_about_box(font_manager: FontManager, about_background_path: Path) -> None:
    title_text_color = list(theme().text_display)  # bright cover-yellow hero
    version_text_color = list(theme().app_title)  # coin gold
    other_text_color = list(theme().text_secondary)  # newsprint cream
    # --- Main container for the About dialog ---
    content = BoxLayout(
        orientation="vertical",
        spacing="12dp",
        padding=("30dp", "30dp"),
    )

    # --- App name ---
    content.add_widget(
        Label(
            text=APP_TITLE,
            size_hint=(1, 0.12),
            bold=True,
            color=title_text_color,
            font_size=round(font_manager.about_box_title_font_size),
            font_name=font_manager.about_box_title_font_name,
            halign="center",
            valign="middle",
        )
    )

    # --- Version line ---
    content.add_widget(
        Label(
            text=f"Version {VERSION}",
            color=version_text_color,
            bold=True,
            font_size=round(font_manager.about_box_version_font_size),
            halign="center",
            valign="middle",
            size_hint=(1, 0.09),
        )
    )

    # --- Copyright / Credits ---
    source_code_font_size = round(font_manager.about_box_fine_print_font_size)
    fan_font_size = round(font_manager.about_box_fine_print_font_size - 1)

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

    content.add_widget(
        Label(
            text=f"""
[b]This software is licensed under the Apache License, Version 2.0.

© {COPYRIGHT_YEARS} Greg Kay.


[size={source_code_font_size}]{source_licence_text}[/size][/b]


[size={fan_font_size}][i]{fan_project_text}[/i][/size]
            """,
            color=other_text_color,
            markup=True,
            font_size=font_manager.about_box_fine_print_font_size,
            halign="center",
            valign="middle",
            size_hint=(1, 1),
        )
    )

    # --- Give the content to the popup ---
    show_standalone_popup(
        title=ABOUT_POPUP_TITLE,
        content=content,
        size_hint=(0.85, 0.54),
        timeout=0,
        auto_dismiss=True,
        add_close_button=True,
        background_image_file=about_background_path,
        wrapper_scrim=ABOUT_WRAPPER_SCRIM,
    )
