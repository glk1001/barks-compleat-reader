"""The markup the speech-bubble popup shows: each bubble under its speaker's line.

Kivy-free: Kivy markup is plain text, so the popup's content can be built and
tested without a widget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.speech_markup import escape_markup
from barks_fantagraphics.speech_speakers import speaker_display_name

from .reader_formatter import mark_terms_in_text
from .reader_palette import color_to_markup_hex, theme

if TYPE_CHECKING:
    from collections.abc import Sequence

    from barks_fantagraphics.whoosh_search_engine import PageInfo

# Matched speech terms are emphasized in the palette's selection accent, built
# lazily (see `_speech_highlight_start_tag`) so the active theme is honoured.
SPEECH_HIGHLIGHT_END_TAG = "[/color][/b]"


def _speech_highlight_start_tag() -> str:
    """Return the markup opening tag for a highlighted speech search term."""
    return f"[b][color={color_to_markup_hex(theme().accent_selection)}]"


# The speaker line's size relative to the bubble's lettering: an annotation
# on the line, not part of it.
SPEAKER_LABEL_SCALE = 0.9
# Breathing space under the speaker line. Kivy markup has no line spacing and
# gives every line at least the widget's own line height, so a small blank line
# is not small. Instead the label line ends in an invisible space set this much
# larger than the label: a line is as tall as its tallest glyph, and glyphs hang
# from the line's top, so the extra height lands under the name.
SPEAKER_GAP_SCALE = 1.7


def _speaker_label_markup(label: str, font_size: int | None) -> str:
    """Return the who-says-it line: bold italic, in the theme's speaker colour, smaller.

    The lettering itself carries ``[b]`` for emphasis, so bold alone would
    read as more of it; what sets the line apart is the italic, a colour the
    bubble's text never uses, and being a step smaller when the caller says
    how big the lettering is.  The bold is weight for the small size.
    """
    text = f"[b][i][color={color_to_markup_hex(theme().speech_speaker)}]{label}[/color][/i][/b]"
    return f"[size={font_size}]{text}[/size]" if font_size else text


def format_page_speech_bubbles(
    page_info: PageInfo,
    search_terms: str,
    speaker_font_size: int | None = None,
    highlight_terms: Sequence[str] | None = None,
) -> str:
    """Return one page's matching bubbles as the markup the popup shows.

    Each bubble is the group's marked-up lettering, with the search terms
    highlighted, under a line naming who says it -- ``SCROOGE:`` -- when
    the index knows.  A group with no speaker call (an index built before
    speakers existed, or a later volume) is shown exactly as before, and a
    ``none`` speaker (a sound effect, a sign) gets no line either.

    The highlight is applied to each bubble's text *before* the speaker line
    is put above it, so searching for "donald" lights up the word in the
    lettering and not the name on the label.  The label is escaped, since an
    ``other:`` speaker may carry an ampersand.

    The widget renders Kivy markup for the highlight anyway, so the
    lettering's own [b]/[i] comes for free.  Caveat: a search phrase
    straddling an emphasis boundary -- "really sharp", where only SHARP is
    bold -- will not highlight, because the matcher sees the tags sitting
    between the words.

    Args:
        page_info: The page's matching speech groups.
        search_terms: What was searched for, to highlight.
        speaker_font_size: Pixel size for the speaker line, or None to
            inherit the bubble's.
        highlight_terms: The words and phrases to highlight instead of
            ``search_terms`` -- a typed query's, which may be many (each
            word's forms, a wildcard's words) -- or None.

    Returns:
        The page's bubbles joined by blank lines, ready for a markup label.

    """
    bubbles: list[str] = []
    for speech in page_info.speech_info_list:
        text = mark_terms_in_text(
            [search_terms] if highlight_terms is None else highlight_terms,
            speech.speech_text_markup,
            _speech_highlight_start_tag(),
            SPEECH_HIGHLIGHT_END_TAG,
        )
        label = speaker_display_name(speech.speaker) if speech.speaker else None
        if label:
            markup = _speaker_label_markup(escape_markup(label) + ":", speaker_font_size)
            gap = (
                f"[size={round(speaker_font_size * SPEAKER_GAP_SCALE)}] [/size]"
                if speaker_font_size
                else ""
            )
            text = f"{markup}{gap}\n{text}"
        bubbles.append(text)
    return "\n\n".join(bubbles).replace("­", "-").strip()
