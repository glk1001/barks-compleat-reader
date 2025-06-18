from random import randrange
from typing import Tuple

from reader_consts_and_types import Color


def prob_rand_less_equal(percent: int) -> bool:
    return randrange(1, 101) < percent


def get_rand_int(min_max: Tuple[int, int]) -> int:
    return randrange(min_max[0], min_max[1] + 1)


def get_formatted_color(color: Color) -> str:
    color_strings = [f"{c:04.2f}" for c in color]
    return f'({", ".join(color_strings)})'
