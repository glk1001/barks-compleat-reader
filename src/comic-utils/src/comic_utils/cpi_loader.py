from threading import Event, Thread

from loguru import logger

from comic_utils.timing import Timing


class CpiModuleLoader:
    def __init__(self) -> None:
        self.ready_event = Event()
        self.module = None
        self.error = None

    def start_async(self) -> None:
        timing = Timing()
        logger.debug("Start loading CPI module.")

        def worker() -> None:
            try:
                import comic_utils.cpi_inflate as cpi  # noqa: PLC0415

                self.module = cpi
                self.ready_event.set()

                logger.debug(
                    f"CPI module has been loaded (in {timing.get_elapsed_time_with_unit()})."
                )

            except Exception as e:  # noqa: BLE001
                logger.exception("Could not import CPI:")
                self.error = e
                self.ready_event.set()

        Thread(target=worker, daemon=True).start()

    def wait_until_ready(self, timeout: float = -1.0):  # noqa: ANN201
        """Block until module is ready or timeout (None = wait forever)."""
        self.ready_event.wait(None if timeout < 0 else timeout)

        return self.module


cpi_loader = CpiModuleLoader()
