"""The speech-bubble popup's markup (barks_reader.core.speech_bubble_markup)."""

from __future__ import annotations

from barks_fantagraphics.whoosh_search_engine import PageInfo, SpeechInfo
from barks_reader.core.reader_palette import color_to_markup_hex, theme
from barks_reader.core.speech_bubble_markup import (
    SPEECH_HIGHLIGHT_END_TAG,
    _speech_highlight_start_tag,
    format_page_speech_bubbles,
)


def _speech(text: str, speaker: str | None = None, group_id: str = "0") -> SpeechInfo:
    return SpeechInfo(
        group_id=group_id,
        panel_num=1,
        speech_text=text,
        speech_text_markup=text,
        speaker=speaker,
    )


def _label(name: str) -> str:
    """Return the speaker line as rendered: bold italic in the speaker colour."""
    return f"[b][i][color={color_to_markup_hex(theme().speech_speaker)}]{name}:[/color][/i][/b]"


class TestFormatPageSpeechBubbles:
    """Each bubble names its speaker on a bold italic, coloured line above the lettering."""

    def test_speaker_line_above_the_bubble(self) -> None:
        page = PageInfo("5", [_speech("MONEY! MONEY!", speaker="Scrooge")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Scrooge')}\nMONEY! MONEY!"

    def test_speaker_line_takes_the_given_size(self) -> None:
        page = PageInfo("5", [_speech("HI", speaker="Scrooge")])

        text = format_page_speech_bubbles(page, "zzz", speaker_font_size=16)

        assert text == f"[size=16]{_label('Scrooge')}[/size][size=27] [/size]\nHI"

    def test_speaker_line_is_set_apart_by_more_than_bold(self) -> None:
        """The lettering carries [b] for emphasis, so the label must carry italic and colour too."""
        page = PageInfo("5", [_speech("A [b]BIG[/b] DEAL", speaker="Scrooge")])

        text = format_page_speech_bubbles(page, "zzz")

        assert text.startswith("[b][i][color=")
        assert text.endswith("[/color][/i][/b]\nA [b]BIG[/b] DEAL")

    def test_bubbles_are_separated_by_a_blank_line(self) -> None:
        page = PageInfo(
            "5",
            [_speech("ONE", speaker="Donald", group_id="0"), _speech("TWO", speaker="nephews")],
        )

        assert format_page_speech_bubbles(page, "zzz") == (
            f"{_label('Donald')}\nONE\n\n{_label('Nephews')}\nTWO"
        )

    def test_no_speaker_call_renders_as_before(self) -> None:
        """An index built before speakers existed shows plain bubbles."""
        page = PageInfo("5", [_speech("ONE"), _speech("TWO", group_id="1")])

        assert format_page_speech_bubbles(page, "zzz") == "ONE\n\nTWO"

    def test_none_speaker_gets_no_line(self) -> None:
        """A sound effect or a sign is nobody's line."""
        page = PageInfo("5", [_speech("CRASH!", speaker="none")])

        assert format_page_speech_bubbles(page, "zzz") == "CRASH!"

    def test_sentinels_and_other_names(self) -> None:
        page = PageInfo(
            "5",
            [
                _speech("LATER...", speaker="narrator", group_id="0"),
                _speech("HEE HEE!", speaker="other:Witch Hazel", group_id="1"),
                _speech("WHO?", speaker="unknown", group_id="2"),
            ],
        )

        assert format_page_speech_bubbles(page, "zzz") == (
            f"{_label('Narrator')}\nLATER...\n\n{_label('Witch Hazel')}\nHEE HEE!"
            f"\n\n{_label('Unknown')}\nWHO?"
        )

    def test_label_is_escaped_for_markup(self) -> None:
        page = PageInfo("5", [_speech("HI", speaker="other:Goldstein & Co.")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Goldstein &amp; Co.')}\nHI"

    def test_search_term_highlighted_in_the_lettering_not_the_label(self) -> None:
        page = PageInfo("5", [_speech("OH, DONALD!", speaker="Donald")])

        text = format_page_speech_bubbles(page, "donald")

        start = _speech_highlight_start_tag()
        assert text == f"{_label('Donald')}\nOH, {start}DONALD{SPEECH_HIGHLIGHT_END_TAG}!"

    def test_the_query_terms_are_highlighted_instead_of_the_search_text(self) -> None:
        page = PageInfo("5", [_speech("DUCKS DUCKING GOLD", speaker="Donald")])

        text = format_page_speech_bubbles(page, "duck -gold", highlight_terms=["ducks", "ducking"])

        start, end = _speech_highlight_start_tag(), SPEECH_HIGHLIGHT_END_TAG
        assert text == f"{_label('Donald')}\n{start}DUCKS{end} {start}DUCKING{end} GOLD"

    def test_soft_hyphens_become_hyphens(self) -> None:
        page = PageInfo("5", [_speech("SUPER\u00adDUCK", speaker="Donald")])

        assert format_page_speech_bubbles(page, "zzz") == f"{_label('Donald')}\nSUPER-DUCK"
