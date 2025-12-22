import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger
from pyuca import Collator
from whoosh.analysis import LowercaseFilter, StopFilter
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
from .whoosh_punct_tokenizer import WordWithPunctTokenizer

COLLATOR = Collator()

# noinspection SpellCheckingInspection
EXTRA_TERMS: set[str] = {
    "Ancient Cathay",
    "Ancient Egyptian",
    "Barnacle Bay",
    "Belgian Prince Leopold",
    "Benzine Banzoony",
    "Blistering Bullets",
    "Blue Danube",
    "Blue Danube Waltz",
    "B.P.F.B",
    "Brahms Concerto",
    "Brown Derby",
    "Bullet Pizen At Rustlers' Gallows",
    "Bungling Bros Circus",
    "Carnage on the Cimarron",
    "Chisel McSue",
    "Casa del Hoosier Motel",
    "cat-o'-nine-tails",
    "Columbia River",
    "Cornpone Gables",
    "Cotton Queen",
    "Daredevil Daly",
    "Darkest Africa",
    "Dayton Street",
    "Diamond Dick",
    "Don Gaspar",
    "Don Porko de Lardo",
    "Dr. U. Qwik",
    "Porko de Lardo",
    "El Dorado",
    "Francisco de Ulloa",
    "Ghost of the Gunnison",
    "Fagin's Fangs",
    "Gore in the Gully",
    "Gory Gap",
    "Gneezle Gnob",
    "Gunsmoke Gulch",
    "Gunfire on the Rio",
    "Hag's Fang Cliff",
    "Heston Froster",
    "Horseshoe Hogg",
    "Jim Dandy",
    "John the Junkman",
    "Jughead Jones",
    "Law of the Roaring Winchesters",
    "Lobster Newberg",
    "Lower California",
    "Manana N. de Patio",
    "North America",
    "Olaf the Blue",
    "Powerburns on the Powderhorn",
    "Prof. Batty",
    "Quackly Hall",
    "Queen of the Kangaroos",
    "Queen of Seiprah",
    "Queen Bess",
    "Queen Mary",
    "Queen Veronica",
    "Queen Victoria",
    "Ramona Pageant Bowl",
    "Ramrod Ransom",
    "River Belle",
    "Rodney McHowl",
    "Sagebrush Savage",
    "San Antone",
    "San Diego",
    "San Joaquin Valley",
    "Snarling Rocks Bay",
    "Squeezem, Fleecem, Skinem, and Skip",
    "Sutter's Fort",
    "Trigger Trueshot",
    "Unca' Donald",
    "Uncle Donald",
    "Unca' Scrooge",
    "Uncle Scrooge",
    "Upper Whambesi",
    "Wild Bill Carson",
    "Wonderhead Son of Ticka",
    "Worry Room",
}

