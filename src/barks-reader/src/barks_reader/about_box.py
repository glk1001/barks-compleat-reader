from pathlib import Path

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from barks_reader._version import COPYRIGHT_YEARS, VERSION
from barks_reader.font_manager import FontManager
from barks_reader.kivy_standalone_show_message import show_standalone_popup
from barks_reader.reader_consts_and_types import APP_TITLE, FANTAGRAPHICS_BARKS_LIBRARY

ABOUT_POPUP_TITLE = "About the Barks Reader"


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
            size_hint=(1, 0.1),
            bold=True,
            color=(0, 0, 0, 1),
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
            color=(0, 0, 0, 1),
            bold=True,
            font_size=round(font_manager.about_box_version_font_size),
            halign="center",
            valign="middle",
            size_hint=(1, 0.15),
        )
    )

    # --- Copyright / Credits ---
    source_code_font_size = round(font_manager.about_box_fine_print_font_size - 1)
    fan_font_size = round(font_manager.about_box_fine_print_font_size - 1)
    # noinspection LongLine
    content.add_widget(
        Label(
            text=f"""
[b]This software is licensed under the Apache License, Version 2.0.

© {COPYRIGHT_YEARS} Greg Kay. All rights reserved.


[size={source_code_font_size}]Source code is open and available under the Apache 2.0 License.
Some artwork, images, and media assets included with this application
are proprietary and are not covered by the open-source license.[/size]

[size={fan_font_size}][i]This project is a fan-made reader for the [/i]"{FANTAGRAPHICS_BARKS_LIBRARY}."
[i]It is not affiliated with Disney or Fantagraphics.[/i][/size][/b]
            """,  # noqa: E501
            color=(0, 0, 0, 1),
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
