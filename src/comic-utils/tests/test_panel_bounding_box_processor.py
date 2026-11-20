# ruff: noqa: PLR2004

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import comic_utils.panel_bounding_box_processor as processor_module
import pytest
from comic_utils.panel_bounding_box_processor import BoundingBoxProcessor
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

    from PIL.Image import Image as PilImage


class FakeKumiko:
    """Stand-in for `KumikoPanelSegmentation` that records the images and names it was given.

    With no answer set, each call returns panels whose bounds encode the image's size, so
    a test can tell which image produced which result. With one, every call returns it.
    """

    def __init__(self) -> None:
        self.images: list[PilImage] = []
        self.filenames: list[Path] = []
        self.answer: dict[str, Any] | None = None

    def get_panels_segment_info(self, srce_image: PilImage, srce_filename: Path) -> dict[str, Any]:
        self.images.append(srce_image)
        self.filenames.append(srce_filename)
        if self.answer is not None:
            return {**self.answer, "panels": [list(p) for p in self.answer["panels"]]}
        w, h = srce_image.size
        return {"panels": [[0, 0, w, h]], "processing_time": 0.1}


@pytest.fixture
def fake_kumiko() -> FakeKumiko:
    return FakeKumiko()


@pytest.fixture
def processor(tmp_path: Path, fake_kumiko: FakeKumiko) -> BoundingBoxProcessor:
    with patch.object(processor_module, "KumikoPanelSegmentation", return_value=fake_kumiko):
        return BoundingBoxProcessor(tmp_path / "work", tmp_path / "building")


def _write_image(path: Path, size: tuple[int, int], mode: str = "RGB") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size).save(path)
    return path


def _page(
    tmp_path: Path, stem: str = "010", size: tuple[int, int] = (30, 40), mode: str = "RGB"
) -> tuple[Path, Path]:
    """Write a page's source image; return it and its (empty) override directory."""
    srce = _write_image(tmp_path / "srce" / f"{stem}.png", size, mode)
    override_dir = tmp_path / "override"
    override_dir.mkdir()
    return srce, override_dir


class TestTheSegmenterItBuilds:
    @pytest.mark.parametrize(
        ("kwargs", "no_panel_expansion"),
        [
            pytest.param({}, False, id="expansion left on by default"),
            pytest.param({"no_panel_expansion": True}, True, id="expansion turned off"),
        ],
    )
    def test_it_is_given_the_directories_and_the_expansion_choice(
        self, tmp_path: Path, kwargs: dict[str, bool], no_panel_expansion: bool
    ) -> None:
        work_dir, building_dir = tmp_path / "work", tmp_path / "building"
        with patch.object(processor_module, "KumikoPanelSegmentation") as kumiko:
            BoundingBoxProcessor(work_dir, building_dir, **kwargs)

        kumiko.assert_called_once_with(work_dir, building_dir, no_panel_expansion)


class TestGetPanelsSegmentInfoFromKumiko:
    def test_uses_srce_file_when_no_override(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce, override_dir = _page(tmp_path)

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 1
        assert fake_kumiko.filenames == [srce]
        assert info["panels"] == [[0, 0, 30, 40]]
        assert info["overall_bounds"] == (0, 0, 29, 39)

    def test_image_is_converted_to_rgb(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce, override_dir = _page(tmp_path, size=(8, 8), mode="RGBA")

        processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert fake_kumiko.images[0].mode == "RGB"

    def test_uses_bounds_override_file(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce, override_dir = _page(tmp_path)
        _write_image(override_dir / "010.jpg", (50, 60))

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 1
        # Kumiko is given the override's image under the page's own name, which names
        # its work file.
        assert fake_kumiko.filenames == [srce]
        assert info["panels"] == [[0, 0, 50, 60]]
        assert info["overall_bounds"] == (0, 0, 49, 59)

    def test_overall_bounds_override_replaces_only_overall_bounds(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce, override_dir = _page(tmp_path)
        _write_image(override_dir / "010.jpg", (50, 60))
        _write_image(override_dir / "010-overall-bounds-only.jpg", (70, 80))

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 2
        assert fake_kumiko.filenames == [srce, srce]
        # Panels come from the bounds override; overall bounds from the overall override.
        assert info["panels"] == [[0, 0, 50, 60]]
        assert info["overall_bounds"] == (0, 0, 69, 79)

    def test_png_override_file_is_rejected(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce, override_dir = _page(tmp_path)
        _write_image(override_dir / "010.png", (50, 60))

        with pytest.raises(RuntimeError, match=r"should not be \.png"):
            processor.get_panels_segment_info_from_kumiko(srce, override_dir)

    def test_overall_override_without_bounds_override_is_rejected(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce, override_dir = _page(tmp_path)
        _write_image(override_dir / "010-overall-bounds-only.jpg", (70, 80))

        with pytest.raises(RuntimeError, match="AND NOT a bounds file"):
            processor.get_panels_segment_info_from_kumiko(srce, override_dir)


class TestSavePanelsSegmentInfo:
    def test_writes_json_without_processing_time(self, tmp_path: Path) -> None:
        out = tmp_path / "010.json"
        info = {"panels": [[1, 2, 3, 4]], "overall_bounds": (1, 2, 3, 5), "processing_time": 9.9}

        BoundingBoxProcessor.save_panels_segment_info(out, info)

        saved = out.read_text(encoding="utf-8")
        assert json.loads(saved) == {"panels": [[1, 2, 3, 4]], "overall_bounds": [1, 2, 3, 5]}
        assert saved.startswith("{\n    ")  # indent=4


# Two tiers of two panels, the right-hand column a little lower than the left, given
# column by column as kumiko gives a jogged page. Reading order is 1, 3, 2, 4.
JOGGED_PANELS = [[0, 0, 10, 10], [0, 20, 10, 10], [20, 2, 10, 10], [20, 22, 10, 10]]


class TestPanelOrdering:
    """Kumiko answers with a jogged page's panels, in its own column-wise order."""

    @pytest.fixture(autouse=True)
    def _jogged_page(self, fake_kumiko: FakeKumiko) -> None:
        fake_kumiko.answer = {"size": [30, 32], "panels": JOGGED_PANELS}

    def test_panels_are_returned_in_reading_order(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce, override_dir = _page(tmp_path, "020", (8, 8))

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        j = JOGGED_PANELS
        assert info["panels"] == [j[0], j[2], j[1], j[3]]
        assert info["overall_bounds"] == (0, 0, 29, 31)

    def test_panel_order_override_is_applied_after_sorting(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce, override_dir = _page(tmp_path, "020", (8, 8))
        (override_dir / "020-panel-order.json").write_text("[4, 3, 2, 1]", encoding="utf-8")

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        j = JOGGED_PANELS
        assert info["panels"] == [j[3], j[1], j[2], j[0]]

    def test_bad_panel_order_override_raises(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce, override_dir = _page(tmp_path, "020", (8, 8))
        (override_dir / "020-panel-order.json").write_text("[1, 2]", encoding="utf-8")

        with pytest.raises(ValueError, match="not a permutation"):
            processor.get_panels_segment_info_from_kumiko(srce, override_dir)

    def test_get_panel_order_override_without_file(self, tmp_path: Path) -> None:
        assert BoundingBoxProcessor.get_panel_order_override(tmp_path, tmp_path / "020.png") is None
