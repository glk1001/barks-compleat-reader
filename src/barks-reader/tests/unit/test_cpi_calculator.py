"""The inflation calculator, over a small table and over the one the app ships."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import patch

import pytest
from comic_utils import cpi_calculator
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year
from comic_utils.cpi_table import ANNUAL_CPI, SERIES_ID

_TWO_YEARS = MappingProxyType({1945: 10.0, 2025: 20.0})


@pytest.fixture
def two_years() -> object:
    with patch.object(cpi_calculator, "ANNUAL_CPI", _TWO_YEARS):
        yield


@pytest.mark.usefixtures("two_years")
class TestTheArithmetic:
    def test_dollars_scale_by_the_ratio_of_the_years_cpi(self) -> None:
        assert get_adjusted_usd(100.0, 1945, 2025) == pytest.approx(200.0)

    def test_the_same_year_is_the_same_amount(self) -> None:
        assert get_adjusted_usd(50.0, 1945, 1945) == pytest.approx(50.0)

    def test_the_target_year_defaults_to_the_latest(self) -> None:
        assert get_adjusted_usd(100.0, 1945) == pytest.approx(200.0)
        assert get_latest_year() == 2025  # noqa: PLR2004

    def test_a_year_the_table_lacks_names_the_tables_range(self) -> None:
        with pytest.raises(ValueError, match=r"No CPI data for 1900 .* \(1945-2025\)"):
            get_adjusted_usd(100.0, 1900, 2025)
        with pytest.raises(ValueError, match="No CPI data for 2030"):
            get_adjusted_usd(100.0, 1945, 2030)


class TestTheShippedTable:
    def test_it_is_the_all_items_cpi_u_from_1913(self) -> None:
        assert SERIES_ID == "CUUR0000SA0"
        assert min(ANNUAL_CPI) == 1913  # noqa: PLR2004

    def test_its_years_run_without_gaps_to_the_latest(self) -> None:
        assert list(ANNUAL_CPI) == list(range(1913, get_latest_year() + 1))

    def test_prices_rose_across_the_century(self) -> None:
        assert ANNUAL_CPI[1950] > ANNUAL_CPI[1913] * 2
        assert ANNUAL_CPI[get_latest_year()] > ANNUAL_CPI[1950] * 10

    def test_it_cannot_be_changed_in_place(self) -> None:
        """Every caller shares the one table."""
        with pytest.raises(TypeError):
            ANNUAL_CPI[1913] = 1.0  # ty: ignore[invalid-assignment]
