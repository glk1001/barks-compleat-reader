"""What the About box says of the app's licence: the words and their Kivy markup.

Kivy-free, so the wording and the sizes its three parts are set in are a unit test's
to hold, and the box (``ui.about_box``) only lays the text out.
"""

from __future__ import annotations

from .reader_consts_and_types import FANTAGRAPHICS_BARKS_LIBRARY

SOURCE_LICENCE_TEXT = (
    "Source code is open and available under the Apache 2.0 License."
    " However, artwork, images, characters, and story data included within or"
    " displayed by this application are the proprietary intellectual property"
    " of their respective owners and are STRICTLY EXCLUDED from the open-source license."
)
FAN_PROJECT_TEXT = (
    f'This project is a fan-made reader utility for the "{FANTAGRAPHICS_BARKS_LIBRARY}."'
    " It is not affiliated with, endorsed by, or sponsored by The Walt Disney Company or"
    " Fantagraphics Books. Donald Duck, Uncle Scrooge, and related characters are"
    " trademarks of The Walt Disney Company."
)


def licence_markup(copyright_years: str, text_font_size: float) -> str:
    """Return the About box's licence text as Kivy markup.

    No line of it is broken at a fixed length: the box wraps it to its own width.

    Args:
        copyright_years: The years the copyright line names ("2025-2026").
        text_font_size: The box's text size. The licence line and the copyright are
            set at it, what the licence leaves out at the nearest whole size, and
            the fan-project note a size smaller than that.

    Returns:
        The markup, bold but for the fan-project note, which is in italics.

    """
    source_code_font_size = round(text_font_size)
    fan_font_size = round(text_font_size - 1)
    return (
        "[b]This software is licensed under the Apache License, Version 2.0.\n\n"
        f"© {copyright_years} Greg Kay.\n\n\n"
        f"[size={source_code_font_size}]{SOURCE_LICENCE_TEXT}[/size][/b]\n\n\n"
        f"[size={fan_font_size}][i]{FAN_PROJECT_TEXT}[/i][/size]"
    )
