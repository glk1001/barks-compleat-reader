def inflate(value: float, year_or_month: int) -> float:
    from . import cpi_inflate  # noqa: PLC0415

    return cpi_inflate.inflate(value, year_or_month)
