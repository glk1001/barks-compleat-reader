import os
import sys

from loguru import Record, logger

os.environ["KIVY_LOG_MODE"] = "MIXED"


def formatter(_record: Record) -> str:
    name_fmt = "<cyan>{extra[sys_name]: <4}</cyan>"

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"{name_fmt}: "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        "\n"
        "{exception}"
    )


@logger.catch
def func_with_exception() -> None:
    print("About to raise ex")
    y = 1
    x = y / 0


logger.configure(extra={"sys_name": "app"})

logger.remove()
logger.add(sys.stderr, format=formatter, backtrace=True, diagnose=True)
# logger.add(sys.stderr, backtrace=True, diagnose=True)

# setup_logging(log_level=logging.DEBUG)

logger.debug("Debug message.")
logger.info("Info message.")
logger.warning("Warning message.")
logger.error("Error message.")
logger.critical("Critical message.")

logger = logger.patch(lambda record: record["extra"].update(sys_name="app2"))
logger.warning("Warning message patched.")

try:
    func_with_exception()
except Exception:
    logger.exception("Ex")
