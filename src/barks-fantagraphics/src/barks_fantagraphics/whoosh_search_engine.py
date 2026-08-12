import heapq
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from pyuca import Collator
from whoosh.analysis import STOP_WORDS, LowercaseFilter, StopFilter
from whoosh.fields import ID, KEYWORD, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser
from whoosh.query import Query
from whoosh.searching import Hit

from .comics_database import ComicsDatabase
from .entity_types import EntityType
from .speech_groupers import OcrTypes, SpeechGroups
from .speech_markup import strip_markup
from .whoosh_barks_terms import (
    ALL_CAPS,
    BARKSIAN_ENTITY_TYPE_MAP,
    BARKSIAN_EXTRA_TERMS,
    CAPITALIZATION_MAP,
    CONTEXT_SENSITIVE_WORDS,
    FRAGMENTS_TO_SUPPRESS,
    MULTI_WORD_TERMS_TO_SUPPRESS,
    TERMS_TO_CAPITALIZE,
    TERMS_TO_REMOVE,
)
from .whoosh_punct_tokenizer import WordWithPunctTokenizer

COLLATOR = Collator()

SUB_ALPHA_SPLIT_SIZE = 56

# Whoosh truncates at this many hits. A common word legitimately appears on more pages
# than this, so the cap is set above the largest realistic result set rather than at a
# round number that would silently drop matches.
_SEARCH_RESULT_LIMIT = 100_000

MY_STOP_WORDS = STOP_WORDS.union(["oh"])

ENTITY_TYPES = list(EntityType)
ENTITY_FIELDS = [f"entities_{t}" for t in ENTITY_TYPES]

# Lowercase→proper-case lookup from curated names for normalizing entity casing
_CURATED_NAME_LOOKUP: dict[str, str] = {t.lower(): t for t in BARKSIAN_EXTRA_TERMS}


def _build_curated_entity_sets() -> dict[EntityType, set[str]]:
    """Build a mapping from EntityType to the set of lowercase curated names for that type."""
    curated: dict[EntityType, set[str]] = {t: set() for t in EntityType}

    for term_set, entity_type in BARKSIAN_ENTITY_TYPE_MAP.items():
        for term in term_set:
            curated[entity_type].add(term.lower())

    # Include context-sensitive canonicals so they survive the curated filter.
    # The entity tagger already returns correct casing for these, so no lookup update needed.
    for fallback_type, fallback_canonical, rules in CONTEXT_SENSITIVE_WORDS.values():
        curated[fallback_type].add(fallback_canonical.lower())
        for _pat, etype, canon in rules:
            curated[etype].add(canon.lower())

    return curated


def _filter_entities_to_curated(
    entities: dict[EntityType, set[str]], curated_sets: dict[EntityType, set[str]]
) -> dict[EntityType, set[str]]:
    """Keep only curated entity names, normalized to their canonical casing."""
    filtered: dict[EntityType, set[str]] = {}
    for entity_type in ENTITY_TYPES:
        curated = curated_sets.get(EntityType(entity_type), set())
        names = entities.get(entity_type, set())
        filtered[entity_type] = {
            _CURATED_NAME_LOOKUP.get(n.lower(), n) for n in names if n.lower() in curated
        }
    return filtered


def _normalize_entity_names(extra_terms: set[str], existing_lower: set[str]) -> set[str]:
    """Normalize entity names against curated sets, filtering garbage spaCy names."""
    normalized = set()
    for t in extra_terms:
        low = t.lower()
        # Skip if a single-word term already covers this
        if low in existing_lower:
            continue
        # Use curated casing if available
        if low in _CURATED_NAME_LOOKUP:
            normalized.add(_CURATED_NAME_LOOKUP[low])
            continue
        # For spaCy-only entities: reject garbage
        if _is_valid_entity_term(t):
            normalized.add(t)
    return normalized


