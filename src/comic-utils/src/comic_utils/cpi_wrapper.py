from loguru import logger

from .timing import Timing


def inflate(value: float, year_or_month: int) -> float:
    from comic_utils.cpi_loader import cpi_loader  # noqa: PLC0415

    if not cpi_loader.ready_event.is_set():
        logger.warning("CPI module is not ready yet. Waiting...")
        timing = Timing()

        cpi_loader.wait_until_ready()

        logger.warning(f"CPI module is ready (after {timing.get_elapsed_time_with_unit()}).")

    if cpi_loader.error:
        return -1.0

    from . import cpi_inflate  # noqa: PLC0415

    return cpi_inflate.inflate(value, year_or_month)
