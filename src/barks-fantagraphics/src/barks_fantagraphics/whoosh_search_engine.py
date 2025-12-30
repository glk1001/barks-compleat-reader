import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from pyuca import Collator
from simplemma import lemmatize
from whoosh.analysis import LowercaseFilter, StopFilter
from whoosh.analysis.analyzers import StandardAnalyzer
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
from .whoosh_barks_terms import BARKSIAN_EXTRA_TERMS, NAME_MAP, TERMS_TO_CAPITALIZE, TERMS_TO_REMOVE
from .whoosh_punct_tokenizer import WordWithPunctTokenizer

COLLATOR = Collator()

SUB_ALPHA_SPLIT_SIZE = 56


@dataclass
class PageInfo:
    comic_page: str = ""
    speech_bubbles: list[str] = field(default_factory=list)


@dataclass
class TitleInfo:
    fanta_vol: int = 0
    fanta_pages: dict[str, PageInfo] = field(default_factory=dict)


type TitleDict = dict[str, TitleInfo]


class SearchEngine:
    def __init__(self, index_dir: Path) -> None:
        self._index = open_dir(index_dir)

        self._unstemmed_terms_path = self._index.storage.folder / "unstemmed-terms.json"
        self._cleaned_unstemmed_terms_path = (
            self._index.storage.folder / "cleaned-unstemmed-terms.json"
        )
        self._cleaned_lemmatized_terms_path = (
            self._index.storage.folder / "cleaned-lemmatized-terms.json"
        )
        self._cleaned_alpha_split_unstemmed_terms_path = (
            self._index.storage.folder / "cleaned-alpha-split-unstemmed-terms.json"
        )
        self._cleaned_alpha_split_lemmatized_terms_path = (
            self._index.storage.folder / "cleaned-alpha-split-lemmatized-terms.json"
        )

    def find_words(self, search_words: str, use_unstemmed_terms: bool) -> TitleDict:
        prelim_results = defaultdict(TitleInfo)
        with self._index.searcher() as searcher:
            field_name = "unstemmed" if use_unstemmed_terms else "content"
            query = QueryParser(field_name, self._index.schema).parse(search_words, debug=False)

            results = searcher.search(query, limit=100)
            for hit in results:
                comic_title = hit["title"]
                prelim_results[comic_title].fanta_vol = int(hit["fanta_vol"])

                fanta_page = hit["fanta_page"]
                comic_page = hit["comic_page"]
                speech_bubble = hit["content"]

                if fanta_page not in prelim_results[comic_title].fanta_pages:
                    prelim_results[comic_title].fanta_pages[fanta_page] = PageInfo()
                prelim_results[comic_title].fanta_pages[fanta_page].comic_page = comic_page
                prelim_results[comic_title].fanta_pages[fanta_page].speech_bubbles.append(
                    speech_bubble
                )

        # Sort the results by title and page.
        title_results = defaultdict(TitleInfo)
        for title in sorted(prelim_results.keys()):
            title_results[title].fanta_vol = prelim_results[title].fanta_vol
            for fanta_page in sorted(prelim_results[title].fanta_pages.keys()):
                title_results[title].fanta_pages[fanta_page] = prelim_results[title].fanta_pages[
                    fanta_page
                ]

        return title_results

    def get_cleaned_unstemmed_terms(self) -> list[str]:
        return json.loads(self._cleaned_unstemmed_terms_path.read_text())

    def get_cleaned_lemmatized_terms(self) -> list[str]:
        return json.loads(self._cleaned_lemmatized_terms_path.read_text())

    def get_cleaned_alpha_split_unstemmed_terms(self) -> dict[str, dict[str, list[str]]]:
        return json.loads(self._cleaned_alpha_split_unstemmed_terms_path.read_text())

    def get_cleaned_alpha_split_lemmatized_terms(self) -> dict[str, dict[str, list[str]]]:
        return json.loads(self._cleaned_alpha_split_lemmatized_terms_path.read_text())

    def find_all_words(self, search_words: str) -> TitleDict:
        return self.find_words(search_words, use_unstemmed_terms=False)

    def find_unstemmed_words(self, search_words: str) -> TitleDict:
        return self.find_words(search_words, use_unstemmed_terms=True)


