"""The popup gallery's sample content: each sample makes the text its popup shows."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_reader.core.data_pack import UpdateStatus
from barks_reader.core.popup_gallery_samples import (
    ERROR_SAMPLES,
    sample_title_speech,
    sample_update_check,
)
from barks_reader.core.speech_hits import comic_pages
from barks_reader.core.user_error_messages import build_error_presentation
from barks_reader.core.user_error_types import ErrorTypes


@pytest.mark.parametrize("error_type", list(ErrorTypes))
def test_each_user_errors_sample_makes_its_message(error_type: ErrorTypes) -> None:
    presentation = build_error_presentation(error_type, ERROR_SAMPLES[error_type], MagicMock())
    assert presentation.text


def test_the_offer_and_the_no_update_say_their_piece() -> None:
    offer = sample_update_check(UpdateStatus.UPDATE_AVAILABLE)
    assert "Install it now?" in offer.offer_message()
    none_new = sample_update_check(UpdateStatus.PACKS_MISSING)
    assert "barks-reader-data-2.barkspack" in none_new.no_update_message()


def test_the_sample_speech_is_on_three_pages_one_with_two_bubbles() -> None:
    speech = sample_title_speech()

    assert comic_pages(speech) == ("3", "7", "21")
    assert [len(page.speech_info_list) for page in speech.fanta_pages.values()] == [1, 2, 1]
