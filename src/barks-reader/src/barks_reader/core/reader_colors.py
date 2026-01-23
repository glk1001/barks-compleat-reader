from random import randrange, sample

from barks_reader.core.reader_utils import get_rand_int, prob_rand_less_equal

Color = tuple[float, float, float, float]


class RandomColorTint:
    _R_INDEX = 0
    _G_INDEX = 1
    _B_INDEX = 2
    _A_INDEX = 3

    def __init__(self, full_color_probability: int, tinted_probability: int) -> None:
        self._affected_indexes = [self._R_INDEX, self._G_INDEX, self._B_INDEX]

        self._red_range = (200, 255)
        self._green_range = (200, 255)
        self._blue_range = (200, 255)
        self._alpha_range = (200, 255)
        self._full_color_alpha_range = (250, 255)

        self._non_random_red = 0.1
        self._non_random_green = 0.1
        self._non_random_blue = 0.1

        self._full_color_probability = full_color_probability
        self._tinted_probability = tinted_probability

    def set_affected_indexes(self, indexes: list[int]) -> None:
        self._affected_indexes = indexes

    def set_red_range(self, r_min: int, r_max: int) -> None:
        self._red_range = (r_min, r_max)

    def set_green_range(self, r_min: int, r_max: int) -> None:
        self._green_range = (r_min, r_max)

    def set_blue_range(self, r_min: int, r_max: int) -> None:
        self._blue_range = (r_min, r_max)

    def set_alpha_range(self, r_min: int, r_max: int) -> None:
        self._alpha_range = (r_min, r_max)

    def set_full_color_alpha_range(self, r_min: int, r_max: int) -> None:
        self._full_color_alpha_range = (r_min, r_max)

    def set_full_color_probability(self, value: int) -> None:
        self._full_color_probability = value

    def _get_non_random_color(self, alpha: float) -> Color:
        return self._non_random_red, self._non_random_green, self._non_random_blue, alpha

    def _get_color_range(self, index: int) -> tuple[int, int]:
        if index == self._R_INDEX:
            return self._red_range
        if index == self._G_INDEX:
            return self._green_range
        if index == self._B_INDEX:
            return self._blue_range
        raise AssertionError

    def get_random_color(self) -> Color:
        if prob_rand_less_equal(self._full_color_probability):
            alpha = get_rand_int(self._full_color_alpha_range) / 255.0
            return 1.0, 1.0, 1.0, alpha

        if prob_rand_less_equal(self._tinted_probability):
            return self._get_tinted_color()

        return self._get_rgb_color()

    def _get_tinted_color(self) -> Color:
        alpha = get_rand_int(self._alpha_range) / 255.0
        rand_color = self._get_non_random_color(alpha)

        rand_color = self._get_random_tinted_color(rand_color)

        return tuple(rand_color)

    def _get_random_tinted_color(self, color: Color) -> Color:
        num_indexes_to_change = randrange(1, 3)
        rand_indexes = sample(
            [self._R_INDEX, self._G_INDEX, self._B_INDEX], k=num_indexes_to_change
        )

        rand_color = list(color)
        for index in rand_indexes:
            rand_color[index] = get_rand_int(self._get_color_range(index)) / 255.0

        # Pycharm inspection bug?
        # noinspection PyTypeChecker
        return tuple(rand_color)  # ty: ignore[invalid-return-type]

    def _get_rgb_color(self) -> Color:
        alpha = get_rand_int(self._full_color_alpha_range) / 255.0

        rand_color = list(self._get_non_random_color(alpha))
        for index in self._affected_indexes:
            rand_color[index] = get_rand_int(self._get_color_range(index)) / 255.0

        # Pycharm inspection bug?
        # noinspection PyTypeChecker
        return tuple(rand_color)  # ty: ignore[invalid-return-type]
