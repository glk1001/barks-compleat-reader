from . import cpi_inflate

cpi_inflate.check_for_stale_data()


def inflate(value: float, year_or_month: int) -> float:
    return cpi_inflate.inflate(value, year_or_month)
