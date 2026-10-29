"""The logging handler that sends Kivy's log lines to the app's loguru log.

Kivy logs through the standard library's logging; ``main.py`` adds this handler to
Kivy's logger. Nothing here imports Kivy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger


class LoguruKivyHandler(logging.Handler):
    """Log each of Kivy's records through loguru, under `sys_name`, from where Kivy logged it."""

    def __init__(self, logr: Logger, sys_name: str) -> None:
        self.logr = logr
        self.sys_name = sys_name
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        """Log `record` through loguru at its level, with its exception if it has one.

        The exception goes through ``opt``, not the patch: loguru then wraps it as one
        of its own records' exceptions, which drops the traceback when the app log's
        queued sink pickles the record. A bare ``exc_info`` there broke that pickling,
        and the line and its traceback went to stderr as a loguru logging error.
        """

        # Untyped: loguru types these fields as its own records' objects, but its
        # formatters take Kivy's plain values as they are.
        def patch_loguru_rec(rec) -> None:  # noqa: ANN001
            rec.update(file=record.filename)
            rec.update(function=record.funcName)
            rec.update(line=record.lineno)
            rec.update(module=record.module)
            rec.update(name=record.name)
            rec.update(process=record.process)
            rec.update(thread=record.thread)

        # noinspection PyBroadException
        try:
            patched_logger = self.logr.patch(patch_loguru_rec).opt(exception=record.exc_info)
            level = logging.getLevelName(record.levelno).lower()

            # Kivy emits this message: "kivy: Modules: Start <inspector> with config {}"
            # which we need to be careful with.
            message = record.getMessage().replace("{", "{{").replace("}", "}}")

            # Now log the kivy information using Loguru.
            # Use getattr to call the appropriate logging method based on level.
            # And fallback to 'info'.
            log_method = getattr(patched_logger, level, patched_logger.info)
            log_method(message, sys_name=self.sys_name)
        except Exception:
            self.logr.exception("Error in LoguruKivyHandler.emit: ")
