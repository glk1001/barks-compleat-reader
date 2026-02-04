import json
from pathlib import Path
from typing import TypedDict

from loguru import logger

from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    BARKS_TITLES,
    Titles,
    is_non_comic_title,
)
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import RESTORABLE_PAGE_TYPES
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.ocr_json_files import JsonFiles
from barks_fantagraphics.pages import get_page_num_str, get_sorted_srce_and_dest_pages


class SpeechText(TypedDict):
    raw_ai_text: str
    ai_text: str
    fanta_vol: int
    fanta_page: str
    comic_page: str


class SpeechGroup(TypedDict):
    title: Titles
    ocr_index: int
    groupid: str
    group: SpeechText


class SpeechGroups:
    def __init__(self, comics_database: ComicsDatabase, fanta_volumes: list[int]) -> None:
        self._comics_database = comics_database
        self._volumes = fanta_volumes
        self._all_groups: dict[Titles, list[SpeechGroup]] = {}

    @property
    def all_groups(self) -> dict[Titles, list[SpeechGroup]]:
        return self._all_groups

    def load_groups(self) -> None:
        titles = self._comics_database.get_configured_titles_in_fantagraphics_volumes(self._volumes)
        for title_str, _ in titles:
            if is_non_comic_title(title_str):
                logger.warning(f'Not a comic title "{title_str}" - skipping.')
                continue
            title = BARKS_TITLE_DICT[title_str]
            self._all_groups[title] = self._get_title_speech_groups(title)

    def _get_title_speech_groups(self, title: Titles) -> list[SpeechGroup]:
        title_str = BARKS_TITLES[title]
        json_files = JsonFiles(self._comics_database, title_str)

        comic = self._comics_database.get_comic_book(title_str)
        srce_dest_map = self._get_srce_page_to_dest_page_map(comic)
        raw_ocr_files = comic.get_srce_restored_raw_ocr_story_files(RESTORABLE_PAGE_TYPES)

        speech_groups: list[SpeechGroup] = []
        for raw_ocr_file in raw_ocr_files:
            json_files.set_ocr_file(raw_ocr_file)
            fanta_page = json_files.page
            dest_page = srce_dest_map[fanta_page]

            for ocr_index in range(2):
                try:
                    # Get the paddle ocr groups.
                    ocr_prelim_group = json.loads(
                        json_files.ocr_prelim_groups_json_file[ocr_index].read_text()
                    )
                except Exception as e:
                    msg = (
                        f"Error reading ocr_prelim_groups:"
                        f' "{json_files.ocr_prelim_groups_json_file[ocr_index]}".'
                    )
                    raise ValueError(msg) from e

                for group_id, group in ocr_prelim_group["groups"].items():
                    raw_ai_text = group["ai_text"]
                    ai_text = (
                        raw_ai_text.replace("-\n", "-")
                        .replace("\u00ad\n", "")
                        .replace("\u200b\n", "")
                    )

                    if self.is_page_number(group):
                        continue

                    speech_groups.append(
                        SpeechGroup(
                            title=title,
                            ocr_index=ocr_index,
                            groupid=group_id,
                            group=SpeechText(
                                raw_ai_text=raw_ai_text,
                                ai_text=ai_text,
                                fanta_vol=comic.fanta_book.volume,
                                fanta_page=fanta_page,
                                comic_page=dest_page,
                            ),
                        )
                    )

        return speech_groups

    @staticmethod
    def _get_srce_page_to_dest_page_map(comic: ComicBook) -> dict[str, str]:
        srce_dest_map = {}

        srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic, get_full_paths=True)
        for srce, dest in zip(
            srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages, strict=True
        ):
            srce_dest_map[Path(srce.page_filename).stem] = get_page_num_str(dest)

        return srce_dest_map

    @staticmethod
    def is_page_number(group: dict) -> bool:
        return int(group["panel_num"]) == -1 and "page number" in group["notes"].lower()
