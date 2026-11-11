"""Which transition a screen switch uses: one of a pool at random, or the one a test names."""

from __future__ import annotations

import os
import random

# Names the one transition every screen switch uses, by its class ("CardTransition"), in
# place of the random pick: a GUI test of what only some transitions do sets it. A
# transition that moves the two screens themselves (card, slide, swap) keeps the screen
# being left laid out in the window until it ends; one that draws them through a shader
# does not.
SCREEN_TRANSITION_ENV_VAR = "BARKS_READER_SCREEN_TRANSITION"


def pick_transition[T](pool: list[T]) -> T:
    """Return the pool's transition the environment names, or one of them at random.

    Args:
        pool: The transitions a switch may use.

    Returns:
        The one whose class is named by ``BARKS_READER_SCREEN_TRANSITION`` (a leading
        underscore on the class's name aside), else a random one.

    """
    wanted = os.environ.get(SCREEN_TRANSITION_ENV_VAR, "")
    for transition in pool:
        if wanted and type(transition).__name__.lstrip("_") == wanted:
            return transition
    return random.choice(pool)
