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


def test_every_marker_formats_with_its_named_fields_only() -> None:
    """A template must use only ``{name}`` fields, so ``pattern`` and ``format`` agree."""
    templates = {
        name: value
        for name, value in vars(log_markers).items()
        if name.isupper() and isinstance(value, str)
    }
    assert templates, "no markers found"
    for name, template in templates.items():
        fields = re.findall(r"\{(\w*)\}", template)
        assert all(fields), f"{name} has a positional {{}} field"
        # The braces a template contains must all be fields: a stray one would
        # make .format raise at the call site.
        assert template.count("{") == template.count("}") == len(fields), name
