"""The statistics generator draws every chart and writes the sidecar it was drawn from."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import generate_stats_images as gen
from barks_reader.core.statistics_series import (
    CHART_DATA_FILE,
    CHART_FILES,
    MOST_FREQUENT_FILE,
    all_series,
    load_series,
)
from PIL import Image

if TYPE_CHECKING:
    import pytest


class TestMain:
    def test_writes_every_chart_and_the_sidecar(self, tmp_path: Path) -> None:
        gen.main(tmp_path, None)

        pngs = sorted(p.name for p in tmp_path.glob("*.png"))
        assert pngs == sorted(CHART_FILES.values())
        for name in pngs:
            with Image.open(tmp_path / name) as image:
                assert image.size[0] > 1000  # noqa: PLR2004
        assert load_series((tmp_path / CHART_DATA_FILE).read_text(encoding="utf-8")) == all_series()

    def test_a_quoted_tilde_is_the_home_folder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        gen.main(Path("~/Statistics"), None)

        assert (tmp_path / "Statistics" / CHART_DATA_FILE).is_file()
        assert not (tmp_path / "~").exists()

    def test_the_word_table_needs_the_index(self, tmp_path: Path) -> None:
        gen.gen_word_statistics(tmp_path, tmp_path / "no-such-indexes")
        assert not (tmp_path / MOST_FREQUENT_FILE).exists()

    def test_the_word_table_from_a_small_term_list(self, tmp_path: Path) -> None:
        indexes = tmp_path / "Indexes"
        indexes.mkdir()
        terms = [[f"word{i}", 100 - i] for i in range(12)]
        (indexes / "most-common-unstemmed-terms.json").write_text(
            json.dumps(terms), encoding="utf-8"
        )
        gen.gen_word_statistics(tmp_path, indexes)
        assert (tmp_path / MOST_FREQUENT_FILE).is_file()


class TestPlotters:
    def test_one_plotter_per_chart(self) -> None:
        assert gen.PLOTTERS.keys() == CHART_FILES.keys()
