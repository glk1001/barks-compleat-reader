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


def test_the_image_before_the_one_on_show_is_known_without_moving() -> None:
    history = ImageHistory(max_images=20)
    assert history.previous() is None
    history.add(_image("a"))
    assert history.previous() is None
    history.add(_image("b"))
    history.add(_image("c"))
    assert history.previous() == _image("b")
    assert history.index == 2
    history.back()
    assert history.previous() == _image("a")
    history.back()
    assert history.previous() is None


def test_an_image_added_as_the_oldest_goes_before_the_one_on_show() -> None:
    history = ImageHistory(max_images=3)
    assert history.add_oldest(_image("seed")) is True
    assert history.index == -1  # Nothing on show yet.
    history.add(_image("a"))
    assert list(history.images) == [_image("seed"), _image("a")]
    assert history.index == 1
    assert history.previous() == _image("seed")

    assert history.add_oldest(_image("older")) is True
    assert list(history.images) == [_image("older"), _image("seed"), _image("a")]
    assert history.index == 2
    # Full, the newest on show: the images shown are kept over one that never was.
    assert history.add_oldest(_image("dropped")) is False
    assert list(history.images) == [_image("older"), _image("seed"), _image("a")]
    assert history.index == 2


def test_a_full_history_drops_its_newest_for_one_added_at_the_oldest_end() -> None:
    """Stepping back past the oldest image rolls the window, as adding rolls the oldest off."""
    history = ImageHistory(max_images=3)
    for name in ("a", "b", "c"):
        history.add(_image(name))
    history.back()
    history.back()
    assert history.index == 0

    assert history.add_oldest(_image("seed")) is True
    assert list(history.images) == [_image("seed"), _image("a"), _image("b")]
    assert history.index == 1
    assert history.previous() == _image("seed")
    assert history.forward() == _image("b")
    assert history.forward() is None


def test_an_image_added_after_a_step_back_drops_the_images_ahead() -> None:
    """The lower tier once showed the old newest image, not the one just on show."""
    history = ImageHistory(max_images=20)
    for name in "abc":
        history.add(_image(name))
    history.back()
    history.back()

    history.add(_image("d"))

    assert list(history.images) == [_image("a"), _image("d")]
    assert history.index == 1
    assert history.previous() == _image("a")
    assert history.forward() is None


def test_an_image_added_at_the_newest_keeps_every_image() -> None:
    history = ImageHistory(max_images=20)
    history.add(_image("a"))
    history.add(_image("b"))
    assert list(history.images) == [_image("a"), _image("b")]


def test_the_first_image_added_keeps_the_seeds_put_behind() -> None:
    history = ImageHistory(max_images=20)
    history.add_oldest(_image("seed2"))
    history.add_oldest(_image("seed1"))

    history.add(_image("a"))

    assert list(history.images) == [_image("seed1"), _image("seed2"), _image("a")]
    assert history.index == 2


def test_an_image_added_as_the_oldest_of_an_empty_history_shows_nothing() -> None:
    history = ImageHistory(max_images=1)
    assert history.add_oldest(_image("seed")) is True
    assert list(history.images) == [_image("seed")]
    assert history.index == -1
    assert history.previous() is None
    # Full with nothing on show: a seed may still replace the newest.
    assert history.add_oldest(_image("older")) is True
    assert list(history.images) == [_image("older")]
    assert history.index == -1
