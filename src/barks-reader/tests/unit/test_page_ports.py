"""The page ports' contracts: the adapters the app wires in satisfy them.

The ports are imported only for type checking, so nothing else runs them; they are
``runtime_checkable``, so a check here fails when an adapter loses or renames a
method the loader calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_reader.core.archive_page_image_source import ArchivePageImageSource
from barks_reader.core.page_image_source import PageImageSource
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter
from barks_reader.core.page_info_ports import RequiredDimensionsPort, SortedPagesPort

if TYPE_CHECKING:
    from pathlib import Path


def test_the_panel_segments_adapter_serves_both_page_info_ports(tmp_path: Path) -> None:
    adapter = FantagraphicsPanelSegmentsAdapter(MagicMock(), tmp_path)
    assert isinstance(adapter, SortedPagesPort)
    assert isinstance(adapter, RequiredDimensionsPort)


def test_the_archive_source_is_a_page_image_source(tmp_path: Path) -> None:
    source = ArchivePageImageSource(
        archive_path=tmp_path / "comic.cbz",
        fanta_volume_archive=None,
        comic_book_image_builder=None,
        empty_page_image=b"",
        use_fantagraphics_overrides=False,
        max_width=200,
        max_height=200,
    )
    assert isinstance(source, PageImageSource)


def test_an_object_without_the_methods_is_no_port() -> None:
    stranger = object()
    assert not isinstance(stranger, SortedPagesPort)
    assert not isinstance(stranger, RequiredDimensionsPort)
    assert not isinstance(stranger, PageImageSource)
