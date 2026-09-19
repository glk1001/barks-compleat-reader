from __future__ import annotations

import pytest
from barks_fantagraphics.speech_speakers import (
    CHARACTER_SPEAKER_OPTIONS,
    NON_CHARACTER_SPEAKERS,
    ROSTER,
    SPEAKER_OPTIONS,
    SpeakerCall,
    is_character_speaker,
    is_other_speaker,
    speaker_call_from_group,
    speaker_display_name,
)


class TestVocabulary:
    def test_roster_is_the_twelve_the_vision_pass_uses(self) -> None:
        assert len(SPEAKER_OPTIONS) == 12  # noqa: PLR2004
        assert frozenset(SPEAKER_OPTIONS) == ROSTER
        assert NON_CHARACTER_SPEAKERS <= ROSTER

    def test_character_options_exclude_only_the_sentinels(self) -> None:
        assert set(CHARACTER_SPEAKER_OPTIONS) == ROSTER - NON_CHARACTER_SPEAKERS
        # Order follows the roster, so a chip row reads the way the pass lists them.
        assert CHARACTER_SPEAKER_OPTIONS[0] == "Donald"
        assert "nephews" in CHARACTER_SPEAKER_OPTIONS


class TestPredicates:
    @pytest.mark.parametrize(
        ("speaker", "expected"),
        [
            ("Donald", False),
            ("other:Witch Hazel", True),
            ("other:", True),
            ("nephews", False),
        ],
    )
    def test_is_other_speaker(self, speaker: str, expected: bool) -> None:
        assert is_other_speaker(speaker) is expected

    @pytest.mark.parametrize(
        ("speaker", "expected"),
        [
            ("Donald", True),
            ("nephews", True),
            ("other:the crowd", True),
            ("Flintheart Glomgold", True),
            ("narrator", False),
            ("none", False),
            ("unknown", False),
        ],
    )
    def test_is_character_speaker(self, speaker: str, expected: bool) -> None:
        assert is_character_speaker(speaker) is expected


class TestDisplayName:
    @pytest.mark.parametrize(
        ("speaker", "expected"),
        [
            ("Donald", "Donald"),
            ("Scrooge", "Scrooge"),
            ("nephews", "Nephews"),
            ("narrator", "Caption"),
            ("unknown", "Unknown"),
            ("none", None),
            ("other:Witch Hazel", "Witch Hazel"),
            ("other:the crowd", "The Crowd"),
            ("other:the juke box", "The Juke Box"),
            ("other:  padded  ", "Padded"),
            ("other:", None),
            ("Flintheart Glomgold", "Flintheart Glomgold"),
            ("other:Donald and the nephews", "Donald and the Nephews"),
            ("other:the quizmaster's assistant", "The Quizmaster's Assistant"),
            ("other:a Beagle Boy", "A Beagle Boy"),
            ("Chisel McSue", "Chisel McSue"),
            ("Goldie O'Gilt", "Goldie O'Gilt"),
            ("other:the villager with the spear", "The Villager with the Spear"),
        ],
    )
    def test_display_name(self, speaker: str, expected: str | None) -> None:
        assert speaker_display_name(speaker) == expected


class TestSpeakerCallFromGroup:
    def test_absent_key_is_none(self) -> None:
        assert speaker_call_from_group({"ai_text": "HI", "panel_num": 1}) is None

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_speaker_is_none(self, value: str | None) -> None:
        assert speaker_call_from_group({"speaker": value}) is None

    def test_full_call(self) -> None:
        call = speaker_call_from_group(
            {
                "speaker": "Huey",
                "speaker_confidence": "high",
                "cap_colour": "red",
                "identified_by": ["cap-colour", "balloon-tail"],
                "speaker_was": "nephews",  # review bookkeeping, not carried
            }
        )

        assert call == SpeakerCall(
            speaker="Huey",
            confidence="high",
            cap_colour="red",
            identified_by=("balloon-tail", "cap-colour"),
        )

    def test_null_evidence_is_tolerated(self) -> None:
        """The pass writes explicit nulls; they read the same as absent evidence."""
        call = speaker_call_from_group(
            {
                "speaker": "none",
                "speaker_confidence": None,
                "cap_colour": None,
                "identified_by": None,
            }
        )

        assert call is not None
        assert call.speaker == "none"
        assert call.confidence is None
        assert call.cap_colour is None
        assert call.identified_by == ()

    def test_speaker_alone(self) -> None:
        call = speaker_call_from_group({"speaker": "other:the mayor"})

        assert call == SpeakerCall(speaker="other:the mayor")

    def test_identified_by_is_sorted(self) -> None:
        """The two engines list the same cues in different orders; order is noise."""
        easy = speaker_call_from_group(
            {"speaker": "Donald", "identified_by": ["dialogue", "balloon-tail"]}
        )
        paddle = speaker_call_from_group(
            {"speaker": "Donald", "identified_by": ["balloon-tail", "dialogue"]}
        )

        assert easy == paddle


class TestSpeakerCallProperties:
    def test_character_call(self) -> None:
        call = SpeakerCall(speaker="other:Witch Hazel")

        assert call.is_other
        assert call.is_character
        assert call.display_name == "Witch Hazel"

    def test_sentinel_call(self) -> None:
        call = SpeakerCall(speaker="none")

        assert not call.is_other
        assert not call.is_character
        assert call.display_name is None

    def test_is_frozen(self) -> None:
        call = SpeakerCall(speaker="Donald")
        with pytest.raises(AttributeError):
            call.speaker = "Daisy"  # ty: ignore[invalid-assignment]
