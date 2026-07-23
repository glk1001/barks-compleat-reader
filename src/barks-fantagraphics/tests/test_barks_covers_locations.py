"""Tests for the cover CCBDL locations (COVER_LOCATIONS and its accessors)."""

import pytest
from barks_fantagraphics import barks_covers as bc
from barks_fantagraphics.barks_covers import (
    BARKS_COVER_BY_KEY,
    BARKS_COVERS,
    COVER_LOCATIONS,
    get_cover_location,
    get_located_covers,
    is_cover_located,
)

MAX_FANTA_VOLUME = 30


class TestCoverLocations:
    def test_location_keys_are_known_covers(self) -> None:
        """Every key in the location table must be a known cover."""
        assert set(COVER_LOCATIONS) <= set(BARKS_COVER_BY_KEY)

    def test_volume_and_page_ranges(self) -> None:
        for volume, page in COVER_LOCATIONS.values():
            assert 1 <= volume <= MAX_FANTA_VOLUME
            assert page > 0

    def test_get_cover_location_none_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(bc, "COVER_LOCATIONS", {})
        assert get_cover_location(BARKS_COVERS[0]) is None
        assert not is_cover_located(BARKS_COVERS[0])
        assert get_located_covers() == []

    def test_zero_location_is_not_located(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A hand-edited (0, 0) entry counts as unlocated and is skipped."""
        monkeypatch.setattr(bc, "COVER_LOCATIONS", {BARKS_COVERS[0].key: (0, 0)})
        assert not is_cover_located(BARKS_COVERS[0])
        assert get_located_covers() == []

    def test_located_covers_preserve_bibliography_order(self) -> None:
        located = get_located_covers()
        assert located
        assert located == [cover for cover in BARKS_COVERS if cover in located]
