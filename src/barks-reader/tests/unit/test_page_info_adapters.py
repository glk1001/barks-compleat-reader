"""Unit tests for :class:`FantagraphicsPanelSegmentsAdapter`.

The adapter caches the shared Fantagraphics sort-pages call so the two
port methods (sorted-pages and required-dimensions) only trigger a single
round of panel-segment JSON I/O per comic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from barks_fantagraphics import pages as fanta_pages
from barks_reader.core import page_info_adapters
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter

if TYPE_CHECKING:
    from pathlib import Path


def _make_sorted_pages_return(
    srce_and_dest: object, required_dim: object
) -> tuple[object, object, object]:
    # The helper returns (srce_and_dest_pages, srce_dim, required_dim).
    return srce_and_dest, MagicMock(name="srce_dim"), required_dim


class TestFantagraphicsPanelSegmentsAdapter:
    def test_get_sorted_pages_loads_and_caches_per_comic(self, tmp_path: Path) -> None:
        srce_and_dest = MagicMock(name="srce_and_dest")
        required_dim = MagicMock(name="required_dim")

        comics_database = MagicMock()
        comics_database.get_fantagraphics_volume_title.return_value = "CBDL-10"

        comic = MagicMock()
        comic.get_fanta_volume.return_value = 10

        adapter = FantagraphicsPanelSegmentsAdapter(comics_database, tmp_path)

        with patch.object(
            page_info_adapters,
            "get_sorted_srce_and_dest_pages_with_dimensions",
            return_value=_make_sorted_pages_return(srce_and_dest, required_dim),
        ) as mock_helper:
            first = adapter.get_sorted_pages(comic)
            second = adapter.get_required_dimensions(comic)

        assert first is srce_and_dest
        assert second is required_dim
        # The cache guarantees one I/O round per comic.
        assert mock_helper.call_count == 1
        comics_database.get_fantagraphics_volume_title.assert_called_once_with(10)

    def test_passes_expected_kwargs_to_helper(self, tmp_path: Path) -> None:
        comics_database = MagicMock()
        comics_database.get_fantagraphics_volume_title.return_value = "CBDL-03"
        comic = MagicMock()
        comic.get_fanta_volume.return_value = 3

        adapter = FantagraphicsPanelSegmentsAdapter(comics_database, tmp_path)

        with patch.object(
            page_info_adapters,
            "get_sorted_srce_and_dest_pages_with_dimensions",
            return_value=_make_sorted_pages_return(MagicMock(name="sad"), MagicMock(name="rd")),
        ) as mock_helper:
            adapter.get_sorted_pages(comic)

        kwargs = mock_helper.call_args.kwargs
        assert kwargs["get_full_paths"] is False
        assert kwargs["check_srce_page_timestamps"] is False
        assert callable(kwargs["get_srce_panel_segments_file"])

        # The derived getter should point inside the per-volume subdirectory
        # and append the JSON extension.
        segments_file = kwargs["get_srce_panel_segments_file"]("007")
        assert segments_file.parent == tmp_path / "CBDL-03"
        assert segments_file.name == "007.json"

    def test_switching_comics_reloads(self, tmp_path: Path) -> None:
        comics_database = MagicMock()
        comics_database.get_fantagraphics_volume_title.side_effect = lambda v: f"CBDL-{v:02d}"

        comic_a = MagicMock()
        comic_a.get_fanta_volume.return_value = 1
        comic_b = MagicMock()
        comic_b.get_fanta_volume.return_value = 2

        adapter = FantagraphicsPanelSegmentsAdapter(comics_database, tmp_path)

        with patch.object(
            page_info_adapters,
            "get_sorted_srce_and_dest_pages_with_dimensions",
            return_value=_make_sorted_pages_return(MagicMock(name="sad"), MagicMock(name="rd")),
        ) as mock_helper:
            adapter.get_sorted_pages(comic_a)
            adapter.get_required_dimensions(comic_a)  # cached
            adapter.get_sorted_pages(comic_b)  # must reload

        assert mock_helper.call_count == 2  # noqa: PLR2004

    def test_adapter_is_real_helper_compatible(self, tmp_path: Path) -> None:
        # Sanity check: the symbol the adapter imports is the one re-exported
        # from barks_fantagraphics.pages (guards against a silent rename).
        assert (
            page_info_adapters.get_sorted_srce_and_dest_pages_with_dimensions
            is fanta_pages.get_sorted_srce_and_dest_pages_with_dimensions
        )
        # And the adapter can be constructed.
        assert FantagraphicsPanelSegmentsAdapter(MagicMock(), tmp_path) is not None
