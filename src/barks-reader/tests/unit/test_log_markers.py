"""The marker templates and the regexes the GUI tests derive from them."""

from __future__ import annotations

import re

import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern


class TestPattern:
    def test_a_marker_with_no_fields_matches_itself_literally(self) -> None:
        regex = pattern(log_markers.CLOSING_APP)
        assert re.search(regex, "Closing app...")
        assert not re.search(regex, "Closing appXYZ")

    def test_a_field_left_out_matches_anything(self) -> None:
        regex = pattern(log_markers.SHOWED_PAGE)
        assert re.search(regex, log_markers.SHOWED_PAGE.format(index=34, elapsed="12ms"))

    def test_a_field_given_is_matched_exactly(self) -> None:
        regex = pattern(log_markers.SHOWED_PAGE, index=3)
        assert re.search(regex, log_markers.SHOWED_PAGE.format(index=3, elapsed="12ms"))
        assert not re.search(regex, log_markers.SHOWED_PAGE.format(index=34, elapsed="12ms"))

    def test_literal_text_and_field_values_are_escaped(self) -> None:
        regex = pattern(log_markers.MAIN_SCREEN_ACTIVE, origin="By the Numbers")
        assert re.search(regex, "Main screen is active (from By the Numbers).")
        assert not re.search(regex, "Main screen is active -from By the Numbers-.")

    def test_a_compiled_regex_field_is_spliced_in_as_written(self) -> None:
        regex = pattern(log_markers.NEW_SELECTED_NODE, name=re.compile(r"19\d\d-19\d\d"))
        line = log_markers.NEW_SELECTED_NODE.format(name="1947-1950", previous="root")
        assert re.search(regex, line)
        assert not re.search(regex, line.replace("1947-1950", "Covers"))

    def test_a_field_not_in_the_template_is_refused(self) -> None:
        with pytest.raises(KeyError, match="no_such_field"):
            pattern(log_markers.SHOWED_PAGE, no_such_field=1)


class TestCapture:
    def test_captures_the_named_field(self) -> None:
        line = log_markers.SHOWED_PAGE.format(index=34, elapsed="1.5s")
        found = re.search(log_markers.capture(log_markers.SHOWED_PAGE, "index"), line)
        assert found is not None
        assert found["index"] == "34"
        found = re.search(log_markers.capture(log_markers.SHOWED_PAGE, "elapsed"), line)
        assert found is not None
        assert found["elapsed"] == "1.5s"

    def test_other_fields_can_still_be_pinned(self) -> None:
        line = log_markers.HISTORY_BUILT_VIEW.format(view="journal", rows=6)
        regex = log_markers.capture(log_markers.HISTORY_BUILT_VIEW, "rows", view="journal")
        found = re.search(regex, line)
        assert found is not None
        assert found["rows"] == "6"
        assert not re.search(
            log_markers.capture(log_markers.HISTORY_BUILT_VIEW, "rows", view="titles"), line
        )

    def test_a_field_not_in_the_template_is_refused(self) -> None:
        with pytest.raises(KeyError, match="no_such_field"):
            log_markers.capture(log_markers.SHOWED_PAGE, "no_such_field")


def _templates() -> dict[str, str]:
    templates = {
        name: value
        for name, value in vars(log_markers).items()
        if name.isupper() and isinstance(value, str)
    }
    assert templates, "no markers found"
    return templates


def test_every_marker_formats_with_its_named_fields_only() -> None:
    """A template must use only ``{name}`` fields, so ``pattern`` and ``format`` agree."""
    for name, template in _templates().items():
        fields = re.findall(r"\{(\w*)\}", template)
        assert all(fields), f"{name} has a positional {{}} field"
        # The braces a template contains must all be fields: a stray one would
        # make .format raise at the call site.
        assert template.count("{") == template.count("}") == len(fields), name


def test_every_quoted_field_closes_its_quote() -> None:
    """A field opened with a quote is closed with it, so a value's end is plain in the log."""
    for name, template in _templates().items():
        assert template.count('"') % 2 == 0, f"{name} has an unclosed double quote"
        for quote, field, after in re.findall(r"""(['"])\{(\w+)\}(.?)""", template):
            assert after == quote, f"{name} opens {quote}{{{field}}} without closing it"


class TestAFieldAtAnEdge:
    """A value at the template's start or end has no literal text there to stop it."""

    def test_a_value_at_the_end_does_not_match_a_longer_one(self) -> None:
        regex = pattern(log_markers.INDEX_ITEM_PRESSED, item="A")
        assert re.search(regex, "12:00 | INFO | x - Index item pressed: A\n")
        assert not re.search(regex, "12:00 | INFO | x - Index item pressed: Abbey\n")

    def test_a_value_at_the_start_does_not_match_a_longer_one(self) -> None:
        regex = pattern(log_markers.ENTERING_FULLSCREEN, screen="1")
        assert re.search(regex, "x - 1: Entering fullscreen mode.")
        assert not re.search(regex, "x - 21: Entering fullscreen mode.")

    def test_a_value_ending_in_punctuation_still_matches(self) -> None:
        regex = pattern(log_markers.INDEX_ITEM_PRESSED, item="Lost in the Andes!")
        assert re.search(regex, "x - Index item pressed: Lost in the Andes!")

    def test_a_value_inside_the_template_is_not_bounded(self) -> None:
        """Literal text on both sides already stops it: no boundary is added."""
        assert r"\b" not in pattern(log_markers.SHOWED_PAGE, index=3)

    def test_a_value_inside_a_template_ending_in_a_field_is_not_bounded(self) -> None:
        """Only the last field is at the end: "800" runs straight on into the "x" after it."""
        regex = pattern(log_markers.TAP_TARGETS, width=800)
        assert re.search(regex, "x - Tap targets #3: 800x600 [ok]")

    def test_a_regex_field_is_spliced_as_written(self) -> None:
        regex = pattern(log_markers.INDEX_ITEM_PRESSED, item=re.compile("Ab.*"))
        assert regex.endswith("Ab.*")


def test_capturing_a_field_also_given_a_value_is_refused() -> None:
    with pytest.raises(KeyError, match="cannot also be given"):
        log_markers.capture(log_markers.SHOWED_PAGE, "index", index=3)
