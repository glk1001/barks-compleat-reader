"""The images a view has shown, the last so many, and a place in them. Kivy-free."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .image_selector import ImageInfo


class ImageHistory:
    """The last `max_images` images shown, and which of them is on show.

    Attributes:
        images: The images, oldest first; the oldest drops out past `max_images`.
        index: The image on show, or -1 with none shown yet.

    """

    def __init__(self, max_images: int) -> None:
        """Make an empty history that keeps the last `max_images` images."""
        self.images: deque[ImageInfo] = deque(maxlen=max_images)
        self.index = -1

    def add(self, image_info: ImageInfo) -> None:
        """Record `image_info` as the image on show, the newest."""
        self.images.append(image_info)
        self.index = len(self.images) - 1

    def back(self) -> ImageInfo | None:
        """Step to the image before the one on show and return it, or None at the oldest."""
        if self.index <= 0:
            return None
        self.index -= 1
        return self.images[self.index]

    def forward(self) -> ImageInfo | None:
        """Step to the image after the one on show and return it, or None at the newest."""
        if self.index >= len(self.images) - 1:
            return None
        self.index += 1
        return self.images[self.index]