def _is_valid_entity_term(term: str) -> bool:
    """Filter garbage spaCy-only entity names not matched by curated sets."""
    if not term or "\n" in term:
        return False
    first = term[0].lower()
    if not (("a" <= first <= "z") or ("0" <= first <= "9") or first == "'"):
        return False
    # Reject if any word is all-caps (longer than 2 chars) — speech bubble artifact
    max_caps_len = 2
    return not any(w == w.upper() and len(w) > max_caps_len for w in term.split())


@dataclass(frozen=True, slots=True)
class SpeechInfo:
    """One matching speech group in a search result.

    ``speech_text`` is plain and ``speech_text_markup`` carries the ``[b]``/``[i]``
    emphasis tags, the same split as ``SpeechText`` and for the same reason: a
    caller that has not heard of emphasis gets correct text from the obvious
    attribute.  Only the reader's bubble list, which renders Kivy markup, wants
    the other one.
    """

    group_id: str
    panel_num: int
    speech_text: str
    speech_text_markup: str
    entity_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PageInfo:
    comic_page: str
    speech_info_list: list[SpeechInfo]


@dataclass(slots=True)
class TitleInfo:
    fanta_vol: int = 0
    fanta_pages: dict[str, PageInfo] = field(default_factory=dict)


type TitleDict = dict[str, TitleInfo]


def _speech_sort_key(speech_info: SpeechInfo) -> tuple[int, str]:
    """Order speech groups on a page numerically, tolerating non-numeric group ids.

    Group ids are numeric strings in a well-formed index. A malformed one must not
    take down the whole search, so it sorts after the numbered groups by its text.
    """
    if speech_info.group_id.isdigit():
        return (int(speech_info.group_id), "")
    return (sys.maxsize, speech_info.group_id)


