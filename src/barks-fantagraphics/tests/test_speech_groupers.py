# ruff: noqa: PLR2004

from __future__ import annotations

import errno
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics import speech_groupers as speech_groupers_module
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.speech_groupers import (
    OCR_TYPE_DICT,
    OcrTypes,
    SpeechGroups,
    SpeechPageGroup,
    SpeechText,
    _get_speech_text_list,
    _has_speech_page_group_changed,
    _is_page_number,
    _save_speech_page_group,
    _save_speech_page_group_json,
    get_speech_page_group,
)
from barks_fantagraphics.speech_markup import strip_markup

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
    resolved = ai_text if ai_text is not None else raw_ai_text
    return SpeechText(
        group_id=group_id,
        panel_num=panel_num,
        raw_ai_text=raw_ai_text,
        ai_text=strip_markup(resolved),
        ai_text_markup=resolved,
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
    def test_parses_basic_group(self, tmp_path: Path) -> None:
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

    def test_skips_page_numbers(self, tmp_path: Path) -> None:
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

    def test_ai_text_hyphen_newline_replaced(self, tmp_path: Path) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="hyph-\nnated")}))
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "hyph-nated"
        assert speech_groups["1"].raw_ai_text == "hyph-\nnated"

    def test_ai_text_strips_emphasis_markup(self, tmp_path: Path) -> None:
        """The default view is plain, so a consumer that ignores emphasis is correct."""
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="A [b]SUCCESS[/b]!")}))
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "A SUCCESS!"
        assert speech_groups["1"].ai_text_markup == "A [b]SUCCESS[/b]!"
        assert speech_groups["1"].raw_ai_text == "A [b]SUCCESS[/b]!"

    def test_ai_text_unescapes_literal_brackets(self, tmp_path: Path) -> None:
        """Gemini's own bracketed annotations survive the round trip."""
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(
                _make_json_content({"1": _make_group_entry(ai_text="&bl;Chinese Characters&br;")})
            )
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "[Chinese Characters]"

    def test_soft_hyphen_newline_removed(self, tmp_path: Path) -> None:
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(
            json.dumps(_make_json_content({"1": _make_group_entry(ai_text="soft\u00ad\nhyph")}))
        )

        speech_groups, _ = _get_speech_text_list(f)

        assert speech_groups["1"].ai_text == "softhyph"

    def test_raises_value_error_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-file.json"  # type: ignore[operator]
        with pytest.raises(ValueError, match="Error reading ocr_prelim_groups"):
            _get_speech_text_list(missing)

    def test_returns_raw_json(self, tmp_path: Path) -> None:
        content = _make_json_content({"1": _make_group_entry()})
        f = tmp_path / "groups.json"  # type: ignore[operator]
        f.write_text(json.dumps(content))

        _, raw_json = _get_speech_text_list(f)

        assert raw_json == content

    def test_empty_groups(self, tmp_path: Path) -> None:
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
# SpeechPageGroup.renumber_groups
# ---------------------------------------------------------------------------


