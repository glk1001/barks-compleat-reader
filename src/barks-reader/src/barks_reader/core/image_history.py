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

    def add_oldest(self, image_info: ImageInfo) -> bool:
        """Record `image_info` as the oldest, before every image shown; the on-show one stays.

        A full history drops its newest image to make room, as `add` drops the oldest:
        the window of images kept moves with the one on show (a step back at the oldest
        image on the spread seeds behind it, and a full history refused it, 2026-10-30).

        Returns:
            Whether it was added: a full history whose newest image is on show keeps
            what it has.

        """
        if len(self.images) == self.images.maxlen:
            if self.index == len(self.images) - 1:
                return False
            self.images.pop()
        self.images.appendleft(image_info)
        if self.index >= 0:
            self.index += 1
        return True

    def previous(self) -> ImageInfo | None:
        """Return the image before the one on show, without moving, or None at the oldest."""
        if self.index <= 0:
            return None
        return self.images[self.index - 1]

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
