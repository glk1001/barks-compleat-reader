"""What the About box says of the licence (``core.about_text``)."""

from __future__ import annotations

from barks_reader.core.about_text import FAN_PROJECT_TEXT, SOURCE_LICENCE_TEXT, licence_markup
from barks_reader.core.markup_text import plain_text


def test_it_names_the_licence_the_years_and_the_holder() -> None:
    text = plain_text(licence_markup("2025-2026", 18.0))
    assert text.startswith("This software is licensed under the Apache License, Version 2.0.")
    assert "\n\n© 2025-2026 Greg Kay.\n\n\n" in text


def test_the_art_is_left_out_of_the_licence_and_the_project_is_a_fan_s() -> None:
    text = plain_text(licence_markup("2026", 18.0))
    assert SOURCE_LICENCE_TEXT in text
    assert "STRICTLY EXCLUDED from the open-source license" in text
    assert text.endswith(FAN_PROJECT_TEXT)
    assert "not affiliated with, endorsed by, or sponsored by The Walt Disney Company" in text


def test_the_exclusion_is_bold_at_the_text_size_and_the_fan_note_italic_a_size_under() -> None:
    markup = licence_markup("2026", 17.6)
    assert f"[size=18]{SOURCE_LICENCE_TEXT}[/size][/b]" in markup
    assert markup.endswith(f"[size=17][i]{FAN_PROJECT_TEXT}[/i][/size]")
    assert markup.startswith("[b]")


def test_no_line_of_a_paragraph_is_broken_at_a_fixed_length() -> None:
    assert "\n" not in SOURCE_LICENCE_TEXT
    assert "\n" not in FAN_PROJECT_TEXT