class SearchEngineCreator(SearchEngine):
    def __init__(self, comics_database: ComicsDatabase, index_dir: Path) -> None:
        self._comics_database = comics_database

        # For keeping apostrophes and hyphens within words
        analyzer = WordWithPunctTokenizer() | LowercaseFilter() | StopFilter()
        schema = Schema(
            title=TEXT(stored=True),
            fanta_vol=ID(stored=True),
            fanta_page=ID(stored=True),
            comic_page=ID(stored=True),
            content=TEXT(stored=True, lang="en", analyzer=StandardAnalyzer()),
            unstemmed=TEXT(stored=False, analyzer=analyzer),
        )
        index_dir.mkdir(parents=True, exist_ok=True)
        self._index = create_in(index_dir, schema)

        super().__init__(index_dir)

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

        with self._index.reader() as reader:
            all_unstemmed_terms = [t[1].decode("utf-8") for t in reader.terms_from("unstemmed", "")]
        with self._unstemmed_terms_path.open("w") as f:
            json.dump(all_unstemmed_terms, f, indent=4)
        with self._cleaned_unstemmed_terms_path.open("w") as f:
            cleaned_unstemmed_terms = sorted(
                self._get_cleaned_unstemmed_terms(all_unstemmed_terms), key=COLLATOR.sort_key
            )
            json.dump(cleaned_unstemmed_terms, f, indent=4)
        with self._cleaned_lemmatized_terms_path.open("w") as f:
            cleaned_lemmatized_terms = sorted(
                self._get_cleaned_lemmatized_terms(cleaned_unstemmed_terms), key=COLLATOR.sort_key
            )
            json.dump(cleaned_lemmatized_terms, f, indent=4)
        with self._cleaned_alpha_split_unstemmed_terms_path.open("w") as f:
            json.dump(self._get_alpha_split_terms(cleaned_unstemmed_terms), f, indent=4)
        with self._cleaned_alpha_split_lemmatized_terms_path.open("w") as f:
            json.dump(self._get_alpha_split_terms(cleaned_lemmatized_terms), f, indent=4)

    @staticmethod
    def _get_cleaned_unstemmed_terms(unstemmed_terms: list[str]) -> set[str]:
        cleaned_unstemmed_terms = set()
        for term in unstemmed_terms:
            if term in TERMS_TO_REMOVE:
                continue

            if term in NAME_MAP:
                cleaned_term = NAME_MAP[term]
            elif term in TERMS_TO_CAPITALIZE:
                cleaned_term = term.capitalize()
            else:
                cleaned_term = term

            if cleaned_term:
                cleaned_unstemmed_terms.add(cleaned_term)

        return cleaned_unstemmed_terms.union(BARKSIAN_EXTRA_TERMS)

    @staticmethod
    def _get_cleaned_lemmatized_terms(terms: list[str]) -> set[str]:
        lemmatized_terms = set()
        for term in terms:
            lemmatized_term = lemmatize(term, lang="en")
            if lemmatized_term == term or lemmatized_term not in lemmatized_terms:
                lemmatized_terms.add(term)

        return lemmatized_terms

    def _add_page_content(self, writer: SegmentWriter, title: str) -> None:
        json_files = JsonFiles(self._comics_database, title)

        comic = self._comics_database.get_comic_book(title)
        srce_dest_map = self._get_srce_page_to_dest_page_map(comic)
        ocr_files = comic.get_srce_restored_raw_ocr_story_files(RESTORABLE_PAGE_TYPES)

        for ocr_file in ocr_files:
            json_files.set_ocr_file(ocr_file)
            fanta_page = json_files.page
            dest_page = srce_dest_map[fanta_page]

            try:
                ocr_prelim_group2 = json.loads(
                    json_files.ocr_prelim_groups_json_file[1].read_text()
                )
            except Exception as e:
                msg = (
                    f"Error reading ocr_prelim_groups:"
                    f' "{json_files.ocr_prelim_groups_json_file[1]}".'
                )
                raise ValueError(msg) from e

            for group in ocr_prelim_group2["groups"].values():
                ai_text = (
                    group["ai_text"]
                    .replace("-\n", "-")
                    .replace("\u00ad\n", "")
                    .replace("\u200b\n", "")
                )
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

    def _get_alpha_split_terms(self, terms: list[str]) -> dict[str, dict[str, list[str]]]:
        alpha_dict = {}
        first_letter_list = []
        current_first_letter_group = "0"
        for term in terms:
            first_letter = term[0].lower()
            if not (
                ("a" <= first_letter <= "z")
                or ("0" <= first_letter <= "9")
                or (first_letter == "'")
            ):
                msg = f'Invalid first letter: "{first_letter}". Term: "{term}".'
                raise ValueError(msg)
            if "0" <= first_letter <= "9":
                first_letter = "0"

            if current_first_letter_group != first_letter:
                alpha_dict[current_first_letter_group] = self._get_sub_alpha_split_terms(
                    first_letter_list
                )
                first_letter_list = []
                current_first_letter_group = first_letter

            first_letter_list.append(term)

        if first_letter_list:
            alpha_dict[current_first_letter_group] = self._get_sub_alpha_split_terms(
                first_letter_list
            )

        return self._get_similar_size_alpha_groups(alpha_dict)

    @staticmethod
    def _get_sub_alpha_split_terms(
        alpha_terms: list[str],
    ) -> dict[str, list[str]]:
        if not alpha_terms:
            return {}

        prefix_len = 1 if "0" <= alpha_terms[0][0] <= "9" else 2
        current_prefix = alpha_terms[0][:prefix_len].lower()

        sub_alpha_dict = {current_prefix: []}
        for term in alpha_terms:
            if current_prefix != term[:prefix_len].lower():
                current_prefix = term[:prefix_len].lower()
                sub_alpha_dict[current_prefix] = []
            sub_alpha_dict[current_prefix].append(term)

        return sub_alpha_dict

    def _get_similar_size_alpha_groups(
        self, alpha_unstemmed_terms: dict[str, dict[str, list[str]]]
    ) -> dict[str, dict[str, list[str]]]:
        assert alpha_unstemmed_terms

        similar_size_alpha_terms = {}
        for first_letter, sub_alpha_lists in alpha_unstemmed_terms.items():
            similar_size_alpha_terms[first_letter] = self._get_similar_size_sub_alpha_groups(
                sub_alpha_lists
            )

        return similar_size_alpha_terms

    @staticmethod
    def _get_similar_size_sub_alpha_groups(
        sub_alpha_lists: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        assert sub_alpha_lists

        similar_size_sub_alpha_terms = defaultdict(list)
        current_size = 0
        current_prefix = ""
        for prefix, sub_alpha_list in sub_alpha_lists.items():
            if not current_prefix:
                current_prefix = prefix

            current_size += len(sub_alpha_list)

            if current_size > SUB_ALPHA_SPLIT_SIZE:
                current_prefix = prefix
                current_size = len(sub_alpha_list)

            similar_size_sub_alpha_terms[current_prefix].extend(sub_alpha_list)

        return similar_size_sub_alpha_terms
