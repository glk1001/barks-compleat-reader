# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import patch

import pytest
from barks_reader.core import reader_colors as reader_colors_module
from barks_reader.core.reader_colors import RandomColorTint


@pytest.fixture
def random_color_tint() -> RandomColorTint:
    return RandomColorTint(full_color_probability=50, tinted_probability=50)


class TestRandomColorTint:
    def test_init(self, random_color_tint: RandomColorTint) -> None:
        """Test initialization."""
        assert random_color_tint._full_color_probability == 50  # noqa: PLR2004
        assert random_color_tint._tinted_probability == 50  # noqa: PLR2004

    def test_setters(self, random_color_tint: RandomColorTint) -> None:
        """Test all setters."""
        random_color_tint.set_affected_indexes([0, 1])
        assert random_color_tint._affected_indexes == [0, 1]

        random_color_tint.set_red_range(10, 20)
        assert random_color_tint._red_range == (10, 20)

        random_color_tint.set_green_range(30, 40)
        assert random_color_tint._green_range == (30, 40)

        random_color_tint.set_blue_range(50, 60)
        assert random_color_tint._blue_range == (50, 60)

        random_color_tint.set_alpha_range(70, 80)
        assert random_color_tint._alpha_range == (70, 80)

        random_color_tint.set_full_color_alpha_range(90, 100)
        assert random_color_tint._full_color_alpha_range == (90, 100)

        random_color_tint.set_full_color_probability(10)
        assert random_color_tint._full_color_probability == 10  # noqa: PLR2004

    def test_get_random_color_full_color(self, random_color_tint: RandomColorTint) -> None:
        """Test getting a full color (white with alpha)."""
        with (
            patch.object(reader_colors_module, "prob_rand_less_equal", return_value=True),
            patch.object(reader_colors_module, "get_rand_int", return_value=128),
        ):
            color = random_color_tint.get_random_color()

            # Alpha 128/255 ~= 0.50196
            assert color == (1.0, 1.0, 1.0, 128 / 255.0)

    def test_get_random_color_tinted(self, random_color_tint: RandomColorTint) -> None:
        """Test getting a tinted color."""
        # Flow:
        # 1. prob_rand_less_equal -> False (not full color)
        # 2. prob_rand_less_equal -> True (tinted)
        # 3. _get_tinted_color called
        #    a. get_rand_int(alpha_range) -> alpha val
        #    b. _get_random_tinted_color called
        #       i. randrange(1, 3) -> num_indexes (say 1)
        #       ii. sample([0,1,2], k=1) -> [0] (Red)
        #       iii. get_rand_int(red_range) -> red val

        with (
            patch.object(reader_colors_module, "prob_rand_less_equal", side_effect=[False, True]),
            patch.object(reader_colors_module, "get_rand_int") as mock_get_int,
            patch.object(reader_colors_module, "randrange", return_value=1),
            patch.object(reader_colors_module, "sample", return_value=[0]),
        ):
            mock_get_int.side_effect = [
                200,  # Alpha
                100,  # Red value
            ]

            color = random_color_tint.get_random_color()

            # Expected:
            alpha = 200 / 255
            red = 100 / 255
            green = 0.1  # (default non-random)
            blue = 0.1  # (default non-random)

            assert color[0] == red
            assert color[1] == green
            assert color[2] == blue
            assert color[3] == alpha

    def test_get_random_color_rgb(self, random_color_tint: RandomColorTint) -> None:
        """Test getting a fully randomized RGB color."""
        # Flow:
        # 1. prob_rand_less_equal -> False
        # 2. prob_rand_less_equal -> False
        # 3. _get_rgb_color called
        #    a. get_rand_int(full_color_alpha_range) -> alpha
        #    b. Loop affected indexes (0, 1, 2 default)
        #       get_rand_int -> R
        #       get_rand_int -> G
        #       get_rand_int -> B

        with (
            patch.object(reader_colors_module, "prob_rand_less_equal", side_effect=[False, False]),
            patch.object(reader_colors_module, "get_rand_int") as mock_get_int,
        ):
            mock_get_int.side_effect = [
                255,  # Alpha
                50,  # R
                100,  # G
                150,  # B
            ]

            color = random_color_tint.get_random_color()

            assert color == (50 / 255.0, 100 / 255.0, 150 / 255.0, 1.0)

    def test_get_random_color_rgb_custom_indexes(self, random_color_tint: RandomColorTint) -> None:
        """Test RGB color with specific affected indexes."""
        random_color_tint.set_affected_indexes([0, 2])  # R and B only

        with (
            patch.object(reader_colors_module, "prob_rand_less_equal", side_effect=[False, False]),
            patch.object(reader_colors_module, "get_rand_int") as mock_get_int,
        ):
            mock_get_int.side_effect = [
                255,  # Alpha
                10,  # R
                20,  # B
            ]

            color = random_color_tint.get_random_color()

            # R=10/255, G=0.1 (unchanged), B=20/255, A=1.0
            assert color[0] == 10 / 255.0
            assert color[1] == 0.1  # noqa: PLR2004
            assert color[2] == 20 / 255.0
            assert color[3] == 1.0
