"""Tests for :mod:`barks_reader.core.page_image`."""

from __future__ import annotations

import pytest
from barks_reader.core.page_image import PageImage
from PIL import Image


class TestFromPil:
    def test_an_rgb_page_is_taken_as_it_is(self) -> None:
        pil = Image.new("RGB", (3, 2), (10, 20, 30))

        page = PageImage.from_pil(pil)

        assert (page.width, page.height, page.mode) == (3, 2, "RGB")
        assert page.pixels == bytes((10, 20, 30)) * 6
        assert page.nbytes == 18  # noqa: PLR2004

    def test_an_rgba_page_keeps_its_alpha(self) -> None:
        pil = Image.new("RGBA", (2, 1), (1, 2, 3, 4))

        page = PageImage.from_pil(pil)

        assert page.mode == "RGBA"
        assert page.pixels == bytes((1, 2, 3, 4)) * 2

    @pytest.mark.parametrize("mode", ["L", "P", "CMYK"])
    def test_any_other_opaque_layout_becomes_rgb(self, mode: str) -> None:
        """A grayscale or palette scan is still filled into an RGB texture."""
        pil = Image.new(mode, (2, 2))

        page = PageImage.from_pil(pil)

        assert page.mode == "RGB"
        assert page.nbytes == 2 * 2 * 3

    @pytest.mark.parametrize("mode", ["LA", "PA"])
    def test_a_layout_with_an_alpha_band_keeps_it(self, mode: str) -> None:
        """A grayscale page with holes in it is not flattened onto black."""
        pil = Image.new(mode, (2, 1))
        pil.putpixel((0, 0), (255, 0))  # transparent
        pil.putpixel((1, 0), (255, 255))  # opaque

        page = PageImage.from_pil(pil)

        assert page.mode == "RGBA"
        assert page.to_pil().getchannel("A").tobytes() == bytes((0, 255))

    def test_a_palette_with_a_transparent_entry_keeps_it(self) -> None:
        """A palette PNG's tRNS chunk is transparency too, though the mode is plain P."""
        pil = Image.new("P", (2, 1))
        pil.putpalette([0, 0, 0, 255, 255, 255])
        pil.putpixel((0, 0), 0)
        pil.putpixel((1, 0), 1)
        pil.info["transparency"] = 0

        page = PageImage.from_pil(pil)

        assert page.mode == "RGBA"
        assert page.to_pil().getpixel((0, 0)) == (0, 0, 0, 0)
        assert page.to_pil().getpixel((1, 0)) == (255, 255, 255, 255)


class TestToPil:
    def test_the_pixels_round_trip_through_pil(self) -> None:
        """The compositor reads the page back as the image it was made from."""
        pil = Image.new("RGB", (4, 3), (200, 100, 50))
        pil.putpixel((1, 2), (1, 2, 3))

        again = PageImage.from_pil(pil).to_pil()

        assert again.size == (4, 3)
        assert again.mode == "RGB"
        assert again.tobytes() == pil.tobytes()
        assert again.getpixel((1, 2)) == (1, 2, 3)