# noinspection SpellCheckingInspection
NAMES: set[str] = {
    "adam",
    "adam's",
    "abie",
    "abie's",
    "aeetes",
    "agavik",
    "agnes",
    "alexander",
    "ali",
    "aquapodicus",
    "arabic",
    "ares",
    "arky",
    "argus",
    "ariadne",
    "astorbilt",
    "atlas",
    "autry",
    "aztec",
    "azure",
    "b",
    "b-36",
    "backdore",
    "balonio",
    "banzoony",
    "barks",
    "barnaby",
    "barnowl",
    "barrymore",
    "bassofoglio",
    "batavia",
    "beakoff",
    "bernard",
    "bernards",
    "bess",
    "bessie",
    "betlah",
    "betsy",
    "biceppa",
    "blacksnake",
    "blacksnake's",
    "blitzen",
    "blowsoutski",
    "bobbie",
    "bolivar",
    "booneheads",
    "bornworthy",
    "brad",
    "brahms",
    "brigidita",
    "bumblehead",
    "bumrisk",
    "buenaventura",
    "caesar",
    "caledonian",
    "cantaloupa",
    "capitol",
    "carson",
    "casaba",
    "casey",
    "castoria",
    "charlemagne",
    "charlie",
    "chatterbeak",
    "christmas",
    "christmastime",
    "clabberhead",
    "clarabelle",
    "claus",
    "clipski",
    "colchis",
    "columbus",
    "comanche",
    "constanza",
    "cortez",
    "crabifolius",
    "craig",
    "creole",
    "crustaceous",
    "cuthbert",
    "cyril",
    "daisy",
    "daltons",
    "daly",
    "daniel",
    "dante",
    "davey",
    "dawson",
    "dean",
    "delilah",
    "deltoid",
    "dewey",
    "diana",
    "dick",
    "dickens",
    "diego",
    "donald",
    "donaldo",
    "donner",
    "donny",
    "dorotea",
    "duck",
    "ducko",
    "edgerton",
    "eiprah",
    "eisseb",
    "edison",
    "egbert",
    "elena",
    "eski",
    "eskimo",
    "eskimos",
    "esmeralda",
    "ezry",
    "fernando",
    "froster",
    "gaspar",
    "gaston",
    "gimleteye",
    "gladstone",
    "gnossy",
    "gnostradamus",
    "gyp",
    "gyro",
    "hamilton",
    "harry",
    "heezoutski",
    "heston",
    "hogg",
    "hoppity",
    "horace",
    "huey",
    "i'm",
    "ignacio",
    "ila",
    "jackie",
    "jeebs",
    "jim",
    "jiminy",
    "jingo",
    "joe",
    "joes",
    "joey",
    "john",
    "jonah",
    "jones",
    "jonesie",
    "jonesy",
    "josie",
    "josh",
    "juanita",
    "louie",
    "mack",
    "manana",
    "ma\u00f1ana",
    "manco",
    "marconi",
    "margarita",
    "maria",
    "marmaduke",
    "mallard",
    "mattressface",
    "mike",
    "mustang",
    "mustapha",
    "nacy's",
    "orb",
    "pablo",
    "paganini",
    "panchita",
    "panchita's",
    "pattie",
    "pattie's",
    "petrolio",
    "petruccio",
    "poochley",
    "poochley's",
    "pulpheart",
    "putzoutski",
    "quacko",
    "quagmire",
    "queen",
    "qwik",
    "ramjckwckwizc",
    "remington",
    "ramona",
    "raleigh",
    "raleigh's",
    "rimfire",
    "rodney",
    "rolando",
    "rolando's",
    "sairy",
    "santa",
    "scarpuss",
    "scrooge",
    "senga",
    "sepulveda",
    "si",
    "socrapossi",
    "stumpalong",
    "swelldorf",
    "tagalong",
    "theodore",
    "throckmorton",
    "tina",
    "tombsbury",
    "trueshot",
    "tupec",
    "vaudeville",
    "vaselino",
    "verdugo",
    "veronica",
    "walter",
}

