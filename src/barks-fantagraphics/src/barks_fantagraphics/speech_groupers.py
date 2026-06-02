import json
from dataclasses import dataclass
from enum import StrEnum
from itertools import groupby
from pathlib import Path
from typing import Any

from .barks_titles import Titles
from .comic_book import ComicBook
from .comics_consts import RESTORABLE_PAGE_TYPES
from .comics_database import ComicsDatabase
from .ocr_file_paths import get_ocr_prelim_groups_json_filename
from .pages import get_page_num_str, get_sorted_srce_and_dest_pages


class OcrTypes(StrEnum):
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"


OCR_TYPE_DICT = {0: OcrTypes.EASYOCR, 1: OcrTypes.PADDLEOCR}


@dataclass(frozen=True, slots=True)
class SpeechText:
    group_id: str
    panel_num: int
    raw_ai_text: str
    ai_text: str
    type: str
    text_box: list[tuple[int | float, int | float]]


# Vertical bucket size (px) for spatial sorting — bubbles whose min_y values
# fall in the same bucket are treated as the same row and sorted left-to-right.
_Y_BUCKET_PX = 100


def _group_sort_key(group: dict) -> tuple[int, float, float]:
    """Sort key for OCR groups: (panel_num, bucketed_y, min_x).  panel_num -1 sorts last."""
    panel_num = int(group.get("panel_num", -1))
    text_box = group.get("text_box", [])
    if not text_box:
        msg = f"OCR group has empty text_box: {group}"
        raise ValueError(msg)
    min_y = min(p[1] for p in text_box)
    min_x = min(p[0] for p in text_box)
    sort_panel = panel_num if panel_num >= 0 else 999
    bucket_y = round(min_y / _Y_BUCKET_PX) * _Y_BUCKET_PX
    return sort_panel, bucket_y, min_x


@dataclass(frozen=True, slots=True)
class SpeechPageGroup:
    fanta_vol: int
    title: Titles
    ocr_index: OcrTypes
    fanta_page: str
    comic_page: str
    speech_groups: dict[str, SpeechText]
    speech_page_json: dict
    ocr_prelim_groups_json_file: Path

    def get_panel_groups(self) -> dict[int, list[SpeechText]]:
        # Sort by panel_num is required for groupby
        items = sorted(
            (s for s in self.speech_groups.values() if s.panel_num != -1),
            key=lambda s: s.panel_num,
        )
        return {k: list(g) for k, g in groupby(items, key=lambda s: s.panel_num)}

    def has_group_changed(self) -> bool:
        return _has_speech_page_group_changed(self)

    def save_group(self, to_file: Path | None = None, backup_file: Path | None = None) -> bool:
        return _save_speech_page_group(self, to_file, backup_file)

    def save_json(self, to_file: Path | None = None, backup_file: Path | None = None) -> None:
        _save_speech_page_group_json(self, to_file, backup_file)

    def renumber_groups(self) -> bool:
        """Sort groups by panel_num then spatial position, and renumber sequentially.

        Groups are sorted by (panel_num, min_y, min_x) so that both OCR engines
        produce the same ordering for the same page.  Groups with panel_num == -1
        sort last.

        Returns True if ordering or numbering changed.
        """
        groups = self.speech_page_json.get("groups", {})
        old_items = list(groups.items())
        sorted_items = sorted(old_items, key=lambda kv: _group_sort_key(kv[1]))
        renumbered = {str(i): value for i, (_, value) in enumerate(sorted_items)}

        expected_keys = [str(i) for i in range(len(groups))]
        old_keys = list(groups.keys())
        old_values = [v for _, v in old_items]
        new_values = [v for _, v in sorted_items]
        if old_keys == expected_keys and old_values == new_values:
            return False

        self.speech_page_json["groups"] = renumbered
        return True


