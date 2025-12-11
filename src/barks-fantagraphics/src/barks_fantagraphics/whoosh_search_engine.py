import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from whoosh.analysis import StandardAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser
from whoosh.writing import SegmentWriter

from .barks_titles import is_non_comic_title
from .comic_book import ComicBook
from .comics_consts import RESTORABLE_PAGE_TYPES
from .comics_database import ComicsDatabase
from .ocr_json_files import JsonFiles
from .pages import get_page_num_str, get_sorted_srce_and_dest_pages


@dataclass
class TitleInfo:
    fanta_vol: int = 0
    pages: list[tuple[str, str, str]] = field(default_factory=list)


type TitleDict = dict[str, TitleInfo]


class SearchEngine:
    def __init__(self, index_dir: Path) -> None:
        self._index = open_dir(index_dir)

    def find_words(self, search_words: str, use_unstemmed_terms: bool) -> TitleDict:
        prelim_results = defaultdict(TitleInfo)
        with self._index.searcher() as searcher:
            field_name = "unstemmed" if use_unstemmed_terms else "content"
            query = QueryParser(field_name, self._index.schema).parse(search_words)

            results = searcher.search(query, limit=100)
            for hit in results:
                prelim_results[hit["title"]].fanta_vol = int(hit["fanta_vol"])
                prelim_results[hit["title"]].pages.append(
                    (hit["fanta_page"], hit["comic_page"], hit["content"])
                )

        # Sort the results by title and page.
        title_results = defaultdict(TitleInfo)
        for title in sorted(prelim_results.keys()):
            title_results[title].fanta_vol = prelim_results[title].fanta_vol
            title_results[title].pages = sorted(prelim_results[title].pages)

        return title_results


class SearchEngineCreator(SearchEngine):
    def __init__(self, comics_database: ComicsDatabase, index_dir: Path) -> None:
        super().__init__(index_dir)

        self._comics_database = comics_database

        schema = Schema(
            title=TEXT(stored=True),
            fanta_vol=ID(stored=True),
            fanta_page=ID(stored=True),
            comic_page=ID(stored=True),
            content=TEXT(stored=True, lang="en"),
            unstemmed=TEXT(stored=False, analyzer=StandardAnalyzer()),
        )
        index_dir.mkdir(parents=True, exist_ok=True)
        self._index = create_in(index_dir, schema)

        self._index = open_dir(index_dir)

    def index_volumes(self, volumes: list[int]) -> None:
        json_volumes_path = self._index.storage.folder / "volumes.json"
        with json_volumes_path.open("w") as f:
            json.dump(volumes, f, indent=4)

        writer = self._index.writer()

        titles = self._comics_database.get_configured_titles_in_fantagraphics_volumes(volumes)
        for title, _ in titles:
            if is_non_comic_title(title):
                logger.warning(f'Not a comic title "{title}" - skipping.')
                continue

            self._add_page_content(writer, title)

        writer.commit()

    def _add_page_content(self, writer: SegmentWriter, title: str) -> None:
        json_files = JsonFiles(self._comics_database, title)

        comic = self._comics_database.get_comic_book(title)
        srce_dest_map = self._get_srce_page_to_dest_page_map(comic)
        ocr_files = comic.get_srce_restored_raw_ocr_story_files(RESTORABLE_PAGE_TYPES)

        for ocr_file in ocr_files:
            json_files.set_ocr_file(ocr_file)
            fanta_page = json_files.page
            dest_page = srce_dest_map[fanta_page]

            ocr_prelim_group2 = json.loads(json_files.ocr_prelim_groups_json_file[1].read_text())

            for group in ocr_prelim_group2["groups"].values():
                ai_text = group["ai_text"]
                writer.add_document(
                    title=title,
                    fanta_vol=str(comic.fanta_book.volume),
                    fanta_page=fanta_page,
                    comic_page=dest_page,
                    content=ai_text,
                    unstemmed=ai_text,
                )

    @staticmethod
    def _get_srce_page_to_dest_page_map(comic: ComicBook) -> dict[str, str]:
        srce_dest_map = {}

        srce_and_dest_pages = get_sorted_srce_and_dest_pages(comic, get_full_paths=True)
        for srce, dest in zip(
            srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages, strict=True
        ):
            srce_dest_map[Path(srce.page_filename).stem] = get_page_num_str(dest)

        return srce_dest_map