class TestRenumberGroups:
    def test_already_sorted_and_sequential_returns_false(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(panel_num=1, ai_text="A"),
                "1": _make_group_entry(panel_num=2, ai_text="B"),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is False
        assert list(json_data["groups"].keys()) == ["0", "1"]
        assert json_data["groups"]["0"]["ai_text"] == "A"

    def test_out_of_order_panel_nums_renumbered(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(panel_num=2, ai_text="B"),
                "1": _make_group_entry(panel_num=1, ai_text="A"),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        groups = json_data["groups"]
        assert list(groups.keys()) == ["0", "1"]
        assert groups["0"]["ai_text"] == "A"
        assert groups["1"]["ai_text"] == "B"

    def test_panel_minus_one_sorts_last(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(panel_num=-1, ai_text="pg"),
                "1": _make_group_entry(panel_num=1, ai_text="real"),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        groups = json_data["groups"]
        assert groups["0"]["ai_text"] == "real"
        assert groups["1"]["ai_text"] == "pg"

    def test_sorts_by_y_bucket_within_panel(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(
                    panel_num=1, ai_text="bottom", text_box=[[50, 300], [150, 400]]
                ),
                "1": _make_group_entry(panel_num=1, ai_text="top", text_box=[[50, 0], [150, 100]]),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        groups = json_data["groups"]
        assert groups["0"]["ai_text"] == "top"
        assert groups["1"]["ai_text"] == "bottom"

    def test_sorts_by_x_within_same_y_bucket(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(
                    panel_num=1, ai_text="right", text_box=[[500, 0], [600, 50]]
                ),
                "1": _make_group_entry(panel_num=1, ai_text="left", text_box=[[0, 0], [100, 50]]),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        groups = json_data["groups"]
        assert groups["0"]["ai_text"] == "left"
        assert groups["1"]["ai_text"] == "right"

    def test_small_y_difference_treated_as_same_row(self) -> None:
        # y values 10 and 40 both bucket to 0 — order must be by x, not y
        json_data = _make_json_content(
            {
                "0": _make_group_entry(
                    panel_num=1, ai_text="right-slightly-higher", text_box=[[500, 10], [600, 60]]
                ),
                "1": _make_group_entry(
                    panel_num=1, ai_text="left-slightly-lower", text_box=[[0, 40], [100, 90]]
                ),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        groups = json_data["groups"]
        assert groups["0"]["ai_text"] == "left-slightly-lower"
        assert groups["1"]["ai_text"] == "right-slightly-higher"

    def test_renumbers_non_sequential_keys(self) -> None:
        json_data = _make_json_content(
            {
                "0": _make_group_entry(panel_num=1, ai_text="A"),
                "5": _make_group_entry(panel_num=2, ai_text="B"),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is True
        assert list(json_data["groups"].keys()) == ["0", "1"]
        assert json_data["groups"]["0"]["ai_text"] == "A"
        assert json_data["groups"]["1"]["ai_text"] == "B"

    def test_empty_groups_returns_false(self) -> None:
        json_data = _make_json_content()
        spg = _make_speech_page_group(speech_page_json=json_data)

        assert spg.renumber_groups() is False
        assert json_data["groups"] == {}

    def test_empty_text_box_raises_value_error(self) -> None:
        no_box = _make_group_entry(panel_num=1, ai_text="no-box")
        no_box["text_box"] = []
        json_data = _make_json_content(
            {
                "0": no_box,
                "1": _make_group_entry(panel_num=2, ai_text="has-box"),
            }
        )
        spg = _make_speech_page_group(speech_page_json=json_data)

        with pytest.raises(ValueError, match="empty text_box"):
            spg.renumber_groups()


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
    def test_no_changes_returns_false(self, tmp_path: Path) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="Same")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Same")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        result = _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert result is False
        assert not f.exists()

    def test_with_changes_returns_true_and_writes(self, tmp_path: Path) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="New")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Old")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        result = _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert result is True
        assert f.exists()
        saved = json.loads(f.read_text())
        assert saved["groups"]["1"]["ai_text"] == "New"

    def test_updates_json_dict_in_place(self, tmp_path: Path) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="Updated")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Original")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        _save_speech_page_group(spg, to_file=f, backup_file=None)

        assert json_data["groups"]["1"]["ai_text"] == "Updated"

    def test_emphasis_only_edit_is_still_saved(self, tmp_path: Path) -> None:
        """Saving must stay markup-sensitive, or an emphasis edit is silently lost."""
        groups = {"1": _make_speech_text("1", raw_ai_text="A [b]SUCCESS[/b]!")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="A SUCCESS!")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data, json_file=f)

        assert _save_speech_page_group(spg, to_file=f, backup_file=None) is True
        assert json.loads(f.read_text())["groups"]["1"]["ai_text"] == "A [b]SUCCESS[/b]!"


class TestGroupsWithTextChanges:
    """The correction-rate metric must not count emphasis edits as text changes."""

    def test_emphasis_only_edit_is_not_a_text_change(self) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="A [b]SUCCESS[/b]!")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="A SUCCESS!")})
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data)

        assert spg.has_group_changed() is True
        assert spg.groups_with_text_changes() == []

    def test_real_text_change_is_reported(self) -> None:
        groups = {"1": _make_speech_text("1", raw_ai_text="A [b]FAILURE[/b]!")}
        json_data = _make_json_content({"1": _make_group_entry(ai_text="A SUCCESS!")})
        spg = _make_speech_page_group(speech_groups=groups, speech_page_json=json_data)

        assert spg.groups_with_text_changes() == ["1"]


# ---------------------------------------------------------------------------
# _save_speech_page_group_json
# ---------------------------------------------------------------------------


