# ruff: noqa: PLR2004

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles

# noinspection PyProtectedMember
from barks_fantagraphics.speech_groupers import (
    OCR_TYPE_DICT,
    OcrTypes,
    SpeechPageGroup,
    SpeechText,
    _get_speech_text_list,
    _has_speech_page_group_changed,
    _is_page_number,
    _save_speech_page_group,
    _save_speech_page_group_json,
    get_speech_page_group,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_speech_text(
    group_id: str = "1",
    panel_num: int = 1,
    raw_ai_text: str = "Hello world",
    ai_text: str | None = None,
    stype: str = "balloon",
) -> SpeechText:
    return SpeechText(
        group_id=group_id,
        panel_num=panel_num,
        raw_ai_text=raw_ai_text,
        ai_text=ai_text if ai_text is not None else raw_ai_text,
        type=stype,
        text_box=[(0, 0), (100, 100)],
    )


def _make_speech_page_group(
    speech_groups: dict[str, SpeechText] | None = None,
    speech_page_json: dict | None = None,
    json_file: Path = Path("test.json"),
) -> SpeechPageGroup:
    return SpeechPageGroup(
        fanta_vol=1,
        title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
        ocr_index=OcrTypes.EASYOCR,
        fanta_page="001",
        comic_page="i",
        speech_groups=speech_groups if speech_groups is not None else {},
        speech_page_json=speech_page_json if speech_page_json is not None else {"groups": {}},
        ocr_prelim_groups_json_file=json_file,
    )


def _make_json_content(groups: dict | None = None) -> dict:
    return {"groups": groups or {}}


def _make_group_entry(
    ai_text: str = "Hello",
    panel_num: int = 1,
    stype: str = "balloon",
    notes: str = "",
    text_box: list | None = None,
) -> dict:
    return {
        "ai_text": ai_text,
        "panel_num": panel_num,
        "type": stype,
        "notes": notes,
        "text_box": text_box or [[0, 0], [100, 100]],
    }


# ---------------------------------------------------------------------------
# OcrTypes / OCR_TYPE_DICT
# ---------------------------------------------------------------------------


class TestOcrTypes:
    def test_str_values(self) -> None:
        assert OcrTypes.EASYOCR == "easyocr"
        assert OcrTypes.PADDLEOCR == "paddleocr"

    def test_dict_mapping(self) -> None:
        assert OCR_TYPE_DICT[0] == OcrTypes.EASYOCR
        assert OCR_TYPE_DICT[1] == OcrTypes.PADDLEOCR


# ---------------------------------------------------------------------------
# _is_page_number
# ---------------------------------------------------------------------------


class TestIsPageNumber:
    def test_page_number_panel_minus_one_with_note(self) -> None:
        group = _make_group_entry(panel_num=-1, notes="This is a page number")
        assert _is_page_number(group) is True

    def test_page_number_note_case_insensitive(self) -> None:
        group = _make_group_entry(panel_num=-1, notes="PAGE NUMBER at bottom")
        assert _is_page_number(group) is True

    def test_not_page_number_wrong_panel(self) -> None:
        group = _make_group_entry(panel_num=1, notes="page number")
        assert _is_page_number(group) is False

    def test_not_page_number_no_note(self) -> None:
        # Returns empty string (falsy) when notes is empty, not literal False
        group = _make_group_entry(panel_num=-1, notes="")
        assert not _is_page_number(group)

    def test_not_page_number_wrong_note(self) -> None:
        group = _make_group_entry(panel_num=-1, notes="some other note")
        assert _is_page_number(group) is False


# ---------------------------------------------------------------------------
# _get_speech_text_list
# ---------------------------------------------------------------------------


class TestGetSpeechTextList:
    def test_parses_basic_group(self, tmp_path: pytest.TempPathFactory) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="Hello world")}))
        )

        speech_groups, _raw_json = _get_speech_text_list(f)

        assert "1" in speech_groups
        st = speech_groups["1"]
        assert st.group_id == "1"
        assert st.raw_ai_text == "Hello world"
        assert st.ai_text == "Hello world"
        assert st.panel_num == 1

    def test_skips_page_numbers(self, tmp_path: pytest.TempPathFactory) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(
                _make_json_content(
                    {
                        "1": _make_group_entry(ai_text="Real text"),
                        "2": _make_group_entry(panel_num=-1, notes="page number here", ai_text="5"),
                    }
                )
            )
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert "1" in speech_groups
        assert "2" not in speech_groups

    def test_ai_text_hyphen_newline_replaced(self, tmp_path: pytest.TempPathFactory) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="hyph-\nnated")}))
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "hyph-nated"
        assert speech_groups["1"].raw_ai_text == "hyph-\nnated"

    def test_soft_hyphen_newline_removed(self, tmp_path: pytest.TempPathFactory) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="soft\u00ad\nhyph")}))
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "softhyph"

    def test_raises_value_error_on_missing_file(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "no-such-file.json"  # type: ignore[operator]
        with pytest.raises(ValueError, match="Error reading ocr_prelim_groups"):
            _get_speech_text_list(missing)

    def test_returns_raw_json(self, tmp_path: pytest.TempPathFactory) -> None:
        content = _make_json_content({"1": _make_group_entry()})
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(json.dumps(content))

        _, raw_json = _get_speech_text_list(f)

        assert raw_json == content

    def test_empty_groups(self, tmp_path: pytest.TempPathFactory) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(json.dumps(_make_json_content()))

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups == {}


# ---------------------------------------------------------------------------
# SpeechPageGroup.get_panel_groups
# ---------------------------------------------------------------------------


class TestGetPanelGroups:
    def test_groups_by_panel_num(self) -> None:
        groups = {
            "1": _make_speech_text("1", panel_num=1, raw_ai_text="A"),
            "2": _make_speech_text("2", panel_num=2, raw_ai_text="B"),
            "3": _make_speech_text("3", panel_num=1, raw_ai_text="C"),
        }
        spg = _make_speech_page_group(speech_groups=groups)

        result = spg.get_panel_groups()

        assert set(result.keys()) == {1, 2}
        assert len(result[1]) == 2
        assert len(result[2]) == 1

    def test_excludes_panel_minus_one(self) -> None:
        groups = {
            "1": _make_speech_text("1", panel_num=-1, raw_ai_text="page num"),
            "2": _make_speech_text("2", panel_num=1, raw_ai_text="real"),
        }
        spg = _make_speech_page_group(speech_groups=groups)

        result = spg.get_panel_groups()

        assert -1 not in result
        assert 1 in result

    def test_empty_groups(self) -> None:
        spg = _make_speech_page_group(speech_groups={})
        assert spg.get_panel_groups() == {}

    def test_sorted_by_panel_num(self) -> None:
        groups = {
            "1": _make_speech_text("1", panel_num=3),
            "2": _make_speech_text("2", panel_num=1),
            "3": _make_speech_text("3", panel_num=2),
        }
        spg = _make_speech_page_group(speech_groups=groups)

        result = spg.get_panel_groups()

        assert list(result.keys()) == [1, 2, 3]


# ---------------------------------------------------------------------------
# _has_speech_page_group_changed
# ---------------------------------------------------------------------------


class TestHasSpeechPageGroupChanged:
    def test_unchanged_returns_false(self) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="Same text")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Same text")})
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data)

        assert _has_speech_page_group_changed(spg) is False

    def test_changed_returns_true(self) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="New text")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Old text")})
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data)

        assert _has_speech_page_group_changed(spg) is True

    def test_empty_groups_unchanged(self) -> None:
        spg = _make_speech_page_group(speech_groups={}, speech_page_json={"groups": {}})
        assert _has_speech_page_group_changed(spg) is False


