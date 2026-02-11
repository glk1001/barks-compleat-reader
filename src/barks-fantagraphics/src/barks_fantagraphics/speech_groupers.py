import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import RESTORABLE_PAGE_TYPES
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.ocr_file_paths import get_ocr_prelim_groups_json_filename
from barks_fantagraphics.pages import get_page_num_str, get_sorted_srce_and_dest_pages


class OcrTypes(StrEnum):
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"


OCR_TYPE_DICT = {0: OcrTypes.EASYOCR, 1: OcrTypes.PADDLEOCR}


@dataclass(frozen=True, slots=True)
class SpeechText:
    raw_ai_text: str
    ai_text: str
    type: str
    panel_num: int
    text_box: list[tuple[int | float, int | float]]


SpeechTextGroup = dict[str, SpeechText]


@dataclass(frozen=True, slots=True)
class SpeechPageGroup:
    fanta_vol: int
    title: Titles
    ocr_index: OcrTypes
    fanta_page: str
    comic_page: str
    speech_groups: SpeechTextGroup
    speech_page_json: dict
    ocr_prelim_groups_json_file: Path

    def has_group_changed(self) -> bool:
        return _has_speech_page_group_changed(self)

    def save_group(self, to_file: Path | None = None, backup_file: Path | None = None) -> bool:
        return _save_speech_page_group(self, to_file, backup_file)


@dataclass(frozen=True, slots=True)
class SpeechGroups:
    _comics_database: ComicsDatabase

    # TODO: Have a way to get with/with json and ocr file.
    def get_speech_page_groups(self, title: Titles) -> list[SpeechPageGroup]:
        title_str = BARKS_TITLES[title]

        volume = self._comics_database.get_fanta_volume_int(title_str)
        comic = self._comics_database.get_comic_book(title_str)
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


def _get_speech_text_list(ocr_prelim_groups_json_file: Path) -> tuple[SpeechTextGroup, dict]:
    try:
        ocr_prelim_group = json.loads(ocr_prelim_groups_json_file.read_text())
    except Exception as e:
        msg = f'Error reading ocr_prelim_groups: "{ocr_prelim_groups_json_file}". Exception: {e}'
        raise ValueError(msg) from e

    speech_groups: SpeechTextGroup = SpeechTextGroup()
    for group_id, group in ocr_prelim_group["groups"].items():
        raw_ai_text = group["ai_text"]
        ai_text = raw_ai_text.replace("-\n", "-").replace("\u00ad\n", "").replace("\u200b\n", "")

        if _is_page_number(group):
            continue

        speech_groups[group_id] = SpeechText(
            raw_ai_text=raw_ai_text,
            ai_text=ai_text,
            type=group["type"],
            panel_num=group["panel_num"],
            text_box=group["text_box"],
        )

    return speech_groups, ocr_prelim_group


def _is_page_number(group: dict) -> bool:
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
        if to_file is None:
            to_file = speech_page_group.ocr_prelim_groups_json_file
        if backup_file:
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            to_file.rename(backup_file)
        with to_file.open("w") as f:
            json.dump(speech_page_json, f, indent=4)

    return need_to_save