class SearchEngine:
    def __init__(self, index_dir: Path) -> None:
        self._index = open_dir(index_dir)

        self._unstemmed_terms_path = self._index.storage.folder / "unstemmed-terms.json"
        self._cleaned_terms_path = self._index.storage.folder / "cleaned-unstemmed-terms.json"
        self._cleaned_alpha_split_terms_path = (
            self._index.storage.folder / "cleaned-alpha-split-unstemmed-terms.json"
        )
        self._most_common_unstemmed_terms_path = (
            self._index.storage.folder / "most-common-unstemmed-terms.json"
        )
        self._least_common_unstemmed_terms_path = (
            self._index.storage.folder / "least-common-unstemmed-terms.json"
        )
        self._entity_terms_paths = {
            t: self._index.storage.folder / f"entities-{t}-terms.json" for t in ENTITY_TYPES
        }

    @staticmethod
    def _get_entity_types(hit: Hit, search_words: str) -> tuple[str, ...]:
        # Match whole words, not substrings: a substring test makes short query tokens
        # ("or", "a") match unrelated entity names.
        words_lower = {w.lower() for w in search_words.split()}
        types = []
        for entity_type in ENTITY_TYPES:
            field_value = hit.get(f"entities_{entity_type}", "")
            if field_value:
                name_words = {
                    word for name in field_value.split(",") for word in name.strip().lower().split()
                }
                if words_lower & name_words:
                    types.append(entity_type)
        return tuple(types)

    def _collect_and_sort_results(self, hits: list[Hit], search_words: str) -> TitleDict:
        prelim_results = defaultdict(TitleInfo)
        for hit in hits:
            comic_title = hit["title"]
            prelim_results[comic_title].fanta_vol = int(hit["fanta_vol"])

            fanta_page = hit["fanta_page"]
            comic_page = hit["comic_page"]
            # The stored `content_raw` carries markup; what was indexed did not.
            stored_text = hit["content_raw"]
            speech_info = SpeechInfo(
                group_id=hit["content_id"],
                panel_num=int(hit["panel_num"]),
                speech_text=strip_markup(stored_text),
                speech_text_markup=stored_text,
                entity_types=self._get_entity_types(hit, search_words),
            )

            if fanta_page not in prelim_results[comic_title].fanta_pages:
                prelim_results[comic_title].fanta_pages[fanta_page] = PageInfo(
                    comic_page, [speech_info]
                )
            else:
                existing_page = prelim_results[comic_title].fanta_pages[fanta_page]
                if existing_page.comic_page != comic_page:
                    msg = (
                        f'Index inconsistency for "{comic_title}": fanta page {fanta_page}'
                        f" maps to both comic page {existing_page.comic_page} and {comic_page}."
                    )
                    raise ValueError(msg)
                existing_page.speech_info_list.append(speech_info)

        title_results: TitleDict = {}
        for title in sorted(prelim_results.keys()):
            title_info = TitleInfo(fanta_vol=prelim_results[title].fanta_vol)
            for fanta_page in sorted(prelim_results[title].fanta_pages.keys()):
                page_info = prelim_results[title].fanta_pages[fanta_page]
                page_info.speech_info_list.sort(key=_speech_sort_key)
                title_info.fanta_pages[fanta_page] = page_info
            title_results[title] = title_info

        return title_results

    def _parse_literal(self, field_name: str, text: str) -> Query:
        """Parse ``text`` as a literal phrase rather than a query expression.

        Every caller passes a term taken from the index or a name chosen from a list,
        never hand-written Whoosh syntax. Quoting keeps characters that the parser
        would otherwise treat as operators -- the index holds terms like
        ``500,000,000...`` -- from being reinterpreted or raising.
        """
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return QueryParser(field_name, self._index.schema).parse(f'"{escaped}"')

    def find_words(self, search_words: str) -> TitleDict:
        with self._index.searcher() as searcher:
            query = self._parse_literal("unstemmed", search_words)
            results = searcher.search(query, limit=_SEARCH_RESULT_LIMIT)
            return self._collect_and_sort_results(results, search_words)

    def iter_all_stored_fields(self) -> Iterator[dict[str, str]]:
        """Yield stored fields for every document in the index."""
        with self._index.reader() as reader:
            for docnum in reader.all_doc_ids():
                yield reader.stored_fields(docnum)

    def get_all_titles(self) -> set[str]:
        with self._index.reader() as reader:
            return {t.decode("utf-8") for t in reader.lexicon("title")}

    def get_cleaned_terms(self) -> list[str]:
        if not self._cleaned_terms_path.exists():
            msg = (
                f"Index sidecar file is missing: {self._cleaned_terms_path}."
                " The search index needs rebuilding."
            )
            raise FileNotFoundError(msg)
        return json.loads(self._cleaned_terms_path.read_text())

    def get_cleaned_alpha_split_terms(self) -> dict[str, dict[str, list[str]]]:
        if not self._cleaned_alpha_split_terms_path.exists():
            msg = (
                f"Index sidecar file is missing: {self._cleaned_alpha_split_terms_path}."
                " The search index needs rebuilding."
            )
            raise FileNotFoundError(msg)
        return json.loads(self._cleaned_alpha_split_terms_path.read_text())

    def find_entities(self, entity_type: str, entity_name: str) -> TitleDict:
        # The name is quoted so multi-word names (e.g. "Duk Duk") match as a single
        # token in the comma-separated KEYWORD field.
        with self._index.searcher() as searcher:
            query = self._parse_literal(f"entities_{entity_type}", entity_name)
            results = searcher.search(query, limit=_SEARCH_RESULT_LIMIT)
            return self._collect_and_sort_results(results, entity_name)

    def get_entity_terms(self, entity_type: str) -> list[str]:
        path = self._entity_terms_paths[EntityType(entity_type)]
        if path.exists():
            return json.loads(path.read_text())
        return []

    def get_alpha_split_entity_terms(self, entity_type: str) -> dict[str, dict[str, list[str]]]:
        terms = self.get_entity_terms(entity_type)
        if not terms:
            return {}
        # Entity terms may contain garbage entries with invalid first chars (e.g. "-ER-").
        # Filter to only terms starting with a letter, digit, or apostrophe.
        valid = [
            t
            for t in terms
            if t and (("a" <= t[0].lower() <= "z") or ("0" <= t[0] <= "9") or t[0] == "'")
        ]
        return self._get_alpha_split_terms(valid) if valid else {}

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
                if first_letter_list:
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


