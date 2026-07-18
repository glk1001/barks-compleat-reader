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


def load_panel_pil(panel_path: PanelPath, *, encrypted_zip: bool = True) -> Image.Image:
    """Load a panel image synchronously (allow-listed decrypt entry point).

    This module is on the compiled decryptor's caller allow-list; all panel
    loading that may hit an encrypted zip must be initiated from here.

    Args:
        panel_path: Filesystem ``Path`` or ``zipfile.Path`` of the panel image.
        encrypted_zip: Whether zip members are encrypted (ignored for
            filesystem paths).

    Returns:
        The decoded PIL image.

    """
    return load_pil(panel_path, encrypted_zip=encrypted_zip)


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
        # Bumped on every new load or cancel; a worker whose captured generation
        # no longer matches is stale and must drop its result. This avoids ever
        # blocking the UI thread waiting for a superseded decode to finish.
        self._generation = 0

    def cancel(self) -> None:
        """Cancel the current load if one is in flight."""
        self._generation += 1

    def load_pil(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        """Schedule *panel_path* to be decoded; *callback* fires on the UI thread."""
        self._start_worker(panel_path, callback=callback)

    def _start_worker(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        self._generation += 1
        Thread(
            target=self._worker,
            args=(panel_path, callback, self._generation),
            daemon=True,
        ).start()

    def _worker(self, panel_path: PanelPath, callback: ImageLoaderCallback, gen: int) -> None:
        try:
            # Panel zipfile.Path bytes are always encrypted in this app.
            pil = load_panel_pil(panel_path)

            if self._generation != gen:
                return

            pil = convert_mode(pil, "RGBA")  # ensures reliable texture creation

            if self._generation != gen:
                return

        except Exception as e:  # noqa: BLE001
            logger.exception(f'Error loading image "{panel_path}":')
            ex = e
            self._scheduler.schedule_once(lambda: self._deliver(gen, callback, None, ex))
            return

        self._scheduler.schedule_once(lambda: self._deliver(gen, callback, pil, None))

    def _deliver(
        self,
        gen: int,
        callback: ImageLoaderCallback,
        pil: Image.Image | None,
        error: Exception | None,
    ) -> None:
        # Re-check on the UI thread: a stale worker may have scheduled its
        # callback just before a newer load bumped the generation.
        if self._generation == gen:
            callback(pil, error)
