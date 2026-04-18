from collections.abc import Callable

from comic_utils.comic_consts import PanelPath
from kivy.core.image import Texture
from PIL import Image

from barks_reader.core.panel_image_loader import PanelImageLoader

type TextureLoaderCallback = Callable[[Texture | None, Exception | None], None]


class PanelTextureLoader:
    """Load a texture in a background thread.

      From either:

      - PanelPath = filesystem Path
      - PanelPath = zipfile.Path

    Composes a :class:`PanelImageLoader` for the off-UI read/decode work, and
    uploads the resulting PIL image to a Kivy texture on the UI thread.
    """

    def __init__(self, pil_loader: PanelImageLoader | None = None) -> None:
        self._pil_loader = pil_loader if pil_loader is not None else PanelImageLoader()

    def cancel(self) -> None:
        self._pil_loader.cancel()

    def load_texture(self, panel_path: PanelPath, callback: TextureLoaderCallback) -> None:
        def pil_callback(img: Image.Image | None, err: Exception | None) -> None:
            if err is not None:
                callback(None, err)
                return

            assert img is not None
            callback(self._pil_to_texture(img), None)

        self._pil_loader.load_pil(panel_path, pil_callback)

    @staticmethod
    def _pil_to_texture(pil: Image.Image) -> Texture:
        tex = Texture.create(size=pil.size)
        tex.blit_buffer(pil.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()

        return tex