class SearchEngineCreator(SearchEngine):
    def __init__(
        self, comics_database: ComicsDatabase, index_dir: Path, ocr_index_to_use: OcrTypes
    ) -> None:
        self._comics_database = comics_database
        self._ocr_index_to_use = ocr_index_to_use

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
            unstemmed=TEXT(stored=False, lang="en", analyzer=punct_analyzer),
            content_raw=TEXT(stored=True, lang="en"),
            entities_person=KEYWORD(stored=True, commas=True, scorable=True),
            entities_location=KEYWORD(stored=True, commas=True, scorable=True),
            entities_org=KEYWORD(stored=True, commas=True, scorable=True),
            entities_work=KEYWORD(stored=True, commas=True, scorable=True),
            entities_misc=KEYWORD(stored=True, commas=True, scorable=True),
        )
        index_dir.mkdir(parents=True, exist_ok=True)
        self._index = create_in(index_dir, schema)

        super().__init__(index_dir)

    def get_search_engine(self) -> SearchEngine:
        """Return a read-only search engine backed by the index just built."""
        return self

    def index_volumes(
        self,
        volumes: list[int],
        entity_tagger: Callable[[str], dict[str, set[str]]] | None = None,
        entity_provider: Callable[[str, str, str], dict[str, set[str]]] | None = None,
    ) -> None:
        json_volumes_path = self._index.storage.folder / "volumes.json"
        with json_volumes_path.open("w") as f:
            json.dump(volumes, f, indent=4)

        self._index_volume_titles(
            volumes, entity_tagger=entity_tagger, entity_provider=entity_provider
        )

        if entity_tagger or entity_provider:
            self._generate_entity_term_lists()

        all_entity_names: set[str] = set()
        for entity_type in ENTITY_TYPES:
            all_entity_names.update(self.get_entity_terms(entity_type))

        with self._index.reader() as reader:
            all_unstemmed_terms = [t.decode("utf-8") for t in reader.lexicon("unstemmed")]
        with self._unstemmed_terms_path.open("w") as f:
            json.dump(all_unstemmed_terms, f, indent=4)
        with self._cleaned_terms_path.open("w") as f:
            cleaned_terms = sorted(
                self._get_cleaned_terms(all_unstemmed_terms, entity_names=all_entity_names),
                key=COLLATOR.sort_key,
            )
            json.dump(cleaned_terms, f, indent=4)
        with self._cleaned_alpha_split_terms_path.open("w") as f:
            json.dump(self._get_alpha_split_terms(cleaned_terms), f, indent=4)

        most_frequent_words = self._get_ai_text_term_frequencies().most_common()
        with self._most_common_unstemmed_terms_path.open("w") as f:
            json.dump(most_frequent_words, f, indent=4)

        least_frequent_words = self._get_least_common_ai_text_terms()
        with self._least_common_unstemmed_terms_path.open("w") as f:
            json.dump(least_frequent_words, f, indent=4)

    def _index_volume_titles(
        self,
        volumes: list[int],
        entity_tagger: Callable[[str], dict[str, set[str]]] | None = None,
        entity_provider: Callable[[str, str, str], dict[str, set[str]]] | None = None,
    ) -> None:
        all_speech_groups = SpeechGroups(self._comics_database)
        curated_sets = _build_curated_entity_sets()

        writer = self._index.writer()

        titles = self._comics_database.get_configured_titles_in_fantagraphics_volumes(
            volumes, exclude_non_comics=True
        )
        for title_str, fanta_info in titles:
            title = fanta_info.comic_book_info.title
            speech_page_groups = all_speech_groups.get_speech_page_groups(title)
            for speech_page in speech_page_groups:
                if speech_page.ocr_index != self._ocr_index_to_use:
                    continue
                for group_id, speech_text in speech_page.speech_groups.items():
                    if entity_provider:
                        entities = entity_provider(title_str, speech_page.fanta_page, group_id)
                    elif entity_tagger:
                        entities = entity_tagger(speech_text.ai_text)
                    else:
                        entities = None

                    if entities is not None:
                        entities = _filter_entities_to_curated(
                            cast("dict[EntityType, set[str]]", entities), curated_sets
                        )
                        entity_kwargs = {
                            f"entities_{et}": ",".join(sorted(entities.get(et, set())))
                            for et in ENTITY_TYPES
                        }
                    else:
                        entity_kwargs = dict.fromkeys(ENTITY_FIELDS, "")

                    writer.add_document(
                        title=title_str,
                        fanta_vol=str(speech_page.fanta_vol),
                        fanta_page=speech_page.fanta_page,
                        comic_page=speech_page.comic_page,
                        content_id=group_id,
                        panel_num=str(speech_text.panel_num),
                        unstemmed=speech_text.ai_text,
                        # Indexed stripped, stored marked up. Whoosh's
                        # `_stored_<field>` convention lets one field do both, so
                        # a search for "saboteurs" still matches a group lettered
                        # "[b]SABOTEURS[/b]" while the reader gets the tags back
                        # to render. Indexing the marked-up form instead would
                        # put "b" and split words into the lexicon.
                        content_raw=strip_markup(speech_text.raw_ai_text),
                        _stored_content_raw=speech_text.raw_ai_text,
                        **entity_kwargs,
                    )

        writer.commit()

    def _generate_entity_term_lists(self) -> None:
        with self._index.reader() as reader:
            for entity_type in ENTITY_TYPES:
                field_name = f"entities_{entity_type}"
                terms = sorted({t.decode("utf-8") for t in reader.lexicon(field_name)})
                path = self._entity_terms_paths[entity_type]
                with path.open("w") as f:
                    json.dump(terms, f, indent=4)

    def _get_ai_text_term_frequencies(self) -> Counter:
        token_counts = Counter()

        with self._index.reader() as reader:
            # iter_field yields tuples: (text, doc_freq, total_freq)
            for text, terminfo in reader.iter_field("unstemmed"):
                # total_freq = Total times word appears across ALL docs
                # _doc_freq   = Number of unique docs containing the word
                token_counts[text.decode("utf-8")] = round(terminfo.weight())

        return token_counts

    def _get_least_common_ai_text_terms(self, top_n: int = 200) -> list[tuple[str, int]]:
        with self._index.reader() as reader:
            # Create a generator that yields (total_freq, text).
            # We swap the order so the heap sorts by frequency first.
            term_generator = (
                (text.decode("utf-8"), round(terminfo.weight()))
                for text, terminfo in reader.iter_field("unstemmed")
                if terminfo.weight() > 1
            )

            # Efficiently find the N smallest items without sorting the whole list.
            return heapq.nsmallest(top_n, term_generator)

    @staticmethod
    def _get_cleaned_terms(
        unstemmed_terms: list[str],
        entity_names: set[str] | None = None,
    ) -> set[str]:
        cleaned_terms = set()
        for term in unstemmed_terms:
            if term in TERMS_TO_REMOVE:
                continue
            if term in FRAGMENTS_TO_SUPPRESS:
                continue

            if term in CAPITALIZATION_MAP:
                cleaned_term = CAPITALIZATION_MAP[term]
            elif term in ALL_CAPS:
                cleaned_term = term.upper()
            elif term in TERMS_TO_CAPITALIZE:
                cleaned_term = term.capitalize()
            else:
                cleaned_term = term

            if cleaned_term:
                cleaned_terms.add(cleaned_term)

        extra_terms = (
            set(BARKSIAN_EXTRA_TERMS | entity_names) if entity_names else set(BARKSIAN_EXTRA_TERMS)
        )
        existing_lower = {t.lower() for t in cleaned_terms}
        normalized_extra = _normalize_entity_names(extra_terms, existing_lower)
        result = cleaned_terms.union(normalized_extra)
        suppress_lower = {t.lower() for t in MULTI_WORD_TERMS_TO_SUPPRESS}
        return {t for t in result if t.lower() not in suppress_lower}
