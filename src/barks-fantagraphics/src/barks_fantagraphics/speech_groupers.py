import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import groupby
from pathlib import Path
from typing import Any

from loguru import logger

from .barks_titles import Titles
from .comic_book import ComicBook
from .comics_consts import RESTORABLE_PAGE_TYPES
from .comics_database import ComicsDatabase
from .ocr_file_paths import get_ocr_prelim_groups_json_filename
from .pages import get_page_num_str, get_srce_and_dest_pages_in_order
from .speech_markup import same_text_ignoring_markup, strip_markup


class OcrTypes(StrEnum):
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"


OCR_TYPE_DICT = {0: OcrTypes.EASYOCR, 1: OcrTypes.PADDLEOCR}


@dataclass(frozen=True, slots=True)
class SpeechText:
    """One OCR speech group's text and geometry.

    Three views of the text, and picking the wrong one is the trap this class
    exists to close:

    - ``raw_ai_text`` -- byte-for-byte what is on disk, emphasis markup and soft
      hyphens included.  This is the editable copy; saving writes it back.
    - ``ai_text`` -- **plain text**, with emphasis markup stripped and hyphenated
      line breaks joined.  The default, and what every consumer wants unless it
      is rendering: the search index, the entity tagger, width-fit measurement.
    - ``ai_text_markup`` -- joined like ``ai_text`` but with ``[b]``/``[i]`` tags
      left in, for the reader, which renders Kivy markup natively.

    ``ai_text`` is the stripped one deliberately.  A consumer that has never
    heard of emphasis gets correct text by doing the obvious thing, and only a
    caller that actively wants tags can get them.
    """

    group_id: str
    panel_num: int
    raw_ai_text: str
    ai_text: str
    ai_text_markup: str
    type: str
    text_box: list[tuple[int | float, int | float]]

    @classmethod
    def from_stored(
        cls,
        group_id: str,
        panel_num: int,
        stored_text: str,
        type_: str,
        text_box: list[tuple[int | float, int | float]],
    ) -> "SpeechText":
        """Build from the text as stored on disk, deriving the other two views.

        The only place the relationship between the three is defined, so that a
        caller cannot construct a group whose ``ai_text`` disagrees with its
        ``ai_text_markup``.

        Args:
            group_id: The group's key in the page JSON.
            panel_num: Panel number, or -1 when unplaced.
            stored_text: The group's ``ai_text`` value as read from disk.
            type_: The group's ``type`` field.
            text_box: The group's four corner points.

        Returns:
            A ``SpeechText`` with all three text views consistent.

        """
        joined = (
            stored_text.replace("-\n", "-")
            .replace("\u00ad\n", "")  # soft hyphen
            .replace("\u200b\n", "")  # zero-width space
        )
        return cls(
            group_id=group_id,
            panel_num=panel_num,
            raw_ai_text=stored_text,
            ai_text=strip_markup(joined),
            ai_text_markup=joined,
            type=type_,
            text_box=text_box,
        )

    def with_stored_text(self, stored_text: str) -> "SpeechText":
        """Return a copy carrying new text, with the derived views recomputed.

        The editor rewrites text as the user types.  Using ``dataclasses.replace``
        to set ``raw_ai_text`` alone would leave ``ai_text`` holding the text from
        before the edit, which is the sort of quiet inconsistency the three views
        are meant to prevent.

        Args:
            stored_text: The new text, in its on-disk form.

        Returns:
            A new ``SpeechText`` with all three views consistent.

        """
        return SpeechText.from_stored(
            group_id=self.group_id,
            panel_num=self.panel_num,
            stored_text=stored_text,
            type_=self.type,
            text_box=self.text_box,
        )


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
    speech_page_json: dict[str, Any]
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

    def groups_with_text_changes(self) -> list[str]:
        """Group ids whose *plain text* differs from disk, ignoring emphasis edits.

        ``has_group_changed`` answers "is there anything to save", and must stay
        sensitive to markup or an emphasis edit would be silently dropped.  This
        answers the different question "did the words change", which is what the
        correction-rate measurement counts.  Re-running the vision pass and
        changing only which words are bold must not register as a text
        correction against the 1.5% baseline.

        Returns:
            The ids of groups whose stripped text differs from what is on disk.

        """
        return _groups_with_text_changes(self)

    def save_group(self, to_file: Path | None = None, backup_file: Path | None = None) -> bool:
        return _save_speech_page_group(self, to_file, backup_file)

    def save_json(self, to_file: Path | None = None, backup_file: Path | None = None) -> None:
        _save_speech_page_group_json(self, to_file, backup_file)

    def renumber_groups(self) -> bool:
        """Sort groups by panel_num then spatial position, and renumber sequentially.

        Groups are sorted by (panel_num, min_y, min_x) so that both OCR engines
        produce the same ordering for the same page.  Groups with panel_num == -1
        sort last.

        ``speech_groups`` is rekeyed to the new ids in the same step.  It used
        to be left behind under the old ids, and ``save_group()`` — which looks
        up the page JSON by ``speech_groups``' keys — would then write one
        group's text over another's, or KeyError on ids the renumber had
        retired.

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

        # speech_groups is a subset of the JSON groups (page numbers are
        # excluded at load), so walk the JSON order and carry over what exists.
        rekeyed: dict[str, SpeechText] = {}
        for i, (old_id, _) in enumerate(sorted_items):
            speech_text = self.speech_groups.get(old_id)
            if speech_text is not None:
                rekeyed[str(i)] = replace(speech_text, group_id=str(i))
        if len(rekeyed) != len(self.speech_groups):
            msg = "speech_groups holds ids not present in the page JSON; cannot renumber."
            raise ValueError(msg)

        # The dataclass is frozen, so the field cannot be rebound — but the
        # dict can be rebuilt in place. The two views must move together.
        self.speech_groups.clear()
        self.speech_groups.update(rekeyed)

        self.speech_page_json["groups"] = renumbered
        return True


@dataclass(frozen=True, slots=True)
class MissingPrelimPage:
    """A page/engine whose prelim OCR JSON file does not exist."""

    fanta_page: str
    ocr_index: OcrTypes
    json_file: Path


@dataclass(frozen=True, slots=True)
class SpeechGroups:
    _comics_database: ComicsDatabase

    # TODO: Have a way to get with/with json and ocr file.
    def get_speech_page_groups(
        self, title: Titles, *, skip_missing: bool = False
    ) -> list[SpeechPageGroup]:
        """Load every page/engine of a title.

        Args:
            title: The title to load.
            skip_missing: When True, a page whose prelim OCR JSON file does not
                exist is warned about and left out instead of aborting the whole
                title. Only an absent file is tolerated — an unreadable or
                malformed one still raises. Default False so that a gap in the
                OCR data stays loud for callers that cannot survive one, such as
                the search-index builders.

        Returns:
            The loaded page groups, two per page when both engines are present.

        """
        volume = self._comics_database.get_fanta_volume_int_for(title)

        speech_page_groups: list[SpeechPageGroup] = []
        for srce_page, dest_page, ocr_index, json_file in self._iter_prelim_pages(title):
            if skip_missing and not json_file.is_file():
                logger.warning(f'No prelim OCR file - skipping page: "{json_file}".')
                continue
            speech_page_groups.append(
                get_speech_page_group(
                    self._comics_database, volume, title, ocr_index, srce_page, dest_page
                )
            )

        return speech_page_groups

    def get_missing_prelim_pages(self, title: Titles) -> list[MissingPrelimPage]:
        """Return the title's pages that have no prelim OCR JSON file.

        These are gaps in the OCR data rather than pages to be ignored: pages
        excluded by ``_get_srce_page_to_dest_page_map`` never appear here.

        Args:
            title: The title to check.

        Returns:
            One entry per missing page/engine, in page then engine order.

        """
        return [
            MissingPrelimPage(srce_page, ocr_index, json_file)
            for srce_page, _dest_page, ocr_index, json_file in self._iter_prelim_pages(title)
            if not json_file.is_file()
        ]

    def _iter_prelim_pages(self, title: Titles) -> Iterator[tuple[str, str, OcrTypes, Path]]:
        """Yield (srce_page, dest_page, ocr_index, prelim_json_file) for a title."""
        volume = self._comics_database.get_fanta_volume_int_for(title)
        comic = self._comics_database.get_comic_book_for(title)

        for srce_page, dest_page in self._get_srce_page_to_dest_page_map(comic).items():
            for ocr_index in OcrTypes:
                json_file = get_ocr_prelim_groups_json_file(
                    self._comics_database, volume, srce_page, ocr_index
                )
                yield srce_page, dest_page, ocr_index, json_file

    @staticmethod
    def _get_srce_page_to_dest_page_map(comic: ComicBook) -> dict[str, str]:
        srce_dest_map = {}

        # Deliberately the geometry-free variant. This wants the page mapping
        # and nothing else, and `get_sorted_srce_and_dest_pages` would first
        # demand a panel-segments file for every page, no older than its image.
        # The one-pager skip below discards all 133 pages of the synthetic
        # "All One-Pagers" collection -- whose pages have no segments file, and
        # should not -- but it only runs *after* the page list is built, so
        # loading the geometry here failed the whole title before the skip
        # could reach it.
        srce_and_dest_pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=True)
        for srce, dest in zip(
            srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages, strict=True
        ):
            if srce.page_type not in RESTORABLE_PAGE_TYPES:
                continue
            srce_page = Path(srce.page_filename).stem
            # A one-pager reprinted from another volume: its source image is a
            # symlink to that volume's page, which is where the OCR lives. Never
            # OCR work here, so not a gap either.
            if comic.get_srce_original_fixes_story_file(srce_page).is_symlink():
                continue
            srce_dest_map[srce_page] = get_page_num_str(dest)

        return srce_dest_map


def get_ocr_prelim_groups_json_file(
    comics_database: ComicsDatabase, volume: int, srce_page: str, ocr_index: OcrTypes
) -> Path:
    """Return the path of one page/engine's prelim OCR groups JSON file.

    Args:
        comics_database: The comics database, used to locate the volume's dir.
        volume: The Fantagraphics volume number.
        srce_page: The source page number, e.g. "078".
        ocr_index: Which OCR engine's file to name.

    Returns:
        The file's path, whether or not it exists.

    """
    ocr_prelim_dir = comics_database.get_fantagraphics_restored_ocr_prelim_volume_dir(volume)
    return ocr_prelim_dir / get_ocr_prelim_groups_json_filename(srce_page, ocr_index)


def get_speech_page_group(
    comics_database: ComicsDatabase,
    volume: int,
    title: Titles,
    ocr_index: OcrTypes,
    srce_page: str,
    dest_page: str,
) -> SpeechPageGroup:
    ocr_prelim_groups_json_file = get_ocr_prelim_groups_json_file(
        comics_database, volume, srce_page, ocr_index
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
        if _is_page_number(group):
            continue

        speech_groups[group_id] = SpeechText.from_stored(
            group_id=group_id,
            panel_num=group["panel_num"],
            stored_text=group["ai_text"],
            type_=group["type"],
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


def _groups_with_text_changes(speech_page_group: SpeechPageGroup) -> list[str]:
    stored = speech_page_group.speech_page_json["groups"]
    return [
        group_id
        for group_id, speech_text in speech_page_group.speech_groups.items()
        if not same_text_ignoring_markup(speech_text.raw_ai_text, stored[group_id]["ai_text"])
    ]


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
    if backup_file and to_file.is_file():
        # Copy rather than rename. A rename cannot cross a filesystem boundary,
        # and the backup directory may well be on another disk — it is a symlink
        # to the 2 TB drive here, which made every editor save raise
        # "Invalid cross-device link". Copying is also safer in its own right:
        # the original stays in place until the new content is written, whereas
        # a rename moves it away first and loses it if the write then fails.
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(to_file, backup_file)
    with to_file.open("w") as f:
        json.dump(speech_page_json, f, indent=4)
