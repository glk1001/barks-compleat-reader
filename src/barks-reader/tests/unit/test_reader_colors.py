# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.reader_colors import RandomColorTint


class TestRandomColorTint:
    @pytest.fixture
    def random_color_tint(self) -> RandomColorTint:
        return RandomColorTint(full_color_probability=30, tinted_probability=50)

    def test_init(self, random_color_tint: RandomColorTint) -> None:
        # noinspection PyProtectedMember
        assert random_color_tint._full_color_probability == 30  # noqa: PLR2004
        # noinspection PyProtectedMember
        assert random_color_tint._tinted_probability == 50  # noqa: PLR2004
        # noinspection PyProtectedMember
        assert random_color_tint._affected_indexes == [0, 1, 2]

    @patch("barks_reader.reader_colors.prob_rand_less_equal")
    @patch("barks_reader.reader_colors.get_rand_int")
    def test_get_random_color_full_color(
        self,
        mock_get_rand_int: MagicMock,
        mock_prob: MagicMock,
        random_color_tint: RandomColorTint,
    ) -> None:
        # Case 1: Full color
        mock_prob.return_value = True
        mock_get_rand_int.return_value = 255  # alpha

        color = random_color_tint.get_random_color()

        mock_prob.assert_called_once_with(30)
        # noinspection PyProtectedMember
        mock_get_rand_int.assert_called_once_with(random_color_tint._full_color_alpha_range)
        assert color == (1.0, 1.0, 1.0, 1.0)

    @patch("barks_reader.reader_colors.prob_rand_less_equal")
    @patch("barks_reader.reader_colors.get_rand_int")
    @patch("barks_reader.reader_colors.randrange")
    @patch("barks_reader.reader_colors.sample")
    def test_get_random_color_tinted(
        self,
        mock_sample: MagicMock,
        mock_randrange: MagicMock,
        mock_get_rand_int: MagicMock,
        mock_prob: MagicMock,
        random_color_tint: RandomColorTint,
    ) -> None:
        # Case 2: Tinted color
        # prob_rand_less_equal called twice: first False (not full color), second True (tinted)
        mock_prob.side_effect = [False, True]

        # get_rand_int calls:
        # 1. alpha in _get_tinted_color (range 200, 255) -> let's say 204 (0.8)
        # 2. inside _get_random_tinted_color loop.

        # randrange calls:
        # 1. num_indexes_to_change in _get_random_tinted_color -> let's say 1

        # sample calls:
        # 1. rand_indexes -> let's say [0] (Red index)

        mock_get_rand_int.side_effect = [204, 128]  # alpha=204, red=128
        mock_randrange.return_value = 1
        mock_sample.return_value = [0]  # Red index

        color = random_color_tint.get_random_color()

        assert mock_prob.call_count == 2  # noqa: PLR2004
        assert color[0] == 128 / 255.0  # Red changed
        assert color[1] == 0.1  # Green default non-random  # noqa: PLR2004
        assert color[2] == 0.1  # Blue default non-random  # noqa: PLR2004
        assert color[3] == 204 / 255.0  # Alpha

    @patch("barks_reader.reader_colors.prob_rand_less_equal")
    @patch("barks_reader.reader_colors.get_rand_int")
    def test_get_random_color_rgb(
        self,
        mock_get_rand_int: MagicMock,
        mock_prob: MagicMock,
        random_color_tint: RandomColorTint,
    ) -> None:
        # Case 3: RGB color
        # prob_rand_less_equal called twice: False, False
        mock_prob.side_effect = [False, False]

        # get_rand_int calls:
        # 1. alpha in _get_rgb_color (full color alpha range) -> 255
        # 2. loop over affected indexes (R, G, B by default) -> 100, 150, 200

        mock_get_rand_int.side_effect = [255, 100, 150, 200]

        color = random_color_tint.get_random_color()

        assert color == (100 / 255.0, 150 / 255.0, 200 / 255.0, 1.0)

    def test_setters(self, random_color_tint: RandomColorTint) -> None:
        random_color_tint.set_affected_indexes([0])
        # noinspection PyProtectedMember
        assert random_color_tint._affected_indexes == [0]

        random_color_tint.set_red_range(0, 10)
        # noinspection PyProtectedMember
        assert random_color_tint._red_range == (0, 10)

        random_color_tint.set_green_range(10, 20)
        # noinspection PyProtectedMember
        assert random_color_tint._green_range == (10, 20)

        random_color_tint.set_blue_range(20, 30)
        # noinspection PyProtectedMember
        assert random_color_tint._blue_range == (20, 30)

        random_color_tint.set_alpha_range(30, 40)
        # noinspection PyProtectedMember
        assert random_color_tint._alpha_range == (30, 40)

        random_color_tint.set_full_color_alpha_range(40, 50)
        # noinspection PyProtectedMember
        assert random_color_tint._full_color_alpha_range == (40, 50)

        random_color_tint.set_full_color_probability(100)
        # noinspection PyProtectedMember
        assert random_color_tint._full_color_probability == 100  # noqa: PLR2004

    def test_get_color_range_invalid(self, random_color_tint: RandomColorTint) -> None:
        # noinspection PyProtectedMember
        with pytest.raises(AssertionError):
            random_color_tint._get_color_range(99)
