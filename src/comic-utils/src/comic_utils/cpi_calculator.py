"""US dollars of one year in another's, by the CPI-U (``cpi_table.py``).

The table is generated from the BLS by ``python -m comic_utils.update_cpi_table``;
its latest year moves with each update, so callers ask for it rather than hardcode it.
"""

from .cpi_table import ANNUAL_CPI, SERIES_ID


def get_latest_year() -> int:
    """Return the most recent year the CPI table has."""
    return max(ANNUAL_CPI)


def _cpi(year: int) -> float:
    try:
        return ANNUAL_CPI[year]
    except KeyError:
        msg = f"No CPI data for {year} in series {SERIES_ID} ({min(ANNUAL_CPI)}-{max(ANNUAL_CPI)})"
        raise ValueError(msg) from None


def get_adjusted_usd(amount: float, base_year: int, to_year: int | None = None) -> float:
    """Return `amount` US dollars of `base_year` in the dollars of `to_year`.

    Args:
        amount: The amount of money to convert.
        base_year: The year the amount is from.
        to_year: The year to convert to; the table's latest when None.

    Raises:
        ValueError: If the table has no figure for either year.

    """
    if to_year is None:
        to_year = get_latest_year()
    return _cpi(to_year) / _cpi(base_year) * amount