# noinspection SpellCheckingInspection
NAME_MAP: dict[str, str] = {
    "almostus": "Almostus Extinctus",
    "absent-": "absent-minded",
    "extinctus": "Almostus Extinctus",
    "extinctuses": "Almostus Extinctuses",
    "antone": "San Antone",
    "b-197": "B-197 X-NG",
    "b.b": "B.B",
    "x-ng": "B-197 X-NG",
    "b-boys": "B-Boys",
    "bio": "bio-physical",
    "casaba": "Casaba Cantaloupa",
    "chillspine": "Chillspine Buoy",
    "codfeesh": "Codfeesh Cove",
    "codfish": "Codfish Cove",
    "coney": "Coney Island",
    "cornelius": "Cornelius McCobb",
    "costa": "Costa Rica",
    "creole": "Creole Belle",
    "ddt": "DDT",
    "debbies": "Junior Sub-teen-age Debbies Club",
    "dick": "Diamond Dick",
    "dog-in-the-": "dog-in-the- manger",
    "donna": "Donna Duck",
    "extroverten": "extroverten-tualities",
    "tualities": "extroverten-tualities",
    "gnatbugg": "Gnatbugg-Mothley",
    "l.t.a.b": "L.T.A.B",
    "lemon-": "lemon-ade",
    "master-": "master- piece",
    "mc": "Mc-Who",
    "mothley": "Gnatbugg-Mothley",
    "mammalarius": "Mammalarius Aquapodicus",
    "mcarchives": "McArchives",
    "mcchicken": "McChicken",
    "mccobb": "McCobb",
    "mccornburger": "McCornburger",
    "mccoy": "McCoy",
    "mccrow": "McCrow",
    "mcdome": "McDome",
    "mcduck": "McDuck",
    "mcduck's": "McDuck's",
    "mcducks": "McDucks",
    "mceagle": "McEagle",
    "mceye": "McEye",
    "mcfiendy": "McFiendy",
    "mcgillicuddy": "McGillicuddy",
    "mchawk": "McHawk",
    "mchowl": "McHowl",
    "mcknucks": "McKnucks",
    "mcmooch": "McMooch",
    "mcowl": "McOwl",
    "mcquirt": "McQuirt",
    "mcsixgun": "McSixgun",
    "mcterrier": "McTerrier",
    "mcviper": "McViper",
    "mcyard": "McYard",
    "mcsue": "Chisel McSue",
    "phoebus": "Phoebus Philea",
    "philea": "Phoebus Philea",
    "conippus": "Pippus Conippus",
    "pippus": "Pippus Conippus",
    "marco": "Marco Polo",
    "polo": "Marco Polo",
    "orville": "Orville Orb",
    "pulpheart": "Pulpheart Clabberhead",
    "rogers": "Autry Mack Brown Rogers",
    "t.n.t": "T.N.T",
    "triple-x": "Triple-X",
    "vaquero": "Rolando the Vaquero",
    "swelldorf": "Swelldorf-Castoria",
}

# noinspection SpellCheckingInspection
PLACE_RELATED_WORDS: set[str] = {
    "abilene",
    "africa",
    "african",
    "alaskan",
    "america",
    "america's",
    "american",
    "americano",
    "americanos",
    "americans",
    "andes",
    "andean",
    "angeles",
    "antarctica",
    "arctic",
    "asia",
    "assyrian",
    "atlantic",
    "atlantis",
    "awfultonians",
    "babylon",
    "barcelona",
    "belgian",
    "bermuda",
    "borneo",
    "boston",
    "brazilian",
    "british",
    "brooklyn",
    "bumpanian",
    "bumpanians",
    "burbank",
    "burgeria",
    "calcutta",
    "calisota",
    "capetown",
    "carthage",
    "casablanca",
    "catalina",
    "cathay",
    "chaldee",
    "chicago",
    "chilcoot",
    "chiliburgeria",
    "chinese",
    "cibola",
    "cibolans",
    "crete",
    "cretan",
    "cuzco",
    "damascus",
    "danube",
    "dayton",
    "dixie",
    "dixieland",
    "duckburg",
    "egyptian",
    "england",
    "english",
    "europe",
    "granada",
    "greenland",
    "hollywood",
    "howduyustan",
    "jupiter",
    "klondike",
    "los",
    "marseille",
    "mayan",
    "monterey",
    "newfoundland",
    "pacific",
    "persia",
    "pickleburg",
    "pumpkinburg",
    "quackville",
    "sacramento",
    "scotland",
    "scroogeville",
    "seville",
    "spanish",
    "tokyo",
    "tripoli",
    "tropicania",
    "tropics",
    "valencia",
    "venus",
    "vine",
    "whambesi",
}

US_STATES: set[str] = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "district of columbia",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}

