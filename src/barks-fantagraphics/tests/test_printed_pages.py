"""Tests for working out the page printed in the book from a scan image.

The expected numbers here were read off the scans themselves: image 040 of volume 18 has
33 at the foot of the page, and volume 7 runs 106, an unnumbered divider, then 109.
"""

import pytest
from barks_fantagraphics.printed_pages import get_printed_page


class TestAScanWithAPrintedPage:
    @pytest.mark.parametrize(
        ("volume", "image", "printed_page"),
        [
            (18, "040", "33"),
            (18, "161", "154"),
            (6, "213", "208"),
            (1, "116", "109"),
        ],
    )
    def test_it_is_the_image_less_the_volume_offset(
        self, volume: int, image: str, printed_page: str
    ) -> None:
        assert get_printed_page(volume, image) == printed_page

    def test_an_unpadded_image_means_the_same_page(self) -> None:
        assert get_printed_page(18, "40") == get_printed_page(18, "040")


class TestAVolumeWhoseOffsetSteps:
    def test_before_the_divider(self) -> None:
        assert get_printed_page(7, "119") == "106"

    def test_after_the_divider(self) -> None:
        assert get_printed_page(7, "121") == "109"

    def test_the_divider_itself_has_no_number(self) -> None:
        assert get_printed_page(7, "120") is None


class TestAPageRestoredBetweenTwoOthers:
    def test_it_is_a_folio(self) -> None:
        assert get_printed_page(4, "227") == "188a"

    def test_the_pages_either_side_are_not_disturbed(self) -> None:
        assert get_printed_page(4, "194") == "188"
        assert get_printed_page(4, "195") == "189"


class TestAnImageWithNoPrintedPage:
    @pytest.mark.parametrize(
        ("volume", "image"),
        [
            pytest.param(18, "003", id="front matter before page 1"),
            pytest.param(18, "007", id="the image just before page 1"),
            pytest.param(1, "258", id="first page of a story censored out of the volume"),
            pytest.param(1, "267", id="last page of a story censored out of the volume"),
            pytest.param(3, "250", id="a second censored-out story"),
            pytest.param(7, "240", id="a page copied in from another volume"),
            pytest.param(28, "207", id="a page added to the volume"),
            pytest.param(1, "500", id="a slot in a collection's own numbering"),
            pytest.param(18, "empty_page", id="a page that is not a scan"),
            pytest.param(18, "", id="a row with no image"),
            pytest.param(31, "040", id="a volume that does not exist"),
        ],
    )
    def test_it_is_none(self, volume: int, image: str) -> None:
        assert get_printed_page(volume, image) is None

    def test_the_page_after_a_censored_out_story_is_still_numbered(self) -> None:
        assert get_printed_page(1, "257") == "250"


def test_every_volume_has_an_offset() -> None:
    assert all(get_printed_page(volume, "100") is not None for volume in range(1, 31))
