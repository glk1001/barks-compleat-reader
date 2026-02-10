import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pyuca import Collator
from simplemma import lemmatize
from whoosh.analysis import STOP_WORDS, LowercaseFilter, StemFilter, StopFilter
from whoosh.fields import ID, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser

from .barks_titles import BARKS_TITLES
from .comics_database import ComicsDatabase
from .speech_groupers import SpeechGroups
from .whoosh_barks_terms import (
    ALL_CAPS,
    BARKSIAN_EXTRA_TERMS,
    NAME_MAP,
    TERMS_TO_CAPITALIZE,
    TERMS_TO_REMOVE,
)
from .whoosh_punct_tokenizer import WordWithPunctTokenizer

COLLATOR = Collator()

SUB_ALPHA_SPLIT_SIZE = 56

MY_STOP_WORDS = STOP_WORDS.union(["oh"])


@dataclass(frozen=True, slots=True)
class SpeechInfo:
    group_id: str
    panel_num: int
    speech_text: str


@dataclass(frozen=True, slots=True)
class PageInfo:
    comic_page: str
    speech_info_list: list[SpeechInfo]


@dataclass(slots=True)
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

            results = searcher.search(query, limit=1000)
            for hit in results:
                comic_title = hit["title"]
                prelim_results[comic_title].fanta_vol = int(hit["fanta_vol"])

                fanta_page = hit["fanta_page"]
                comic_page = hit["comic_page"]
                speech_info = SpeechInfo(
                    hit["content_id"], int(hit["panel_num"]), hit["content_raw"]
                )

                if fanta_page not in prelim_results[comic_title].fanta_pages:
                    prelim_results[comic_title].fanta_pages[fanta_page] = PageInfo(
                        comic_page, [speech_info]
                    )
                else:
                    assert (
                        prelim_results[comic_title].fanta_pages[fanta_page].comic_page == comic_page
                    )
                    prelim_results[comic_title].fanta_pages[fanta_page].speech_info_list.append(
                        speech_info
                    )

        # Sort the results by title and page.
        title_results = defaultdict(TitleInfo)
        for title in sorted(prelim_results.keys()):
            title_results[title].fanta_vol = prelim_results[title].fanta_vol
            for fanta_page in sorted(prelim_results[title].fanta_pages.keys()):
                page_info = prelim_results[title].fanta_pages[fanta_page]
                page_info.speech_info_list.sort(key=lambda x: int(x.group_id))
                title_results[title].fanta_pages[fanta_page] = page_info

        return title_results

    def get_all_titles(self) -> set[str]:
        with self._index.reader() as reader:
            return {t.decode("utf-8") for t in reader.lexicon("title")}

    def get_cleaned_unstemmed_terms(self) -> list[str]:
        return json.loads(self._cleaned_unstemmed_terms_path.read_text())

    def get_cleaned_lemmatized_terms(self) -> list[str]:
        return json.loads(self._cleaned_lemmatized_terms_path.read_text())

    def get_cleaned_alpha_split_unstemmed_terms(self) -> dict[str, dict[str, list[str]]]:
        return json.loads(self._cleaned_alpha_split_unstemmed_terms_path.read_text())

    def get_cleaned_alpha_split_lemmatized_terms(self) -> dict[str, dict[str, list[str]]]:
        return json.loads(self._cleaned_alpha_split_lemmatized_terms_path.read_text())

    def find_stemmed_words(self, search_words: str) -> TitleDict:
        return self.find_words(search_words, use_unstemmed_terms=False)

    def find_unstemmed_words(self, search_words: str) -> TitleDict:
        return self.find_words(search_words, use_unstemmed_terms=True)

    def find_all_words(self, search_words: str) -> TitleDict:
        found = self.find_stemmed_words(search_words)
        if found:
            return found

        return self.find_unstemmed_words(search_words)


class SearchEngineCreator(SearchEngine):
    def __init__(
        self, comics_database: ComicsDatabase, index_dir: Path, ocr_index_to_use: int
    ) -> None:
        self._comics_database = comics_database
        self._ocr_index_to_use = ocr_index_to_use
        assert self._ocr_index_to_use in [0, 1]

        # For keeping apostrophes and hyphens within words
        punct_analyzer = (
            WordWithPunctTokenizer() | LowercaseFilter() | StopFilter(stoplist=MY_STOP_WORDS)
        )
        schema = Schema(
            title=ID(stored=True),
            fanta_vol=ID(stored=True),
            fanta_page=ID(stored=True),
            comic_page=ID(stored=True),
            content_id=ID(stored=True),
            panel_num=ID(stored=True),
            content=TEXT(stored=False, lang="en", analyzer=punct_analyzer | StemFilter(lang="en")),
            unstemmed=TEXT(stored=False, lang="en", analyzer=punct_analyzer),
            content_raw=TEXT(stored=True, lang="en"),
        )
        index_dir.mkdir(parents=True, exist_ok=True)
        self._index = create_in(index_dir, schema)

        super().__init__(index_dir)

    def index_volumes(self, volumes: list[int]) -> None:
        json_volumes_path = self._index.storage.folder / "volumes.json"
        with json_volumes_path.open("w") as f:
            json.dump(volumes, f, indent=4)

        self._index_volume_titles(volumes)

        with self._index.reader() as reader:
            all_unstemmed_terms = [t.decode("utf-8") for t in reader.lexicon("unstemmed")]
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

    def _index_volume_titles(self, volumes: list[int]) -> None:
        all_speech_groups = SpeechGroups(self._comics_database, volumes)
        all_speech_groups.load_groups()

        writer = self._index.writer()

        for title, speech_page_groups in all_speech_groups.all_speech_page_groups.items():
            title_str = BARKS_TITLES[title]
            for speech_page in speech_page_groups:
                if speech_page["ocr_index"] != self._ocr_index_to_use:
                    continue
                for group_id, speech_text in speech_page["speech_groups"].items():
                    writer.add_document(
                        title=title_str,
                        fanta_vol=str(speech_page["fanta_vol"]),
                        fanta_page=speech_page["fanta_page"],
                        comic_page=speech_page["comic_page"],
                        content_id=group_id,
                        panel_num=str(speech_text["panel_num"]),
                        content=speech_text["ai_text"],
                        unstemmed=speech_text["ai_text"],
                        content_raw=speech_text["raw_ai_text"],
                    )

        writer.commit()

    @staticmethod
    def _get_cleaned_unstemmed_terms(unstemmed_terms: list[str]) -> set[str]:
        cleaned_unstemmed_terms = set()
        for term in unstemmed_terms:
            if term in TERMS_TO_REMOVE:
                continue

            if term in NAME_MAP:
                cleaned_term = NAME_MAP[term]
            elif term in ALL_CAPS:
                cleaned_term = term.upper()
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