COUNTRIES: set[str] = {
    "afghanistan",
    "albania",
    "algeria",
    "andorra",
    "angola",
    "antigua & deps",
    "argentina",
    "armenia",
    "australia",
    "austria",
    "azerbaijan",
    "bahamas",
    "bahrain",
    "bangladesh",
    "barbados",
    "belarus",
    "belgium",
    "belize",
    "benin",
    "bhutan",
    "bolivia",
    "bosnia herzegovina",
    "botswana",
    "brazil",
    "brunei",
    "bulgaria",
    "burkina",
    "burma",
    "burundi",
    "cambodia",
    "cameroon",
    "canada",
    "cape verde",
    "central african rep",
    "chad",
    "chile",
    "china",
    "colombia",
    "comoros",
    "congo",
    "congo {democratic rep}",
    "costa rica",
    "croatia",
    "cuba",
    "cyprus",
    "czech republic",
    "denmark",
    "djibouti",
    "dominica",
    "dominican republic",
    "east timor",
    "ecuador",
    "egypt",
    "el salvador",
    "equatorial guinea",
    "eritrea",
    "estonia",
    "ethiopia",
    "fiji",
    "finland",
    "france",
    "gabon",
    "gambia",
    "georgia",
    "germany",
    "ghana",
    "greece",
    "grenada",
    "guatemala",
    "guinea",
    "guinea-bissau",
    "guyana",
    "haiti",
    "honduras",
    "hungary",
    "iceland",
    "india",
    "indonesia",
    "iran",
    "iraq",
    "ireland",
    "israel",
    "italy",
    "ivory coast",
    "jamaica",
    "japan",
    "jordan",
    "kazakhstan",
    "kenya",
    "kiribati",
    "korea north",
    "korea south",
    "kosovo",
    "kuwait",
    "kyrgyzstan",
    "laos",
    "latvia",
    "lebanon",
    "lesotho",
    "liberia",
    "libya",
    "liechtenstein",
    "lithuania",
    "luxembourg",
    "macedonia",
    "madagascar",
    "malawi",
    "malaysia",
    "maldives",
    "mali",
    "malta",
    "marshall islands",
    "mauritania",
    "mauritius",
    "mexico",
    "micronesia",
    "moldova",
    "monaco",
    "mongolia",
    "montenegro",
    "morocco",
    "mozambique",
    "myanmar",
    "namibia",
    "nauru",
    "nepal",
    "netherlands",
    "new zealand",
    "nicaragua",
    "niger",
    "nigeria",
    "norway",
    "oman",
    "pakistan",
    "palau",
    "panama",
    "papua new guinea",
    "paraguay",
    "peru",
    "philippines",
    "poland",
    "portugal",
    "qatar",
    "romania",
    "russian federation",
    "rwanda",
    "st kitts & nevis",
    "st lucia",
    "saint vincent & the grenadines",
    "samoa",
    "san marino",
    "sao tome & principe",
    "saudi arabia",
    "senegal",
    "serbia",
    "seychelles",
    "sierra leone",
    "singapore",
    "slovakia",
    "slovenia",
    "solomon islands",
    "somalia",
    "south africa",
    "south sudan",
    "spain",
    "sri lanka",
    "sudan",
    "suriname",
    "swaziland",
    "sweden",
    "switzerland",
    "syria",
    "taiwan",
    "tajikistan",
    "tanzania",
    "thailand",
    "togo",
    "tonga",
    "trinidad & tobago",
    "tunisia",
    "turkey",
    "turkmenistan",
    "tuvalu",
    "uganda",
    "ukraine",
    "united arab emirates",
    "united kingdom",
    "united states",
    "uruguay",
    "uzbekistan",
    "vanuatu",
    "vatican city",
    "venezuela",
    "vietnam",
    "yemen",
    "zambia",
    "zimbabwe",
}

SPECIAL_WORDS: set[str] = NAMES.union(PLACE_RELATED_WORDS).union(US_STATES).union(COUNTRIES)

