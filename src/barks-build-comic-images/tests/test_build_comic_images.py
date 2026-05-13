# ruff: noqa: PLR2004

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from barks_build_comic_images.build_comic_images import (
    RGB_PROFILE,
    SVG_ADAPTIVE_PROFILE,
    AdaptivePageImageSource,
    AlphaPageImageSource,
    BuildSourceProfile,
    PageImageSource,
    RgbPageImageSource,
)
from barks_fantagraphics.pages import (
    FinalStoryFileResolver,
    SvgPngStoryFileResolver,
)
from PIL import Image


class TestPageImageSource:
    def test_abstract_base_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            PageImageSource()  # type: ignore[abstract]


class TestRgbPageImageSource:
    def test_returns_image_unchanged_and_no_mask(self) -> None:
        image = Image.new("RGB", (4, 4), color=(10, 20, 30))

        rgb, mask = RgbPageImageSource().to_renderable(image)

        assert rgb is image
        assert mask is None


class TestAlphaPageImageSource:
    def test_alpha_becomes_mask_and_inverted_alpha_becomes_grayscale_rgb(self) -> None:
        # Pixel 1 fully opaque (alpha=255), pixel 2 fully transparent (alpha=0).
        image = Image.new("RGBA", (2, 1))
        image.putpixel((0, 0), (50, 60, 70, 255))
        image.putpixel((1, 0), (50, 60, 70, 0))

        rgb, mask = AlphaPageImageSource().to_renderable(image)

        assert rgb.mode == "RGB"
        assert mask is not None
        # Opaque source pixel → inverted alpha 0 → black ink on the page.
        assert rgb.getpixel((0, 0)) == (0, 0, 0)
        # Transparent source pixel → inverted alpha 255 → white (lets page show).
        assert rgb.getpixel((1, 0)) == (255, 255, 255)
        # Paste mask is the *original* alpha — opaque where ink should land.
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((1, 0)) == 0


class TestAdaptivePageImageSource:
    def test_rgba_dispatches_to_rgba_source(self) -> None:
        rgba_src = AlphaPageImageSource()
        rgb_src = RgbPageImageSource()
        adapter = AdaptivePageImageSource(rgba_source=rgba_src, rgb_source=rgb_src)

        rgba_image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 255))
        rgb, mask = adapter.to_renderable(rgba_image)

        # AlphaPageImageSource always emits an RGB image plus a mask.
        assert rgb.mode == "RGB"
        assert mask is not None

    def test_non_rgba_dispatches_to_rgb_source(self) -> None:
        adapter = AdaptivePageImageSource()
        rgb_image = Image.new("RGB", (1, 1), color=(1, 2, 3))

        rgb, mask = adapter.to_renderable(rgb_image)

        # RgbPageImageSource returns the input image as-is, no mask.
        assert rgb is rgb_image
        assert mask is None

    def test_defaults_match_the_module_constants(self) -> None:
        adapter = AdaptivePageImageSource()

        # RGBA → alpha pipeline (mask is not None).
        rgba_image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 0))
        _, mask = adapter.to_renderable(rgba_image)
        assert mask is not None

        # Non-RGBA (e.g. L) → rgb pipeline (mask is None).
        l_image = Image.new("L", (1, 1), color=128)
        _, mask = adapter.to_renderable(l_image)
        assert mask is None


class TestBuildSourceProfile:
    def test_frozen_dataclass_blocks_field_reassignment(self) -> None:
        profile = BuildSourceProfile(
            page_image_source=RgbPageImageSource(),
            srce_story_file_resolver=FinalStoryFileResolver(),
        )

        with pytest.raises(FrozenInstanceError):
            profile.page_image_source = RgbPageImageSource()  # ty: ignore[invalid-assignment]

    def test_rgb_profile_pairs_rgb_source_with_final_resolver(self) -> None:
        assert isinstance(RGB_PROFILE.page_image_source, RgbPageImageSource)
        assert isinstance(RGB_PROFILE.srce_story_file_resolver, FinalStoryFileResolver)

    def test_svg_adaptive_profile_pairs_adaptive_source_with_svg_resolver(self) -> None:
        assert isinstance(SVG_ADAPTIVE_PROFILE.page_image_source, AdaptivePageImageSource)
        assert isinstance(SVG_ADAPTIVE_PROFILE.srce_story_file_resolver, SvgPngStoryFileResolver)

    def test_svg_adaptive_profile_resolver_has_final_fallback(self) -> None:
        # The SVG-PNG resolver must fall back to the final story file so pages that
        # have not yet been SVG-rendered still render via the JPG pipeline.
        resolver = SVG_ADAPTIVE_PROFILE.srce_story_file_resolver
        assert isinstance(resolver, SvgPngStoryFileResolver)
        assert isinstance(resolver._fallback, FinalStoryFileResolver)  # noqa: SLF001
