from collections.abc import Callable

from comic_utils.comic_consts import PanelPath

# noinspection PyProtectedMember
from kivy.core.image import Texture
from PIL import Image

from barks_reader.core.panel_image_loader import PanelImageLoader

type TextureLoaderCallback = Callable[[Texture | None, Exception | None], None]


class PanelTextureLoader(PanelImageLoader):
    """Load a texture in a background thread.

      From either:

      - PanelPath = filesystem Path
      - PanelPath = zipfile.Path

    Texture upload always happens on the UI thread (required by Kivy).
    """

    def __init__(self, barks_panels_are_encrypted: bool) -> None:
        super().__init__(barks_panels_are_encrypted)

    def load_texture(self, panel_path: PanelPath, callback: TextureLoaderCallback) -> None:
        def pil_callback(img: Image.Image | None, err: Exception | None) -> None:
            if err:
                callback(None, err)
                return

            assert img
            callback(self._pil_to_texture(img), None)

        self._start_worker(panel_path, callback=pil_callback)

    @staticmethod
    def _pil_to_texture(pil: Image.Image) -> Texture:
        # noinspection PyArgumentList
        tex = Texture.create(size=pil.size)
        tex.blit_buffer(pil.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()

        return tex