# ---------------------------------------------------------------------------
# _save_speech_page_group
# ---------------------------------------------------------------------------


class TestSaveSpeechPageGroup:
    def test_no_changes_returns_false(self, tmp_path: pytest.TempPathFactory) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="Same")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Same")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        result = _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert result is False
        assert not f.exists()

    def test_with_changes_returns_true_and_writes(self, tmp_path: pytest.TempPathFactory) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="New")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Old")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        result = _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert result is True
        assert f.exists()
        saved = json.loads(f.read_text())
        assert saved["groups"]["1"]["ai_text"] == "New"

    def test_updates_json_dict_in_place(self, tmp_path: pytest.TempPathFactory) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="Updated")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Original")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert json_data["groups"]["1"]["ai_text"] == "Updated"


# ---------------------------------------------------------------------------
# _save_speech_page_group_json
# ---------------------------------------------------------------------------


class TestSaveSpeechPageGroupJson:
    def test_writes_to_explicit_file(self, tmp_path: pytest.TempPathFactory) -> None:
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Hello")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=f)

        _save_speech_page_group_json(spg, to_file=f, backup_file=None)

        saved = json.loads(f.read_text())
        assert saved == json_data

    def test_writes_to_default_file_when_none(self, tmp_path: pytest.TempPathFactory) -> None:
        json_data = _make_json_content({"1": _make_group_entry()})
        f = tmp_path / "default.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=f)

        _save_speech_page_group_json(spg, to_file=None, backup_file=None)

        assert f.exists()
        saved = json.loads(f.read_text())
        assert saved == json_data

    def test_backup_file_gets_original_renamed(self, tmp_path: pytest.TempPathFactory) -> None:
        json_data = _make_json_content()
        original = tmp_path / "original.json"  # type: ignore[operator]
        original.write_text(json.dumps({"old": True}))
        backup = tmp_path / "backup" / "original.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=original)

        _save_speech_page_group_json(spg, to_file=original, backup_file=backup)

        assert backup.exists()
        assert json.loads(backup.read_text()) == {"old": True}
        saved = json.loads(original.read_text())
        assert saved == json_data


# ---------------------------------------------------------------------------
# get_speech_page_group
# ---------------------------------------------------------------------------


class TestGetSpeechPageGroup:
    def test_returns_correct_speech_page_group(self, tmp_path: pytest.TempPathFactory) -> None:
        db = MagicMock()
        db.get_fantagraphics_restored_ocr_prelim_volume_dir.return_value = tmp_path

        json_content = _make_json_content({"1": _make_group_entry(ai_text="Quack!")})
        json_file = tmp_path / "001-easyocr-gemini-prelim-groups.json"  # type: ignore[operator]
        json_file.write_text(json.dumps(json_content))

        result = get_speech_page_group(
            db,
            volume=3,
            title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            ocr_index=OcrTypes.EASYOCR,
            srce_page="001",
            dest_page="1",
        )

        db.get_fantagraphics_restored_ocr_prelim_volume_dir.assert_called_once_with(3)
        assert result.fanta_vol == 3
        assert result.title == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        assert result.ocr_index == OcrTypes.EASYOCR
        assert result.fanta_page == "001"
        assert result.comic_page == "1"
        assert "1" in result.speech_groups
        assert result.speech_groups["1"].ai_text == "Quack!"
