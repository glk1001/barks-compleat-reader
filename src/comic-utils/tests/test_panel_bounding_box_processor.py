# ruff: noqa: PLR2004

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import patch

import comic_utils.panel_bounding_box_processor as processor_module
import pytest
from comic_utils.panel_bounding_box_processor import BoundingBoxProcessor
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

    from PIL.Image import Image as PilImage


class FakeKumiko:
    """Stand-in for `KumikoPanelSegmentation` that records the images it was given.

    Each call returns panels whose bounds encode the image's size, so a test can tell
    which image produced which result.
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        self.images: list[PilImage] = []

    def get_panels_segment_info(self, srce_image: PilImage, _srce_filename: Path) -> dict[str, Any]:
        self.images.append(srce_image)
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


class TestGetPanelsSegmentInfoFromKumiko:
    def test_uses_srce_file_when_no_override(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (30, 40))
        override_dir = tmp_path / "override"
        override_dir.mkdir()

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 1
        assert info["panels"] == [[0, 0, 30, 40]]
        assert info["overall_bounds"] == (0, 0, 29, 39)

    def test_image_is_converted_to_rgb(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (8, 8), mode="RGBA")
        override_dir = tmp_path / "override"
        override_dir.mkdir()

        processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert fake_kumiko.images[0].mode == "RGB"

    def test_uses_bounds_override_file(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (30, 40))
        override_dir = tmp_path / "override"
        _write_image(override_dir / "010.jpg", (50, 60))

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 1
        assert info["panels"] == [[0, 0, 50, 60]]
        assert info["overall_bounds"] == (0, 0, 49, 59)

    def test_overall_bounds_override_replaces_only_overall_bounds(
        self, tmp_path: Path, processor: BoundingBoxProcessor, fake_kumiko: FakeKumiko
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (30, 40))
        override_dir = tmp_path / "override"
        _write_image(override_dir / "010.jpg", (50, 60))
        _write_image(override_dir / "010-overall-bounds-only.jpg", (70, 80))

        info = processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        assert len(fake_kumiko.images) == 2
        # Panels come from the bounds override; overall bounds from the overall override.
        assert info["panels"] == [[0, 0, 50, 60]]
        assert info["overall_bounds"] == (0, 0, 69, 79)

    def test_png_override_file_is_rejected(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (30, 40))
        override_dir = tmp_path / "override"
        _write_image(override_dir / "010.png", (50, 60))

        with pytest.raises(RuntimeError, match=r"should not be \.png"):
            processor.get_panels_segment_info_from_kumiko(srce, override_dir)

    def test_overall_override_without_bounds_override_is_rejected(
        self, tmp_path: Path, processor: BoundingBoxProcessor
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "010.png", (30, 40))
        override_dir = tmp_path / "override"
        _write_image(override_dir / "010-overall-bounds-only.jpg", (70, 80))

        with pytest.raises(RuntimeError, match="AND NOT a bounds file"):
            processor.get_panels_segment_info_from_kumiko(srce, override_dir)


class TestSavePanelsSegmentInfo:
    def test_writes_json_without_processing_time(self, tmp_path: Path) -> None:
        out = tmp_path / "010.json"
        info = {"panels": [[1, 2, 3, 4]], "overall_bounds": (1, 2, 3, 5), "processing_time": 9.9}

        BoundingBoxProcessor.save_panels_segment_info(out, info)

        saved = json.loads(out.read_text())
        assert saved == {"panels": [[1, 2, 3, 4]], "overall_bounds": [1, 2, 3, 5]}
        assert out.read_text().startswith("{\n    ")  # indent=4


class UnsortedKumiko:
    """Returns Vol 10 p020's panels in kumiko's column-wise order."""

    JOGGED: ClassVar[list[list[int]]] = [
        [222, 194, 965, 511],
        [222, 731, 994, 780],
        [1189, 194, 885, 648],
        [1218, 868, 856, 647],
    ]

    def get_panels_segment_info(self, _image: PilImage, _srce_filename: Path) -> dict[str, Any]:
        return {"size": [2216, 3056], "panels": [list(p) for p in self.JOGGED]}


@pytest.fixture
def unsorted_processor(tmp_path: Path) -> BoundingBoxProcessor:
    with patch.object(processor_module, "KumikoPanelSegmentation", return_value=UnsortedKumiko()):
        return BoundingBoxProcessor(tmp_path / "work", tmp_path / "building")


class TestPanelOrdering:
    def test_panels_are_saved_in_reading_order(
        self, tmp_path: Path, unsorted_processor: BoundingBoxProcessor
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "020.png", (8, 8))
        override_dir = tmp_path / "override"
        override_dir.mkdir()

        info = unsorted_processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        j = UnsortedKumiko.JOGGED
        assert info["panels"] == [j[0], j[2], j[1], j[3]]
        assert info["overall_bounds"] == (222, 194, 2073, 1514)

    def test_panel_order_override_is_applied_after_sorting(
        self, tmp_path: Path, unsorted_processor: BoundingBoxProcessor
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "020.png", (8, 8))
        override_dir = tmp_path / "override"
        override_dir.mkdir()
        (override_dir / "020-panel-order.json").write_text("[4, 3, 2, 1]")

        info = unsorted_processor.get_panels_segment_info_from_kumiko(srce, override_dir)

        j = UnsortedKumiko.JOGGED
        assert info["panels"] == [j[3], j[1], j[2], j[0]]

    def test_bad_panel_order_override_raises(
        self, tmp_path: Path, unsorted_processor: BoundingBoxProcessor
    ) -> None:
        srce = _write_image(tmp_path / "srce" / "020.png", (8, 8))
        override_dir = tmp_path / "override"
        override_dir.mkdir()
        (override_dir / "020-panel-order.json").write_text("[1, 2]")

        with pytest.raises(ValueError, match="not a permutation"):
            unsorted_processor.get_panels_segment_info_from_kumiko(srce, override_dir)

    def test_get_panel_order_override_without_file(self, tmp_path: Path) -> None:
        assert BoundingBoxProcessor.get_panel_order_override(tmp_path, tmp_path / "020.png") is None
