import textwrap
from pathlib import Path

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from barks_reader._version import COPYRIGHT_YEARS, VERSION
from barks_reader.font_manager import FontManager
from barks_reader.kivy_standalone_show_message import show_standalone_popup
from barks_reader.reader_consts_and_types import APP_TITLE, FANTAGRAPHICS_BARKS_LIBRARY

ABOUT_POPUP_TITLE = "About the Barks Reader"

TITLE_TEXT_COLOR = (0.0, 0.0, 0.0, 1)
VERSION_TEXT_COLOR = (0.0, 0.0, 0.0, 1)
OTHER_TEXT_COLOR = (0.0, 0.0, 0.0, 1)


def show_about_box(font_manager: FontManager, about_background_path: Path) -> None:
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
            size_hint=(1, 0.07),
            bold=True,
            color=TITLE_TEXT_COLOR,
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
            color=VERSION_TEXT_COLOR,
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
        This project is a fan-made reader utility for the [/i]"{FANTAGRAPHICS_BARKS_LIBRARY}.[i]"
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
            color=OTHER_TEXT_COLOR,
            markup=True,
            font_size=font_manager.about_box_fine_print_font_size,
            halign="center",
            valign="middle",
            size_hint=(1, 0.25),
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
    )
