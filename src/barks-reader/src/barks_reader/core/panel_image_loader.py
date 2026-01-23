import io
import zipfile
from collections.abc import Callable
from pathlib import Path
from threading import Thread

from comic_utils.comic_consts import PanelPath

# noinspection PyUnresolvedReferences
from comic_utils.get_panel_bytes import get_decrypted_bytes  # ty: ignore[unresolved-import]
from loguru import logger
from PIL import Image

from barks_reader.core.services import schedule_once

type ImageLoaderCallback = Callable[[Image.Image | None, Exception | None], None]


class PanelImageLoader:
    """Load an image in a background thread.

      From either:

      - PanelPath = filesystem Path
      - PanelPath = zipfile.Path

    Heavy work (I/O + Pillow decode) runs off the UI thread.
    Texture upload always happens on the UI thread (required by Kivy).
    """

    def __init__(self, barks_panels_are_encrypted: bool) -> None:
        self._barks_panels_are_encrypted = barks_panels_are_encrypted
        self._cancel = False
        self._current_thread: Thread | None = None

    def cancel(self) -> None:
        self._cancel = True

    def load_pil(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        self._start_worker(panel_path, callback=callback)

    def _start_worker(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        # Kill the current thread.
        if self._current_thread:
            self._cancel = True
            self._current_thread.join()

        self._cancel = False
        self._current_thread = Thread(
            target=self._worker,
            args=(panel_path, callback),
            daemon=True,
        )
        self._current_thread.start()

    def _worker(self, panel_path: PanelPath, callback: ImageLoaderCallback) -> None:
        # noinspection PyBroadException
        try:
            # PanelPath may be Path or zipfile.Path.
            if isinstance(panel_path, (Path, zipfile.Path)):
                raw = (
                    get_decrypted_bytes(panel_path.read_bytes())
                    if self._barks_panels_are_encrypted
                    else panel_path.read_bytes()
                )
            else:
                msg = f"Unsupported PanelPath type: {type(panel_path)}"
                raise TypeError(msg)  # noqa: TRY301

            if self._cancel:
                return

            pil = Image.open(io.BytesIO(raw))
            pil.load()
            pil = pil.convert("RGBA")  # ensures reliable texture creation

            if self._cancel:
                return

        except Exception as e:  # noqa: BLE001
            logger.exception("Error loading image:")
            ex = e
            schedule_once(lambda _dt: callback(None, ex), 0)
            return

        schedule_once(lambda _dt: callback(pil, None), 0)