class TestSaveSpeechPageGroupJson:
    def test_writes_to_explicit_file(self, tmp_path: Path) -> None:
        json_data = _make_json_content({"1": _make_group_entry(ai_text="Hello")})
        f = tmp_path / "out.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=f)

        _save_speech_page_group_json(spg, to_file=f, backup_file=None)

        saved = json.loads(f.read_text())
        assert saved == json_data

    def test_writes_to_default_file_when_none(self, tmp_path: Path) -> None:
        json_data = _make_json_content({"1": _make_group_entry()})
        f = tmp_path / "default.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=f)

        _save_speech_page_group_json(spg, to_file=None, backup_file=None)

        assert f.exists()
        saved = json.loads(f.read_text())
        assert saved == json_data

    def test_backup_file_gets_the_previous_content(self, tmp_path: Path) -> None:
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

    def test_backup_works_across_a_filesystem_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The backup dir may be on another disk, so this must not use rename().

        In practice Prelim-backups is a symlink to a second drive, and a
        rename() there raises OSError(EXDEV) on every save.
        """
        json_data = _make_json_content()
        original = tmp_path / "original.json"  # type: ignore[operator]
        original.write_text(json.dumps({"old": True}))
        backup = tmp_path / "backup" / "original.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=original)

        def _refuse_cross_device(*_args: object, **_kwargs: object) -> None:
            msg = "Invalid cross-device link"
            raise OSError(errno.EXDEV, msg)

        monkeypatch.setattr(Path, "rename", _refuse_cross_device)

        _save_speech_page_group_json(spg, to_file=original, backup_file=backup)

        assert json.loads(backup.read_text()) == {"old": True}
        assert json.loads(original.read_text()) == json_data

    def test_missing_original_still_writes(self, tmp_path: Path) -> None:
        """A first save has nothing to back up and must not fail trying."""
        json_data = _make_json_content()
        original = tmp_path / "brand-new.json"  # type: ignore[operator]
        backup = tmp_path / "backup" / "brand-new.json"  # type: ignore[operator]
        spg = _make_speech_page_group(speech_page_json=json_data, json_file=original)

        _save_speech_page_group_json(spg, to_file=original, backup_file=backup)

        assert not backup.exists()
        assert json.loads(original.read_text()) == json_data


# ---------------------------------------------------------------------------
# get_speech_page_group
# ---------------------------------------------------------------------------


class TestGetSpeechPageGroup:
    def test_returns_correct_speech_page_group(self, tmp_path: Path) -> None:
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


# ---------------------------------------------------------------------------
# SpeechGroups._get_srce_page_to_dest_page_map
# ---------------------------------------------------------------------------


def _make_srce_dest_pages(
    page_stems: list[str], page_types: list[PageType] | None = None
) -> MagicMock:
    types = page_types or [PageType.BODY] * len(page_stems)
    result = MagicMock()
    result.srce_pages = [
        MagicMock(page_filename=f"/some/dir/{stem}.png", page_type=ptype)
        for stem, ptype in zip(page_stems, types, strict=True)
    ]
    result.dest_pages = [MagicMock(page_num=i) for i, _ in enumerate(page_stems)]
    return result


def _make_comic(fixes_files: dict[str, Path]) -> MagicMock:
    """Make a comic whose get_srce_original_fixes_story_file returns the given paths."""
    comic = MagicMock()
    comic.get_srce_original_fixes_story_file.side_effect = lambda page: fixes_files.get(
        page, Path("/no/such/fixes/file.png")
    )
    return comic


class TestGetSrcePageToDestPageMap:
    def test_symlinked_source_page_is_excluded(self, tmp_path: Path) -> None:
        """A one-pager reprinted from another volume is not this title's OCR work."""
        target = tmp_path / "other-volume-page.png"  # type: ignore[operator]
        target.write_text("art")
        symlinked = tmp_path / "500.png"  # type: ignore[operator]
        symlinked.symlink_to(target)
        real = tmp_path / "001.png"  # type: ignore[operator]
        real.write_text("art")

        comic = _make_comic({"001": real, "500": symlinked})
        srce_dest = _make_srce_dest_pages(["001", "500"])

        with patch.object(
            speech_groupers_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = SpeechGroups._get_srce_page_to_dest_page_map(comic)  # noqa: SLF001

        assert list(result) == ["001"]

    def test_non_restorable_page_types_are_excluded(self, tmp_path: Path) -> None:
        real = tmp_path / "001.png"  # type: ignore[operator]
        real.write_text("art")
        comic = _make_comic({"001": real, "002": real})
        srce_dest = _make_srce_dest_pages(["001", "002"], [PageType.BODY, PageType.COVER])

        with patch.object(
            speech_groupers_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = SpeechGroups._get_srce_page_to_dest_page_map(comic)  # noqa: SLF001

        assert list(result) == ["001"]

    def test_missing_fixes_file_is_kept(self) -> None:
        """A page with no fixes file at all is ordinary OCR work."""
        comic = _make_comic({})
        srce_dest = _make_srce_dest_pages(["001"])

        with patch.object(
            speech_groupers_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = SpeechGroups._get_srce_page_to_dest_page_map(comic)  # noqa: SLF001

        assert list(result) == ["001"]


# ---------------------------------------------------------------------------
# SpeechGroups.get_speech_page_groups / get_missing_prelim_pages
# ---------------------------------------------------------------------------


def _make_speech_groups(
    tmp_path: Path, pages: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> SpeechGroups:
    """Make a SpeechGroups over `pages` (srce -> dest), with tmp_path as the prelim dir."""
    db = MagicMock()
    db.get_fanta_volume_int_for.return_value = 1
    db.get_fantagraphics_restored_ocr_prelim_volume_dir.return_value = tmp_path
    db.get_comic_book_for.return_value = MagicMock()

    monkeypatch.setattr(
        SpeechGroups, "_get_srce_page_to_dest_page_map", staticmethod(lambda _comic: pages)
    )
    return SpeechGroups(db)


def _write_prelim(tmp_path: Path, page: str, ocr_type: OcrTypes, text: str = "Quack!") -> Path:
    json_file = tmp_path / f"{page}-{ocr_type}-gemini-prelim-groups.json"  # type: ignore[operator]
    json_file.write_text(json.dumps(_make_json_content({"1": _make_group_entry(ai_text=text)})))
    return json_file


class TestGetSpeechPageGroups:
    def test_loads_both_engines_for_each_page(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speech_groups = _make_speech_groups(tmp_path, {"001": "1"}, monkeypatch)
        for ocr_type in OcrTypes:
            _write_prelim(tmp_path, "001", ocr_type)

        result = speech_groups.get_speech_page_groups(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD)

        assert [g.ocr_index for g in result] == [OcrTypes.EASYOCR, OcrTypes.PADDLEOCR]
        assert all(g.fanta_page == "001" for g in result)

    def test_missing_file_raises_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The default must stay loud: a gap in the OCR data is a defect."""
        speech_groups = _make_speech_groups(tmp_path, {"001": "1"}, monkeypatch)

        with pytest.raises(ValueError, match="Error reading ocr_prelim_groups"):
            speech_groups.get_speech_page_groups(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD)

    def test_missing_file_skipped_when_opted_in(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speech_groups = _make_speech_groups(tmp_path, {"001": "1", "002": "2"}, monkeypatch)
        for ocr_type in OcrTypes:
            _write_prelim(tmp_path, "001", ocr_type)
        _write_prelim(tmp_path, "002", OcrTypes.EASYOCR)

        result = speech_groups.get_speech_page_groups(
            Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, skip_missing=True
        )

        assert [(g.fanta_page, g.ocr_index) for g in result] == [
            ("001", OcrTypes.EASYOCR),
            ("001", OcrTypes.PADDLEOCR),
            ("002", OcrTypes.EASYOCR),
        ]

    def test_malformed_file_still_raises_when_opted_in(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """skip_missing tolerates an absent file, never an unreadable one."""
        speech_groups = _make_speech_groups(tmp_path, {"001": "1"}, monkeypatch)
        for ocr_type in OcrTypes:
            bad = tmp_path / f"001-{ocr_type}-gemini-prelim-groups.json"  # type: ignore[operator]
            bad.write_text("{not json")

        with pytest.raises(ValueError, match="Error reading ocr_prelim_groups"):
            speech_groups.get_speech_page_groups(
                Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, skip_missing=True
            )


class TestGetMissingPrelimPages:
    def test_reports_only_the_absent_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speech_groups = _make_speech_groups(tmp_path, {"001": "1", "002": "2"}, monkeypatch)
        for ocr_type in OcrTypes:
            _write_prelim(tmp_path, "001", ocr_type)
        _write_prelim(tmp_path, "002", OcrTypes.EASYOCR)

        result = speech_groups.get_missing_prelim_pages(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD)

        assert len(result) == 1
        assert result[0].fanta_page == "002"
        assert result[0].ocr_index == OcrTypes.PADDLEOCR
        assert result[0].json_file.name == "002-paddleocr-gemini-prelim-groups.json"

    def test_empty_when_nothing_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        speech_groups = _make_speech_groups(tmp_path, {"001": "1"}, monkeypatch)
        for ocr_type in OcrTypes:
            _write_prelim(tmp_path, "001", ocr_type)

        assert speech_groups.get_missing_prelim_pages(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD) == []
