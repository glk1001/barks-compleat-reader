LOGGER_SYS_NAME_KEY = "sys_name"


# Global formatter function for 'loguru-config'.
# noinspection Annotator
def log_to_file_formatter(_record) -> str:  # noqa: ANN001
    return _get_log_color_format_string(module_etc_at_end=False)


# Global formatter function for 'loguru-config'.
# noinspection Annotator
def log_to_console_formatter(_record) -> str:  # noqa: ANN001
    return _get_log_color_format_string(module_etc_at_end=True)


def _get_log_color_format_string(module_etc_at_end: bool = False) -> str:
    sys_name_fmt = f"<yellow>{{extra[{LOGGER_SYS_NAME_KEY}]: <4}}: </yellow>"
    module_fmt_str = "{name}:{function}:{line}"
    module_etc_fmt = "" if module_etc_at_end else f"<cyan>{module_fmt_str} - </cyan>"
    module_etc_at_end_fmt = f"  <cyan>[{module_fmt_str}]</cyan>" if module_etc_at_end else ""

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"{sys_name_fmt}"
        f"{module_etc_fmt}"
        "<level>{message}</level>"
        f"{module_etc_at_end_fmt}"
        "\n"
        "{exception}"
    )


if __name__ == "__main__":
    import sys

    from loguru import logger

    @logger.catch
    def func_with_exception() -> None:
        # noinspection Annotator
        print("About to raise ex")  # noqa: T201
        y = 1
        # noinspection PyUnusedLocal,Annotator
        x = y / 0  # noqa: F841

    logger.configure(extra={"sys_name": "app"})

    logger.remove()
    logger.add(sys.stderr, format=log_to_console_formatter, backtrace=True, diagnose=True)

    logger.debug("Debug message.")
    logger.info("Info message.")
    logger.warning("Warning message.")
    logger.error("Error message.")
    logger.critical("Critical message.")

    logger = logger.patch(lambda record: record["extra"].update(sys_name="app2"))
    logger.warning("Warning message patched.")

    logger.info("Tricky message with curly braces {}")

    # noinspection PyBroadException
    try:
        func_with_exception()
    except Exception:
        logger.exception("Ex")
