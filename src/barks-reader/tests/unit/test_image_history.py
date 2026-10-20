"""The images a view has shown (barks_reader.core.image_history)."""

# ruff: noqa: PLR2004

from __future__ import annotations

from pathlib import Path

from barks_reader.core.image_history import ImageHistory
from barks_reader.core.image_selector import ImageInfo


def _image(name: str) -> ImageInfo:
    return ImageInfo(filename=Path(name))


def test_back_and_forward_step_through_the_images_shown_and_stop_at_the_ends() -> None:
    history = ImageHistory(max_images=20)
    assert history.index == -1
    assert history.back() is None
    assert history.forward() is None

    history.add(_image("a"))
    history.add(_image("b"))
    history.add(_image("c"))
    assert history.index == 2
    assert history.back() == _image("b")
    assert history.back() == _image("a")
    assert history.back() is None
    assert history.forward() == _image("b")
    assert history.forward() == _image("c")
    assert history.forward() is None


def test_only_the_last_so_many_are_kept() -> None:
    history = ImageHistory(max_images=2)
    for name in "abc":
        history.add(_image(name))
    assert list(history.images) == [_image("b"), _image("c")]
    assert history.index == 1