@dataclass(frozen=True, slots=True)
class SpeechGroups:
    _comics_database: ComicsDatabase

    # TODO: Have a way to get with/with json and ocr file.
    def get_speech_page_groups(self, title: Titles) -> list[SpeechPageGroup]:
        volume = self._comics_database.get_fanta_volume_int_for(title)
        comic = self._comics_database.get_comic_book_for(title)
        srce_dest_map = self._get_srce_page_to_dest_page_map(comic)

        speech_page_groups: list[SpeechPageGroup] = []
        for srce_page, dest_page in srce_dest_map.items():
            for ocr_index in OcrTypes:
                speech_page_group = get_speech_page_group(
                    self._comics_database, volume, title, ocr_index, srce_page, dest_page
                )
                speech_page_groups.append(speech_page_group)

        return speech_page_groups

    @staticmethod
    def _get_srce_page_to_dest_page_map(comic: ComicBook) -> dict[str, str]:
        srce_dest_map = {}

        srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic, get_full_paths=True)
        for srce, dest in zip(
            srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages, strict=True
        ):
            if srce.page_type not in RESTORABLE_PAGE_TYPES:
                continue
            srce_dest_map[Path(srce.page_filename).stem] = get_page_num_str(dest)

        return srce_dest_map


def get_speech_page_group(
    comics_database: ComicsDatabase,
    volume: int,
    title: Titles,
    ocr_index: OcrTypes,
    srce_page: str,
    dest_page: str,
) -> SpeechPageGroup:
    ocr_prelim_dir = comics_database.get_fantagraphics_restored_ocr_prelim_volume_dir(volume)
    ocr_prelim_groups_json_file = ocr_prelim_dir / get_ocr_prelim_groups_json_filename(
        srce_page, ocr_index
    )
    speech_groups, speech_groups_json = _get_speech_text_list(ocr_prelim_groups_json_file)

    return SpeechPageGroup(
        fanta_vol=volume,
        title=title,
        ocr_index=ocr_index,
        fanta_page=srce_page,
        comic_page=dest_page,
        speech_groups=speech_groups,
        speech_page_json=speech_groups_json,
        ocr_prelim_groups_json_file=ocr_prelim_groups_json_file,
    )


def _get_speech_text_list(
    ocr_prelim_groups_json_file: Path,
) -> tuple[dict[str, SpeechText], dict[str, Any]]:
    try:
        ocr_prelim_group = json.loads(ocr_prelim_groups_json_file.read_text())
    except Exception as e:
        msg = f'Error reading ocr_prelim_groups: "{ocr_prelim_groups_json_file}". Exception: {e}'
        raise ValueError(msg) from e

    speech_groups = {}
    for group_id, group in ocr_prelim_group["groups"].items():
        raw_ai_text = group["ai_text"]
        ai_text = raw_ai_text.replace("-\n", "-").replace("\u00ad\n", "").replace("\u200b\n", "")

        if _is_page_number(group):
            continue

        speech_groups[group_id] = SpeechText(
            group_id=group_id,
            panel_num=group["panel_num"],
            raw_ai_text=raw_ai_text,
            ai_text=ai_text,
            type=group["type"],
            text_box=group["text_box"],
        )

    return speech_groups, ocr_prelim_group


def _is_page_number(group: dict[str, Any]) -> bool:
    return (
        int(group["panel_num"]) == -1 and group["notes"] and "page number" in group["notes"].lower()
    )


def _has_speech_page_group_changed(speech_page_group: SpeechPageGroup) -> bool:
    speech_page_json = speech_page_group.speech_page_json

    changed = False
    for group_id, speech_text in speech_page_group.speech_groups.items():
        if speech_text.raw_ai_text != speech_page_json["groups"][group_id]["ai_text"]:
            changed = True
            break

    return changed


def _save_speech_page_group(
    speech_page_group: SpeechPageGroup,
    to_file: Path | None,
    backup_file: Path | None,
) -> bool:
    speech_page_json = speech_page_group.speech_page_json

    need_to_save = False
    for group_id, speech_text in speech_page_group.speech_groups.items():
        if speech_text.raw_ai_text != speech_page_json["groups"][group_id]["ai_text"]:
            need_to_save = True
            speech_page_json["groups"][group_id]["ai_text"] = speech_text.raw_ai_text

    if need_to_save:
        _save_speech_page_group_json(speech_page_group, to_file, backup_file)

    return need_to_save


def _save_speech_page_group_json(
    speech_page_group: SpeechPageGroup,
    to_file: Path | None,
    backup_file: Path | None,
) -> None:
    speech_page_json = speech_page_group.speech_page_json

    if to_file is None:
        to_file = speech_page_group.ocr_prelim_groups_json_file
    assert to_file is not None
    if backup_file:
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        to_file.rename(backup_file)
    with to_file.open("w") as f:
        json.dump(speech_page_json, f, indent=4)