REMOVE_WORDS: set[str] = {
    "_",
    # "s",
}

SUB_ALPHA_SPLIT_SIZE = 56


@dataclass
class TitleInfo:
    fanta_vol: int = 0
    pages: list[tuple[str, str, str]] = field(default_factory=list)


type TitleDict = dict[str, TitleInfo]


class SearchEngine:
    def __init__(self, index_dir: Path) -> None:
        self._index = open_dir(index_dir)

        self._unstemmed_terms_path = self._index.storage.folder / "unstemmed-terms.json"
        self._cleaned_unstemmed_terms_path = (
            self._index.storage.folder / "cleaned-unstemmed-terms.json"
        )
        self._cleaned_alpha_split_unstemmed_terms_path = (
            self._index.storage.folder / "cleaned-alpha-split-unstemmed-terms.json"
        )

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

    def get_cleaned_unstemmed_terms(self) -> list[str]:
        return json.loads(self._cleaned_unstemmed_terms_path.read_text())

    def get_cleaned_alpha_split_unstemmed_terms(self) -> dict[str, dict[str, list[str]]]:
        return json.loads(self._cleaned_alpha_split_unstemmed_terms_path.read_text())

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
            content=TEXT(stored=True, lang="en"),
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
        with self._cleaned_alpha_split_unstemmed_terms_path.open("w") as f:
            json.dump(self._get_alpha_split_unstemmed_terms(cleaned_unstemmed_terms), f, indent=4)

    @staticmethod
    def _get_cleaned_unstemmed_terms(unstemmed_terms: list[str]) -> set[str]:
        cleaned_unstemmed_terms = set()
        for term in unstemmed_terms:
            if term in REMOVE_WORDS:
                continue

            if term in NAME_MAP:
                cleaned_term = NAME_MAP[term]
            elif term in SPECIAL_WORDS:
                cleaned_term = term.capitalize()
            elif term.startswith(("-", "--")):
                cleaned_term = term.lstrip("-")
            elif term.endswith(("-", "--")):
                cleaned_term = term.rstrip("-")
            else:
                cleaned_term = term

            if cleaned_term:
                cleaned_unstemmed_terms.add(cleaned_term)

        return cleaned_unstemmed_terms.union(EXTRA_TERMS)

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

    def _get_alpha_split_unstemmed_terms(
        self, cleaned_unstemmed_terms: list[str]
    ) -> dict[str, dict[str, list[str]]]:
        alpha_dict = {}
        first_letter_list = []
        current_first_letter_group = "0"
        for term in cleaned_unstemmed_terms:
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
                alpha_dict[current_first_letter_group] = self._get_sub_alpha_split_unstemmed_terms(
                    first_letter_list
                )
                first_letter_list = []
                current_first_letter_group = first_letter

            first_letter_list.append(term)

        if first_letter_list:
            alpha_dict[current_first_letter_group] = self._get_sub_alpha_split_unstemmed_terms(
                first_letter_list
            )

        return self._get_similar_size_alpha_groups(alpha_dict)

    @staticmethod
    def _get_sub_alpha_split_unstemmed_terms(
        alpha_unstemmed_terms: list[str],
    ) -> dict[str, list[str]]:
        if not alpha_unstemmed_terms:
            return {}

        prefix_len = 1 if "0" <= alpha_unstemmed_terms[0][0] <= "9" else 2
        current_prefix = alpha_unstemmed_terms[0][:prefix_len].lower()

        sub_alpha_unstemmed_dict = {current_prefix: []}
        for term in alpha_unstemmed_terms:
            if current_prefix != term[:prefix_len].lower():
                current_prefix = term[:prefix_len].lower()
                sub_alpha_unstemmed_dict[current_prefix] = []
            sub_alpha_unstemmed_dict[current_prefix].append(term)

        return sub_alpha_unstemmed_dict

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
