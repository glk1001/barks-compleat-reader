"""A loaded comic page as the pixels a texture is filled from. Kivy-free."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image as PilImage

if TYPE_CHECKING:
    from PIL.Image import Image

# The pixel layouts a texture takes as they are; any other is converted to RGB.
TEXTURE_MODES = ("RGB", "RGBA")


@dataclass(frozen=True, slots=True)
class PageImage:
    """A display-ready page: its size, its pixel layout and the pixels themselves.

    The loader used to hand each page over as a level-0 PNG stream for Kivy to
    decode again. Level 0 is the raw pixels with headers around them, so the encode
    and the decode bought nothing; the texture is filled straight from these bytes.

    Attributes:
        width: The page's width in pixels.
        height: The page's height in pixels.
        mode: The pixel layout, ``"RGB"`` or ``"RGBA"``, as PIL names it; a texture's
            color format is the same name in lower case.
        pixels: The rows top to bottom, packed as *mode* says.

    """

    width: int
    height: int
    mode: str
    pixels: bytes

    @classmethod
    def from_pil(cls, pil_image: Image) -> PageImage:
        """Take a PIL image's pixels, converting any layout but RGB and RGBA to RGB.

        Args:
            pil_image: The resized page.

        Returns:
            The page as a texture takes it.

        """
        if pil_image.mode not in TEXTURE_MODES:
            pil_image = pil_image.convert("RGB")
        return cls(pil_image.width, pil_image.height, pil_image.mode, pil_image.tobytes())

    def to_pil(self) -> Image:
        """Return a read-only PIL image over these pixels, for compositing; no copy is made."""
        return PilImage.frombuffer(
            self.mode, (self.width, self.height), self.pixels, "raw", self.mode, 0, 1
        )

    @property
    def nbytes(self) -> int:
        """The memory the pixels hold."""
        return len(self.pixels)
