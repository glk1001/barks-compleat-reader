from __future__ import annotations

from threading import Thread
from typing import TYPE_CHECKING

from loguru import logger
from PIL import Image

from .image_pipeline import convert_mode, load_pil

if TYPE_CHECKING:
    from collections.abc import Callable

    from comic_utils.comic_consts import PanelPath

    from .ports import Scheduler

type ImageLoaderCallback = Callable[[Image.Image | None, Exception | None], None]


class PanelImageLoader:
    """Load an image in a background thread.

      From either:

      - PanelPath = filesystem Path
      - PanelPath = zipfile.Path

    Heavy work (I/O + Pillow decode) runs off the UI thread.
    Texture upload always happens on the UI thread (required by Kivy).
    """

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler
        self._cancel = False
        self._current_thread: Thread | None = None

    def cancel(self) -> None:
        """Cancel the current load if one is in flight."""
        self._cancel = True

    def load_pil(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        """Schedule *panel_path* to be decoded; *callback* fires on the UI thread."""
        self._start_worker(panel_path, callback=callback)

    def _start_worker(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        # Kill the current thread.
        if self._current_thread:
            self._cancel = True
            self._current_thread.join()

        self._cancel = False
        current_thread = Thread(
            target=self._worker,
            args=(panel_path, callback),
            daemon=True,
        )
        current_thread.start()
        self._current_thread = current_thread

    def _worker(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        try:
            # Panel zipfile.Path bytes are always encrypted in this app.
            pil = load_pil(panel_path, encrypted_zip=True)

            if self._cancel:
                return

            pil = convert_mode(pil, "RGBA")  # ensures reliable texture creation

            if self._cancel:
                return

        except Exception as e:  # noqa: BLE001
            logger.exception(f'Error loading image "{panel_path}":')
            ex = e
            self._scheduler.schedule_once(lambda: callback(None, ex))
            return

        self._scheduler.schedule_once(lambda: callback(pil, None))
