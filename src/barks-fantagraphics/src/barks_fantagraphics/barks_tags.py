# ruff: noqa: D205

from __future__ import annotations

from enum import Enum

from .barks_titles import Titles


class Tags(Enum):
    BARKS_FAVOURITES = "Barks' Picks"
    EVERY_GEEK_FAVOURITES = "everygeek.net"
    PERSONAL_FAVOURITES = "My Picks"
    PETER_SCHILLING_FAVOURITES = "Peter Schilling"
    WIKI_NOTABLE_STORIES = "Wiki Notable Stories"
    CLASSICS = "The Classics"

    CENSORED_STORIES_BUT_FIXED = "censored but fixed stories"

    ALGERIA = "Algeria"
    ANDES = "Andes"
    ANTARCTICA = "Antarctica"
    ARABIAN_PENINSULA = "Arabian Peninsula"
    ARCTIC_OCEAN = "Arctic Ocean"
    ATLANTIS = "Atlantis"
    AUSTRALIA = "Australia"
    BARNACLE_BAY = "Barnacle Bay"
    CENTRAL_AFRICA = "Central Africa"
    CHINA = "China"
    CONGO = "Congo"
    DUCKBURG = "Duckburg"
    EGYPT = "Egypt"
    FRANCE = "France"
    GERMANY = "Germany"
    GREECE = "Greece"
    HIMALAYAS = "Himalayas"
    INDIA = "India"
    INDIAN_OCEAN = "Indian Ocean"
    INDO_CHINA = "Indo-China"
    IRAQ = "Iraq"
    ITALY = "Italy"
    LIBYA = "Libya"
    MALI = "Mali"
    MONGOLIA = "Mongolia"
    MOROCCO = "Morocco"
    NIAGARA_FALLS = "Niagara Falls"
    NORWAY = "Norway"
    OLD_DEMON_TOOTH = "Old Demon Tooth"
    PAKISTAN = "Pakistan"
    PERSIA = "Persia"
    PLAIN_AWFUL = "Plain Awful"
    RUSSIA = "Russia"
    SCOTLAND = "Scotland"
    SOUTH_AFRICA = "South Africa"
    SPAIN = "Spain"
    SUDAN = "Sudan"
    SWEDEN = "Sweden"
    SWITZERLAND = "Switzerland"
    SYDNEY = "Sydney"
    SYRIA = "Syria"
    TANGANYIKA = "Tanganyika"

    AIRPLANE = "airplane"
    CAMERA = "camera"
    CIGARETTES = "cigarettes"
    FIRE = "fire"
    SQUARE_EGGS = "square eggs"
    WEEMITE = "weemite"

    CHRISTMAS_STORIES = "christmas stories"
    HYPNOSIS = "hypnosis"
    MAGIC = "magic"
    PHOTOGRAPHY = "photography"
    NEW_VERSIONS = "new versions of old stories"

    AZURE_BLUE = "Azure Blue"
    ARGUS_MCFIENDY = "Argus McFiendy"
    BEAGLE_BOYS = "The Beagle Boys"
    BENZENE_BANZOONY = "Benzene Banzoony"
    BOMBIE_THE_ZOMBIE = "Bombie the Zombie"
    CARVER_BEAKOFF = "Doctor Carver Beakoff"
    CHISEL_MC_SUE = "Chisel McSue"
    CORNELIUS_MC_COBB = "Cornelius McCobb"
    DAISY = "Daisy Duck"
    EL_DORADO = "El Dorado"
    FERMIES = "Fermies"
    FLINTHEART_GLOMGOLD = "Flintheart Glomgold"
    FOOLA_ZOOLA = "Foola Zoola"
    GENERAL_SNOZZIE = "General Snozzie"
    GLADSTONE_GANDER = "Gladstone Gander"
    GYRO_GEARLOOSE = "Gyro Gearloose"
    GYRO_NOT_IN_GG = "Gyro not in GG series"
    HASSAN_BEN_JAILD = "Hassan Ben Jaild"
    HERBERT = "Herbert"
    JUNIOR_WOODCHUCKS = "Junior Woodchucks"
    MAGICA_DE_SPELL = "Magica de Spell"
    MR_MC_SWINE = "Mr. McSwine"
    NEIGHBOR_JONES = "Neighbor Jones"
    P_J_MC_BRINE = "P.J.McBrine"
    PORKMAN_DE_LARDO = "Porkman de Lardo"
    SCROOGE_NOT_IN_US = "Uncle Scrooge not in US series"
    SOAPY_SLICK = "Soapy Slick"
    TERRIES = "Terries"


BARKS_TAG_EXTRA_ALIASES = {
    "south pole": Tags.ANTARCTICA,
    "arabia": Tags.ARABIAN_PENINSULA,
    "arctic": Tags.ARCTIC_OCEAN,
    "barnacle": Tags.BARNACLE_BAY,
    "niagara": Tags.NIAGARA_FALLS,
    "argus": Tags.ARGUS_MCFIENDY,
    "mcfiendy": Tags.ARGUS_MCFIENDY,
    "azure": Tags.AZURE_BLUE,
    "the beagle boys": Tags.BEAGLE_BOYS,
    "beagles": Tags.BEAGLE_BOYS,
    "benzene": Tags.BENZENE_BANZOONY,
    "banzoony": Tags.BENZENE_BANZOONY,
    "bombie": Tags.BOMBIE_THE_ZOMBIE,
    "zombie": Tags.BOMBIE_THE_ZOMBIE,
    "carver beakoff": Tags.CARVER_BEAKOFF,
    "beakoff": Tags.CARVER_BEAKOFF,
    "carver": Tags.CARVER_BEAKOFF,
    "chisel": Tags.CHISEL_MC_SUE,
    "mcsue": Tags.CHISEL_MC_SUE,
    "cornelius": Tags.CORNELIUS_MC_COBB,
    "mccobb": Tags.CORNELIUS_MC_COBB,
    "daisy": Tags.DAISY,
    "el": Tags.EL_DORADO,
    "dorado": Tags.EL_DORADO,
    "foola": Tags.FOOLA_ZOOLA,
    "zoola": Tags.FOOLA_ZOOLA,
    "flintheart": Tags.FLINTHEART_GLOMGOLD,
    "glomgold": Tags.FLINTHEART_GLOMGOLD,
    "snozzie": Tags.GENERAL_SNOZZIE,
    "gladstone": Tags.GLADSTONE_GANDER,
    "gyro": Tags.GYRO_GEARLOOSE,
    "gearloose": Tags.GYRO_GEARLOOSE,
    "woodchucks": Tags.JUNIOR_WOODCHUCKS,
    "magica": Tags.MAGICA_DE_SPELL,
    "spell": Tags.MAGICA_DE_SPELL,
    "mcswine": Tags.MR_MC_SWINE,
    "mrmcswine": Tags.MR_MC_SWINE,
    "jones": Tags.NEIGHBOR_JONES,
    "demon": Tags.OLD_DEMON_TOOTH,
    "mount demon tooth": Tags.OLD_DEMON_TOOTH,
    "old demon tooth": Tags.OLD_DEMON_TOOTH,
    "pjmcbrine": Tags.P_J_MC_BRINE,
    "mcbrine": Tags.P_J_MC_BRINE,
    "uncle": Tags.SCROOGE_NOT_IN_US,
    "scrooge": Tags.SCROOGE_NOT_IN_US,
}

BARKS_TAG_ALIASES = {str(t.value).lower(): t for t in Tags} | BARKS_TAG_EXTRA_ALIASES


class TagCategories(Enum):
    CHARACTERS = "Characters"
    FAVOURITES = "Favourites"
    PLACES = "Places"
    THEMES = "Themes"
    THINGS = "Things"


class TagGroups(Enum):
    AFRICA = "Africa"
    ASIA = "Asia"
    AUSTRALIA = "Australia"
    EUROPE = "Europe"
    NORTH_AMERICA = "North America"
    OTHER = "Other"
    SOUTH_AMERICA = "South America"
    DRUGS = "drugs"
    PRIMARY_CHARACTERS = "Primary Characters"
    SECONDARY_CHARACTERS = "Secondary Characters"
    ONE_OFF_CHARACTERS = "One-off Characters"
    PIG_VILLAINS = "Pig Villains"


BARKS_TAG_GROUPS_ALIASES = {str(t.value).lower(): t for t in TagGroups}


BARKS_TAG_CATEGORIES_DICT = {cat.value: cat for cat in TagCategories}

BARKS_TAG_CATEGORIES = {
    TagCategories.FAVOURITES: [
        Tags.BARKS_FAVOURITES,
        Tags.EVERY_GEEK_FAVOURITES,
        Tags.PERSONAL_FAVOURITES,
        Tags.PETER_SCHILLING_FAVOURITES,
        Tags.WIKI_NOTABLE_STORIES,
        Tags.CLASSICS,
    ],
    TagCategories.THINGS: [
        Tags.AIRPLANE,
        Tags.CAMERA,
        Tags.CIGARETTES,
        Tags.FIRE,
        Tags.SQUARE_EGGS,
        Tags.WEEMITE,
    ],
    TagCategories.THEMES: [
        Tags.CENSORED_STORIES_BUT_FIXED,
        Tags.CHRISTMAS_STORIES,
        TagGroups.DRUGS,
        Tags.HYPNOSIS,
        Tags.MAGIC,
        Tags.PHOTOGRAPHY,
        Tags.NEW_VERSIONS,
    ],
    TagCategories.CHARACTERS: [
        TagGroups.PRIMARY_CHARACTERS,
        TagGroups.SECONDARY_CHARACTERS,
        TagGroups.ONE_OFF_CHARACTERS,
    ],
    TagCategories.PLACES: [
        TagGroups.AFRICA,
        Tags.ALGERIA,
        Tags.ANDES,
        Tags.ANTARCTICA,
        Tags.ARABIAN_PENINSULA,
        Tags.ARCTIC_OCEAN,
        Tags.ATLANTIS,
        TagGroups.ASIA,
        # Tags.AUSTRALIA,
        TagGroups.AUSTRALIA,
        Tags.BARNACLE_BAY,
        Tags.CENTRAL_AFRICA,
        Tags.CHINA,
        Tags.CONGO,
        Tags.DUCKBURG,
        Tags.EGYPT,
        TagGroups.EUROPE,
        Tags.FRANCE,
        Tags.GERMANY,
        Tags.GREECE,
        Tags.HIMALAYAS,
        Tags.INDIA,
        Tags.INDIAN_OCEAN,
        Tags.INDO_CHINA,
        Tags.IRAQ,
        Tags.ITALY,
        Tags.LIBYA,
        Tags.MALI,
        Tags.MONGOLIA,
        Tags.MOROCCO,
        Tags.NIAGARA_FALLS,
        TagGroups.NORTH_AMERICA,
        Tags.NORWAY,
        Tags.OLD_DEMON_TOOTH,
        Tags.PAKISTAN,
        Tags.PERSIA,
        Tags.PLAIN_AWFUL,
        Tags.RUSSIA,
        Tags.SCOTLAND,
        Tags.SOUTH_AFRICA,
        TagGroups.SOUTH_AMERICA,
        Tags.SPAIN,
        Tags.SUDAN,
        Tags.SWEDEN,
        Tags.SWITZERLAND,
        Tags.SYDNEY,
        Tags.SYRIA,
        Tags.TANGANYIKA,
    ],
}

BARKS_TAG_GROUPS = {
    TagGroups.AFRICA: [
        Tags.ALGERIA,
        Tags.ARABIAN_PENINSULA,
        Tags.CENTRAL_AFRICA,
        Tags.CONGO,
        Tags.EGYPT,
        Tags.LIBYA,
        Tags.MALI,
        Tags.MOROCCO,
        Tags.SOUTH_AFRICA,
        Tags.SUDAN,
        Tags.TANGANYIKA,
    ],
    TagGroups.ASIA: [
        Tags.CHINA,
        Tags.INDO_CHINA,
        Tags.HIMALAYAS,
        Tags.INDIA,
        Tags.IRAQ,
        Tags.MONGOLIA,
        Tags.PAKISTAN,
        Tags.PERSIA,
    ],
    TagGroups.AUSTRALIA: [
        Tags.AUSTRALIA,
        Tags.SYDNEY,
    ],
    TagGroups.EUROPE: [
        Tags.SWITZERLAND,
        Tags.SWEDEN,
        Tags.ITALY,
        Tags.FRANCE,
        Tags.GERMANY,
        Tags.SCOTLAND,
        Tags.SPAIN,
        Tags.RUSSIA,
        Tags.GREECE,
        Tags.NORWAY,
    ],
    TagGroups.NORTH_AMERICA: [],
    TagGroups.OTHER: [
        Tags.ANTARCTICA,
        Tags.ARCTIC_OCEAN,
        Tags.ATLANTIS,
        Tags.BARNACLE_BAY,
        Tags.DUCKBURG,
        Tags.OLD_DEMON_TOOTH,
    ],
    TagGroups.SOUTH_AMERICA: [
        Tags.ANDES,
        Tags.PLAIN_AWFUL,
    ],
    TagGroups.DRUGS: [
        Tags.CIGARETTES,
    ],
    TagGroups.PRIMARY_CHARACTERS: [
        Tags.BEAGLE_BOYS,
        Tags.DAISY,
        Tags.GLADSTONE_GANDER,
        Tags.GYRO_GEARLOOSE,
        Tags.GYRO_NOT_IN_GG,
        Tags.JUNIOR_WOODCHUCKS,
        Tags.SCROOGE_NOT_IN_US,
    ],
    TagGroups.SECONDARY_CHARACTERS: [
        Tags.FLINTHEART_GLOMGOLD,
        Tags.GENERAL_SNOZZIE,
        Tags.HERBERT,
        Tags.MAGICA_DE_SPELL,
        Tags.NEIGHBOR_JONES,
        TagGroups.PIG_VILLAINS,
    ],
    TagGroups.ONE_OFF_CHARACTERS: [
        Tags.ARGUS_MCFIENDY,
        Tags.AZURE_BLUE,
        Tags.BENZENE_BANZOONY,
        Tags.BOMBIE_THE_ZOMBIE,
        Tags.CARVER_BEAKOFF,
        Tags.CHISEL_MC_SUE,
        Tags.CORNELIUS_MC_COBB,
        Tags.EL_DORADO,
        Tags.FERMIES,
        Tags.FOOLA_ZOOLA,
        Tags.TERRIES,
    ],
    TagGroups.PIG_VILLAINS: [
        Tags.HASSAN_BEN_JAILD,
        Tags.MR_MC_SWINE,
        Tags.P_J_MC_BRINE,
        Tags.PORKMAN_DE_LARDO,
        Tags.SOAPY_SLICK,
    ],
}

BARKS_TAGGED_TITLES: dict[Tags, list[Titles]] = {
    # Favourites
    Tags.CLASSICS: [
        # As chosen by GLK
        Titles.LOST_IN_THE_ANDES,
        Titles.GHOST_OF_THE_GROTTO_THE,
        Titles.OLD_CASTLES_SECRET_THE,
        Titles.SHERIFF_OF_BULLET_VALLEY,
        Titles.LAND_OF_THE_TOTEM_POLES,
        Titles.IN_ANCIENT_PERSIA,
        Titles.VACATION_TIME,
        Titles.IN_OLD_CALIFORNIA,
        Titles.GILDED_MAN_THE,
        Titles.GOLDEN_HELMET_THE,
        Titles.ONLY_A_POOR_OLD_MAN,
        Titles.BACK_TO_THE_KLONDIKE,
        Titles.MASTER_RAINMAKER_THE,
        Titles.FINANCIAL_FABLE_A,
        Titles.HYPNO_GUN_THE,
        Titles.BEE_BUMBLES,
    ],
    Tags.BARKS_FAVOURITES: [
        # This list of Barks' favorites is from https://www.cbarks.dk/thefavourites.htm
        Titles.LOST_IN_THE_ANDES,
        Titles.IN_OLD_CALIFORNIA,
        Titles.RIP_VAN_DONALD,
        Titles.FINANCIAL_FABLE_A,
        Titles.OMELET,
        Titles.HORSERADISH_STORY_THE,
        Titles.SECRET_OF_ATLANTIS_THE,
        Titles.LAND_OF_THE_PYGMY_INDIANS,
        Titles.ISLAND_IN_THE_SKY,
        Titles.MICRO_DUCKS_FROM_OUTER_SPACE,
        Titles.GHOST_OF_THE_GROTTO_THE,
        Titles.LAND_OF_THE_TOTEM_POLES,
        Titles.IN_ANCIENT_PERSIA,
        Titles.GOLDEN_HELMET_THE,
        Titles.VACATION_TIME,
    ],
    Tags.PETER_SCHILLING_FAVOURITES: [
        # This list of the Barks stories covered in Peter Schilling's book:
        # "Carl Barks' Duck - Average American"
        Titles.MAHARAJAH_DONALD,
        Titles.LOST_IN_THE_ANDES,
        Titles.LUCK_OF_THE_NORTH,
        Titles.GILDED_MAN_THE,
        Titles.MAGIC_HOURGLASS_THE,
        Titles.GOLDEN_HELMET_THE,
        Titles.LAND_OF_THE_TOTEM_POLES,
        Titles.NO_SUCH_VARMINT,
        Titles.MASTER_RAINMAKER_THE,
        Titles.SMOKE_WRITER_IN_THE_SKY,
        Titles.MASTER_GLASSER_THE,
        Titles.SPARE_THAT_HAIR,
        Titles.VACATION_TIME,
    ],
    Tags.WIKI_NOTABLE_STORIES: [
        Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
        Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
        Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
        Titles.OLD_CASTLES_SECRET_THE,
        Titles.SHERIFF_OF_BULLET_VALLEY,
        Titles.LOST_IN_THE_ANDES,
        Titles.VACATION_TIME,
        Titles.FINANCIAL_FABLE_A,
        Titles.IN_OLD_CALIFORNIA,
        Titles.CHRISTMAS_FOR_SHACKTOWN_A,
        Titles.ONLY_A_POOR_OLD_MAN,
        Titles.FLIP_DECISION,
        Titles.GOLDEN_HELMET_THE,
        Titles.BACK_TO_THE_KLONDIKE,
        Titles.TRALLA_LA,
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE,
        Titles.GOLDEN_FLEECING_THE,
        Titles.LAND_BENEATH_THE_GROUND,
        Titles.MONEY_WELL_THE,
        Titles.GOLDEN_RIVER_THE,
        Titles.ISLAND_IN_THE_SKY,
        Titles.NORTH_OF_THE_YUKON,
    ],
    Tags.EVERY_GEEK_FAVOURITES: [
        # This list from https://everygeek.net/carl-barks-comics-ducktales-fan
        Titles.BACK_TO_THE_KLONDIKE,
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE,
        Titles.GOLDEN_FLEECING_THE,
        Titles.VACATION_TIME,
        Titles.GOLDEN_HELMET_THE,
        Titles.LUCK_OF_THE_NORTH,
        Titles.STATUESQUE_SPENDTHRIFTS,
    ],
    # Censorship
    Tags.CENSORED_STORIES_BUT_FIXED: [
        Titles.BACK_TO_THE_KLONDIKE,
        Titles.FROZEN_GOLD,
        Titles.LAND_BENEATH_THE_GROUND,
        Titles.LOST_IN_THE_ANDES,
        Titles.GOOD_DEEDS,
        Titles.SILENT_NIGHT,
        Titles.SWIMMING_SWINDLERS,
        Titles.BILL_COLLECTORS_THE,
        Titles.FIREBUG_THE,
        Titles.GOLDEN_CHRISTMAS_TREE_THE,
        Titles.GOLDEN_FLEECING_THE,
        Titles.ICEBOX_ROBBER_THE,
        Titles.LOVELORN_FIREMAN_THE,
        Titles.TERROR_OF_THE_RIVER_THE,
        Titles.TRICK_OR_TREAT,
        Titles.VOODOO_HOODOO,
    ],
    # Real places
    Tags.ALGERIA: [Titles.ROCKET_RACE_AROUND_THE_WORLD],
    Tags.ANDES: [Titles.LOST_IN_THE_ANDES],
    Tags.ANTARCTICA: [Titles.COLD_BARGAIN_A],
    Tags.ARABIAN_PENINSULA: [
        Titles.MINES_OF_KING_SOLOMON_THE,
        Titles.MONEY_CHAMP_THE,
        Titles.PIPELINE_TO_DANGER,
        Titles.CAVE_OF_ALI_BABA,
        Titles.MCDUCK_OF_ARABIA,
    ],
    Tags.ARCTIC_OCEAN: [Titles.LUCK_OF_THE_NORTH],
    Tags.ATLANTIS: [Titles.SECRET_OF_ATLANTIS_THE],
    Tags.AUSTRALIA: [
        Titles.ADVENTURE_DOWN_UNDER,
        Titles.RICHES_RICHES_EVERYWHERE,
        Titles.QUEEN_OF_THE_WILD_DOG_PACK_THE,
    ],
    Tags.CENTRAL_AFRICA: [
        Titles.DARKEST_AFRICA,
        Titles.VOODOO_HOODOO,
        Titles.JUNGLE_HI_JINKS,
        Titles.WISHING_WELL_THE,
        Titles.JUNGLE_BUNGLE,
        Titles.SO_FAR_AND_NO_SAFARI,
    ],
    Tags.CHINA: [Titles.MONEY_CHAMP_THE],
    Tags.CONGO: [Titles.BONGO_ON_THE_CONGO],
    Tags.EGYPT: [Titles.DONALD_DUCK_AND_THE_MUMMYS_RING],
    Tags.FRANCE: [Titles.DANGEROUS_DISGUISE],
    Tags.GERMANY: [Titles.FABULOUS_PHILOSOPHERS_STONE_THE],
    Tags.GREECE: [
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE,
        Titles.GOLDEN_FLEECING_THE,
        Titles.ODDBALL_ODYSSEY,
        Titles.INSTANT_HERCULES,
    ],
    Tags.HIMALAYAS: [
        Titles.TRAIL_OF_THE_UNICORN,
        Titles.TRALLA_LA,
        Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE,
    ],
    Tags.INDIA: [
        Titles.MAHARAJAH_DONALD,
        Titles.TRAIL_OF_THE_UNICORN,
        Titles.MINES_OF_KING_SOLOMON_THE,
        Titles.BILLION_DOLLAR_SAFARI_THE,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
    ],
    Tags.INDIAN_OCEAN: [
        Titles.MANY_FACES_OF_MAGICA_DE_SPELL_THE,
        Titles.DOOM_DIAMOND_THE,
    ],
    Tags.INDO_CHINA: [
        Titles.CITY_OF_GOLDEN_ROOFS,
        Titles.MCDUCK_OF_ARABIA,
        Titles.TREASURE_OF_MARCO_POLO,
        Titles.MONKEY_BUSINESS,
    ],
    Tags.IRAQ: [
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE,
        Titles.RUG_RIDERS_IN_THE_SKY,
    ],
    Tags.ITALY: [
        Titles.FABULOUS_PHILOSOPHERS_STONE_THE,
        Titles.MIDAS_TOUCH_THE,
        Titles.UNSAFE_SAFE_THE,
        Titles.ODDBALL_ODYSSEY,
        Titles.FOR_OLD_DIMES_SAKE,
        Titles.MANY_FACES_OF_MAGICA_DE_SPELL_THE,
        Titles.DUCKS_EYE_VIEW_OF_EUROPE_A,
    ],
    Tags.LIBYA: [Titles.ROCKET_RACE_AROUND_THE_WORLD],
    Tags.MALI: [
        Titles.DAY_DUCKBURG_GOT_DYED_THE,
        Titles.CANDY_KID_THE,
    ],
    Tags.MONGOLIA: [Titles.MONEY_CHAMP_THE],
    Tags.MOROCCO: [Titles.MAGIC_HOURGLASS_THE],
    Tags.NIAGARA_FALLS: [Titles.HIGH_WIRE_DAREDEVILS],
    Tags.NORWAY: [Titles.LEMMING_WITH_THE_LOCKET_THE],
    Tags.PAKISTAN: [Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE],
    Tags.PERSIA: [Titles.IN_ANCIENT_PERSIA],
    Tags.PLAIN_AWFUL: [Titles.LOST_IN_THE_ANDES],
    Tags.RUSSIA: [Titles.CITY_OF_GOLDEN_ROOFS],
    Tags.SCOTLAND: [
        Titles.OLD_CASTLES_SECRET_THE,
        Titles.HOUND_OF_THE_WHISKERVILLES,
        Titles.INVISIBLE_INTRUDER_THE,
        Titles.MYSTERY_OF_THE_LOCH,
    ],
    Tags.SOUTH_AFRICA: [
        Titles.SECOND_RICHEST_DUCK_THE,
        Titles.SO_FAR_AND_NO_SAFARI,
    ],
    Tags.SPAIN: [
        Titles.DANGEROUS_DISGUISE,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
    ],
    Tags.SUDAN: [Titles.MINES_OF_KING_SOLOMON_THE],
    Tags.SWEDEN: [Titles.MINES_OF_KING_SOLOMON_THE],
    Tags.SWITZERLAND: [Titles.DUCKS_EYE_VIEW_OF_EUROPE_A],
    Tags.SYDNEY: [Titles.ADVENTURE_DOWN_UNDER],
    Tags.SYRIA: [Titles.FABULOUS_PHILOSOPHERS_STONE_THE],
    Tags.TANGANYIKA: [Titles.UNSAFE_SAFE_THE],
    # Not so real
    Tags.BARNACLE_BAY: [Titles.NO_SUCH_VARMINT],
    Tags.DUCKBURG: [
        Titles.HIGH_WIRE_DAREDEVILS,
        Titles.CHRISTMAS_IN_DUCKBURG,
        Titles.TITANIC_ANTS_THE,
        Titles.LAND_BENEATH_THE_GROUND,
        Titles.HIS_HANDY_ANDY,
        Titles.DUCKBURGS_DAY_OF_PERIL,
        Titles.GIANT_ROBOT_ROBBERS_THE,
        Titles.GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE,
        Titles.OLYMPIC_HOPEFUL_THE,
        Titles.DAY_DUCKBURG_GOT_DYED_THE,
        Titles.CODE_OF_DUCKBURG_THE,
        Titles.BLACK_WEDNESDAY,
        Titles.DUCKBURG_PET_PARADE_THE,
    ],
    Tags.OLD_DEMON_TOOTH: [Titles.GOLDEN_CHRISTMAS_TREE_THE, Titles.MONEY_STAIRS_THE],
    # Themes
    Tags.CHRISTMAS_STORIES: [
        Titles.DONALD_DUCKS_BEST_CHRISTMAS,
        Titles.SILENT_NIGHT,
        Titles.SANTAS_STORMY_VISIT,
        Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
        Titles.TOYLAND,
        Titles.GOLDEN_CHRISTMAS_TREE_THE,
        Titles.WINTERTIME_WAGER,
        Titles.NEW_TOYS,
        Titles.LETTER_TO_SANTA,
        Titles.YOU_CANT_WIN,
        Titles.TURKEY_RAFFLE,
        Titles.CHRISTMAS_FOR_SHACKTOWN_A,
        Titles.TURKEY_WITH_ALL_THE_SCHEMINGS,
        Titles.HAMMY_CAMEL_THE,
        Titles.SEARCH_FOR_THE_CUSPIDORIA,
        Titles.THREE_UN_DUCKS,
        Titles.BLACK_PEARLS_OF_TABU_YAMA_THE,
        Titles.CODE_OF_DUCKBURG_THE,
        Titles.CHRISTMAS_IN_DUCKBURG,
        Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY,
        Titles.NORTHEASTER_ON_CAPE_QUACK,
        Titles.CHRISTMAS_CHEERS,
        Titles.DOUBLE_MASQUERADE,
        Titles.THRIFTY_SPENDTHRIFT_THE,
    ],
    Tags.HYPNOSIS: [
        Titles.DAYS_AT_THE_LAZY_K,
        Titles.ADVENTURE_DOWN_UNDER,
        Titles.GOING_APE,
        Titles.YOU_CANT_GUESS,
        Titles.HYPNO_GUN_THE,
        Titles.BACK_TO_LONG_AGO,
        Titles.LOST_PEG_LEG_MINE_THE,
        Titles.RAVEN_MAD,
        Titles.THRIFTY_SPENDTHRIFT_THE,
        Titles.SWAMP_OF_NO_RETURN_THE,
    ],
    Tags.MAGIC: [Titles.MAGICAL_MISERY],
    Tags.NEW_VERSIONS: [
        Titles.MOCKING_BIRD_RIDGE,
        Titles.DRAMATIC_DONALD,
        Titles.LITTLEST_CHICKEN_THIEF_THE,
        Titles.BEACHCOMBERS_PICNIC_THE,
        Titles.GOOD_DEEDS_THE,
        Titles.WATCHFUL_PARENTS_THE,
        Titles.WANT_TO_BUY_AN_ISLAND,
        Titles.FROGGY_FARMER,
        Titles.ICE_TAXIS_THE,
        Titles.IN_THE_SWIM,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
        Titles.TERRIBLE_TOURIST,
        Titles.LAND_OF_THE_PYGMY_INDIANS,
        Titles.FORBIDDEN_VALLEY,
        Titles.YOICKS_THE_FOX,
    ],
    # Things
    Tags.AIRPLANE: [
        Titles.TRUANT_NEPHEWS_THE,
        Titles.MASTER_RAINMAKER_THE,
        Titles.CROWN_OF_THE_MAYAS,
        Titles.ADVENTURE_DOWN_UNDER,
        Titles.NORTH_OF_THE_YUKON,
        Titles.TRAIL_OF_THE_UNICORN,
        Titles.TWO_WAY_LUCK,
        Titles.GREAT_WIG_MYSTERY_THE,
        Titles.BALLOONATICS,
        Titles.FROZEN_GOLD,
        Titles.LOST_FRONTIER,
        Titles.FRAIDY_FALCON_THE,
        Titles.TRALLA_LA,
        Titles.SO_FAR_AND_NO_SAFARI,
        Titles.VOLCANO_VALLEY,
        Titles.VOODOO_HOODOO,
        Titles.SPICY_TALE_A,
        Titles.LAND_OF_THE_PYGMY_INDIANS,
        Titles.GOOD_DEEDS_THE,
        Titles.SECRET_OF_ATLANTIS_THE,
        Titles.SMOKE_WRITER_IN_THE_SKY,
        Titles.QUEEN_OF_THE_WILD_DOG_PACK_THE,
    ],
    Tags.CAMERA: [
        Titles.CAMERA_CRAZY,
        Titles.PECKING_ORDER,
        Titles.VACATION_TIME,
        Titles.SECRET_RESOLUTIONS,
        Titles.MYSTERY_OF_THE_LOCH,
        Titles.MEDALING_AROUND,
        Titles.DUCKS_EYE_VIEW_OF_EUROPE_A,
    ],
    Tags.CIGARETTES: [
        Titles.LIMBER_W_GUEST_RANCH_THE,
        Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
        Titles.MAD_CHEMIST_THE,
        Titles.SWIMMING_SWINDLERS,
        Titles.GOING_BUGGY,
        Titles.JAM_ROBBERS,
        Titles.SHERIFF_OF_BULLET_VALLEY,
        Titles.DANGEROUS_DISGUISE,
        Titles.VACATION_TIME,
        Titles.BILLIONS_TO_SNEEZE_AT,
    ],
    Tags.FIRE: [Titles.FIREBUG_THE, Titles.FIREMAN_DONALD, Titles.LOVELORN_FIREMAN_THE],
    Tags.SQUARE_EGGS: [Titles.LOST_IN_THE_ANDES],
    Tags.WEEMITE: [Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY],
    # Characters
    Tags.ARGUS_MCFIENDY: [Titles.DARKEST_AFRICA],
    Tags.AZURE_BLUE: [Titles.GOLDEN_HELMET_THE],
    Tags.BEAGLE_BOYS: [
        Titles.TERROR_OF_THE_BEAGLE_BOYS,
        Titles.BIG_BIN_ON_KILLMOTOR_HILL_THE,
        Titles.ONLY_A_POOR_OLD_MAN,
        Titles.ROUND_MONEY_BIN_THE,
        Titles.MENEHUNE_MYSTERY_THE,
        Titles.SEVEN_CITIES_OF_CIBOLA_THE,
        Titles.MYSTERIOUS_STONE_RAY_THE,
        Titles.FANTASTIC_RIVER_RACE_THE,
        Titles.MONEY_WELL_THE,
        Titles.CHRISTMAS_IN_DUCKBURG,
        Titles.STRANGE_SHIPWRECKS_THE,
        Titles.TWENTY_FOUR_CARAT_MOON_THE,
        Titles.PAUL_BUNYAN_MACHINE_THE,
        Titles.ALL_AT_SEA,
        Titles.TREE_TRICK,
        Titles.BILLIONS_IN_THE_HOLE,
        Titles.GIFT_LION,
        Titles.DEEP_DOWN_DOINGS,
        Titles.UNSAFE_SAFE_THE,
        Titles.TRICKY_EXPERIMENT,
        Titles.STATUS_SEEKER_THE,
        Titles.CASE_OF_THE_STICKY_MONEY_THE,
        Titles.ISLE_OF_GOLDEN_GEESE,
        Titles.HOW_GREEN_WAS_MY_LETTUCE,
        Titles.GIANT_ROBOT_ROBBERS_THE,
        Titles.HOUSE_OF_HAUNTS,
        Titles.HEEDLESS_HORSEMAN_THE,
        Titles.DOOM_DIAMOND_THE,
        Titles.MR_PRIVATE_EYE,
        Titles.DELIVERY_DILEMMA,
    ],
    Tags.BENZENE_BANZOONY: [Titles.FIREBUG_THE],
    Tags.BOMBIE_THE_ZOMBIE: [Titles.VOODOO_HOODOO],
    Tags.CARVER_BEAKOFF: [Titles.FIREBUG_THE],
    Tags.CHISEL_MC_SUE: [Titles.HORSERADISH_STORY_THE],
    Tags.CORNELIUS_MC_COBB: [Titles.VOODOO_HOODOO],
    Tags.DAISY: [
        Titles.MIGHTY_TRAPPER_THE,
        Titles.EYES_IN_THE_DARK,
        Titles.DONALD_TAMES_HIS_TEMPER,
        Titles.BICEPS_BLUES,
        Titles.GOLD_FINDER_THE,
        Titles.CANTANKEROUS_CAT_THE,
        Titles.PICNIC_TRICKS,
        Titles.MAGICAL_MISERY,
        Titles.WALTZ_KING_THE,
        Titles.WINTERTIME_WAGER,
        Titles.WATCHING_THE_WATCHMAN,
        Titles.GOING_APE,
        Titles.ROCKET_RACE_TO_THE_MOON,
        Titles.GLADSTONE_RETURNS,
        Titles.PEARLS_OF_WISDOM,
        Titles.DONALD_DUCKS_WORST_NIGHTMARE,
        Titles.DONALDS_LOVE_LETTERS,
        Titles.LAND_OF_THE_TOTEM_POLES,
        Titles.WILD_ABOUT_FLOWERS,
        Titles.BIG_TOP_BEDLAM,
        Titles.YOU_CANT_GUESS,
        Titles.KNIGHTLY_RIVALS,
        Titles.CHRISTMAS_FOR_SHACKTOWN_A,
        Titles.ATTIC_ANTICS,
        Titles.GLADSTONES_USUAL_VERY_GOOD_YEAR,
        Titles.ROCKET_WING_SAVES_THE_DAY,
        Titles.HOBBLIN_GOBLINS,
        Titles.OMELET,
        Titles.CHARITABLE_CHORE_A,
        Titles.FLIP_DECISION,
        Titles.MY_LUCKY_VALENTINE,
        Titles.EASTER_ELECTION_THE,
        Titles.MASTER_RAINMAKER_THE,
        Titles.RAFFLE_REVERSAL,
        Titles.FIX_UP_MIX_UP,
        Titles.DAFFY_TAFFY_PULL_THE,
        Titles.KNIGHT_IN_SHINING_ARMOR,
        Titles.LOSING_FACE,
        Titles.DAY_DUCKBURG_GOT_DYED_THE,
        Titles.RED_APPLE_SAP,
        Titles.DODGING_MISS_DAISY,
        Titles.WATER_SKI_RACE,
        Titles.TRACKING_SANDY,
        Titles.BEACHCOMBERS_PICNIC_THE,
        Titles.DRAMATIC_DONALD,
        Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY,
        Titles.LOVELORN_FIREMAN_THE,
        Titles.KNIGHTS_OF_THE_FLYING_SLEDS,
        Titles.WEATHER_WATCHERS_THE,
        Titles.VILLAGE_BLACKSMITH_THE,
        Titles.TURKEY_TROUBLE,
        Titles.BOXED_IN,
        Titles.MR_PRIVATE_EYE,
        Titles.JINXED_JALOPY_RACE_THE,
        Titles.HAVE_GUN_WILL_DANCE,
        Titles.OLYMPIAN_TORCH_BEARER_THE,
        Titles.HERO_OF_THE_DIKE,
        Titles.BEAUTY_BUSINESS_THE,
        Titles.NOT_SO_ANCIENT_MARINER_THE,
    ],
    Tags.EL_DORADO: [Titles.GILDED_MAN_THE],
    Tags.FERMIES: [Titles.LAND_BENEATH_THE_GROUND],
    Tags.FLINTHEART_GLOMGOLD: [
        Titles.SECOND_RICHEST_DUCK_THE,
        Titles.MONEY_CHAMP_THE,
        Titles.SO_FAR_AND_NO_SAFARI,
    ],
    Tags.FOOLA_ZOOLA: [Titles.VOODOO_HOODOO],
    Tags.GENERAL_SNOZZIE: [
        Titles.PHANTOM_OF_NOTRE_DUCK_THE,
        Titles.DODGING_MISS_DAISY,
        Titles.BLACK_FOREST_RESCUE_THE,
        Titles.HOUND_HOUNDER,
        Titles.MEDALING_AROUND,
        Titles.BEACH_BOY,
        Titles.DUCK_OUT_OF_LUCK,
    ],
    Tags.GLADSTONE_GANDER: [
        Titles.YOU_CANT_GUESS,
        Titles.SECRET_OF_HONDORICA,
        Titles.RACE_TO_THE_SOUTH_SEAS,
        Titles.LUCK_OF_THE_NORTH,
        Titles.TRAIL_OF_THE_UNICORN,
        Titles.CHRISTMAS_FOR_SHACKTOWN_A,
        Titles.GILDED_MAN_THE,
        Titles.LOST_RABBIT_FOOT_THE,
        Titles.BEAR_TAMER_THE,
        Titles.GOING_TO_PIECES,
        Titles.KITTY_GO_ROUND,
        Titles.GOLDEN_NUGGET_BOAT_THE,
        Titles.SEEING_IS_BELIEVING,
        Titles.BILLION_DOLLAR_SAFARI_THE,
        Titles.WINTERTIME_WAGER,
        Titles.GLADSTONE_RETURNS,
        Titles.LINKS_HIJINKS,
        Titles.RIVAL_BEACHCOMBERS,
        Titles.GOLDILOCKS_GAMBIT_THE,
        Titles.DONALDS_LOVE_LETTERS,
        Titles.WILD_ABOUT_FLOWERS,
        Titles.FINANCIAL_FABLE_A,
        Titles.KNIGHTLY_RIVALS,
        Titles.GLADSTONES_LUCK,
        Titles.GLADSTONES_USUAL_VERY_GOOD_YEAR,
        Titles.GLADSTONES_TERRIBLE_SECRET,
        Titles.GEMSTONE_HUNTERS,
        Titles.CHARITABLE_CHORE_A,
        Titles.MY_LUCKY_VALENTINE,
        Titles.EASTER_ELECTION_THE,
        Titles.SOME_HEIR_OVER_THE_RAINBOW,
        Titles.MASTER_RAINMAKER_THE,
        Titles.RAFFLE_REVERSAL,
        Titles.SALMON_DERBY,
        Titles.DAFFY_TAFFY_PULL_THE,
        Titles.GOOD_CANOES_AND_BAD_CANOES,
        Titles.SEARCHING_FOR_A_SUCCESSOR,
        Titles.RED_APPLE_SAP,
        Titles.TENDERFOOT_TRAP_THE,
        Titles.CODE_OF_DUCKBURG_THE,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
        Titles.MOCKING_BIRD_RIDGE,
        Titles.DRAMATIC_DONALD,
        Titles.BEACHCOMBERS_PICNIC_THE,
        Titles.LOVELORN_FIREMAN_THE,
        Titles.TURKEY_TROUBLE,
        Titles.DUCK_LUCK,
        Titles.JINXED_JALOPY_RACE_THE,
        Titles.DUCKBURG_PET_PARADE_THE,
        Titles.HERO_OF_THE_DIKE,
        Titles.DUCK_OUT_OF_LUCK,
        Titles.NOT_SO_ANCIENT_MARINER_THE,
    ],
    Tags.GYRO_GEARLOOSE: [
        Titles.GRANDMAS_PRESENT,
        Titles.HOBBLIN_GOBLINS,
        Titles.FORBIDIUM_MONEY_BIN_THE,
        Titles.AUGUST_ACCIDENT,
        Titles.WEATHER_WATCHERS_THE,
        Titles.GAB_MUFFER_THE,
        Titles.STUBBORN_STORK_THE,
        Titles.MILKTIME_MELODIES,
        Titles.LOST_RABBIT_FOOT_THE,
        Titles.BIRD_CAMERA_THE,
        Titles.ODD_ORDER_THE,
        Titles.CALL_OF_THE_WILD_THE,
        Titles.CAVE_OF_THE_WINDS,
        Titles.MIXED_UP_MIXER,
        Titles.MADBALL_PITCHER_THE,
        Titles.BEAR_TAMER_THE,
        Titles.TALE_OF_THE_TAPE,
        Titles.HIS_SHINING_HOUR,
        Titles.PICNIC,
        Titles.SEVEN_CITIES_OF_CIBOLA_THE,
        Titles.HEIRLOOM_WATCH,
        Titles.TRAPPED_LIGHTNING,
        Titles.INVENTOR_OF_ANYTHING,
        Titles.CAT_BOX_THE,
        Titles.FORECASTING_FOLLIES,
        Titles.FISHING_MYSTERY,
        Titles.SURE_FIRE_GOLD_FINDER_THE,
        Titles.GYRO_BUILDS_A_BETTER_HOUSE,
        Titles.ROSCOE_THE_ROBOT,
        Titles.GETTING_THOR,
        Titles.KNOW_IT_ALL_MACHINE_THE,
        Titles.GYRO_GOES_FOR_A_DIP,
        Titles.HOUSE_ON_CYCLONE_HILL_THE,
        Titles.WISHING_WELL_THE,
        Titles.KRANKENSTEIN_GYRO,
        Titles.FIREFLY_TRACKER_THE,
        Titles.INVENTORS_CONTEST_THE,
        Titles.OODLES_OF_OOMPH,
        Titles.WAR_PAINT,
        Titles.FISHY_WARDEN,
        Titles.THAT_SMALL_FEELING,
        Titles.YOU_CANT_WIN,
        Titles.WILY_RIVAL,
        Titles.FAST_AWAY_CASTAWAY,
        Titles.DUCKBURGS_DAY_OF_PERIL,
        Titles.GREAT_POP_UP_THE,
        Titles.MADCAP_INVENTORS,
        Titles.FINNY_FUN,
        Titles.POSTHASTY_POSTMAN,
        Titles.SNOW_DUSTER,
        Titles.HELPERS_HELPING_HAND_A,
        Titles.MAN_VERSUS_MACHINE,
        Titles.JONAH_GYRO,
        Titles.GLADSTONES_TERRIBLE_SECRET,
        Titles.THINK_BOX_BOLLIX_THE,
        Titles.TALKING_DOG_THE,
        Titles.WORM_WEARY,
        Titles.TOO_SAFE_SAFE,
        Titles.SMOKE_WRITER_IN_THE_SKY,
        Titles.GYROS_IMAGINATION_INVENTION,
        Titles.DAY_DUCKBURG_GOT_DYED_THE,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
        Titles.BLACK_WEDNESDAY,
        Titles.KNIGHTS_OF_THE_FLYING_SLEDS,
        Titles.VILLAGE_BLACKSMITH_THE,
        Titles.BALLOONATICS,
        Titles.MISSILE_FIZZLE,
        Titles.MADCAP_MARINER_THE,
        Titles.STRANGER_THAN_FICTION,
        Titles.JET_WITCH,
        Titles.DUCKBURG_PET_PARADE_THE,
        Titles.CAPN_BLIGHTS_MYSTERY_SHIP,
        Titles.FUN_WHATS_THAT,
        Titles.ON_THE_DREAM_PLANET,
    ],
    Tags.GYRO_NOT_IN_GG: [
        Titles.HOBBLIN_GOBLINS,
        Titles.SEVEN_CITIES_OF_CIBOLA_THE,
        Titles.HEIRLOOM_WATCH,
        Titles.GLADSTONES_TERRIBLE_SECRET,
        Titles.THINK_BOX_BOLLIX_THE,
        Titles.TALKING_DOG_THE,
        Titles.WORM_WEARY,
        Titles.TOO_SAFE_SAFE,
        Titles.SMOKE_WRITER_IN_THE_SKY,
        Titles.GYROS_IMAGINATION_INVENTION,
        Titles.DAY_DUCKBURG_GOT_DYED_THE,
        Titles.ROCKET_RACE_AROUND_THE_WORLD,
        Titles.BLACK_WEDNESDAY,
        Titles.KNIGHTS_OF_THE_FLYING_SLEDS,
        Titles.UNDER_THE_POLAR_ICE,
        Titles.VILLAGE_BLACKSMITH_THE,
        Titles.BALLOONATICS,
        Titles.MISSILE_FIZZLE,
        Titles.MADCAP_MARINER_THE,
        Titles.STRANGER_THAN_FICTION,
        Titles.JET_WITCH,
        Titles.DUCKBURG_PET_PARADE_THE,
        Titles.CAPN_BLIGHTS_MYSTERY_SHIP,
        Titles.FORBIDIUM_MONEY_BIN_THE,
        # TODO: NEED TO CHECK THESE
        Titles.CALL_OF_THE_WILD_THE,
        Titles.CAVE_OF_THE_WINDS,
        Titles.MIXED_UP_MIXER,
        Titles.MADBALL_PITCHER_THE,
        Titles.BEAR_TAMER_THE,
        Titles.TALE_OF_THE_TAPE,
        Titles.HIS_SHINING_HOUR,
        Titles.THAT_SMALL_FEELING,
        Titles.YOU_CANT_WIN,
        Titles.WILY_RIVAL,
        Titles.FAST_AWAY_CASTAWAY,
        Titles.DUCKBURGS_DAY_OF_PERIL,
        Titles.GREAT_POP_UP_THE,
        Titles.MADCAP_INVENTORS,
        Titles.FINNY_FUN,
        Titles.POSTHASTY_POSTMAN,
        Titles.SNOW_DUSTER,
        Titles.HELPERS_HELPING_HAND_A,
        Titles.MAN_VERSUS_MACHINE,
        Titles.JONAH_GYRO,
        Titles.FUN_WHATS_THAT,
        Titles.ON_THE_DREAM_PLANET,
    ],
    Tags.HASSAN_BEN_JAILD: [Titles.MCDUCK_OF_ARABIA],
    Tags.HERBERT: [
        Titles.THREE_DIRTY_LITTLE_DUCKS,
        Titles.TEN_CENTS_WORTH_OF_TROUBLE,
        Titles.SMUGSNORKLE_SQUATTIE_THE,
    ],
    Tags.JUNIOR_WOODCHUCKS: [
        Titles.OPERATION_ST_BERNARD,
        Titles.TEN_STAR_GENERALS,
        Titles.GLADSTONES_USUAL_VERY_GOOD_YEAR,
        Titles.SCREAMING_COWBOY_THE,
        Titles.SPENDING_MONEY,
        Titles.MY_LUCKY_VALENTINE,
        Titles.BEE_BUMBLES,
        Titles.CHICKADEE_CHALLENGE_THE,
        Titles.HALF_BAKED_BAKER_THE,
        Titles.TRACKING_SANDY,
        Titles.BLACK_FOREST_RESCUE_THE,
        Titles.STUBBORN_STORK_THE,
        Titles.UNDER_THE_POLAR_ICE,
        Titles.DOG_SITTER_THE,
        Titles.HOUND_HOUNDER,
        Titles.MEDALING_AROUND,
        Titles.BEACH_BOY,
        Titles.BUBBLEWEIGHT_CHAMP,
    ],
    Tags.MAGICA_DE_SPELL: [
        Titles.MIDAS_TOUCH_THE,
        Titles.UNSAFE_SAFE_THE,
        Titles.ODDBALL_ODYSSEY,
        Titles.FOR_OLD_DIMES_SAKE,
        Titles.ISLE_OF_GOLDEN_GEESE,
        Titles.MANY_FACES_OF_MAGICA_DE_SPELL_THE,
        Titles.RUG_RIDERS_IN_THE_SKY,
        Titles.TEN_CENT_VALENTINE,
        Titles.RAVEN_MAD,
    ],
    Tags.MR_MC_SWINE: [Titles.MILKMAN_THE],
    Tags.NEIGHBOR_JONES: [
        Titles.GOOD_DEEDS,
        Titles.GOOD_NEIGHBORS,
        Titles.PURLOINED_PUTTY_THE,
        Titles.TEN_DOLLAR_DITHER,
        Titles.SILENT_NIGHT,
        Titles.GOOD_DEEDS_THE,
        Titles.FEUD_AND_FAR_BETWEEN,
        Titles.UNFRIENDLY_ENEMIES,
    ],
    Tags.P_J_MC_BRINE: [Titles.FORBIDDEN_VALLEY],
    Tags.PORKMAN_DE_LARDO: [Titles.STATUS_SEEKER_THE],
    Tags.SCROOGE_NOT_IN_US: [
        Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
        Titles.OLD_CASTLES_SECRET_THE,
        Titles.FOXY_RELATIONS,
        Titles.SUNKEN_YACHT_THE,
        Titles.RACE_TO_THE_SOUTH_SEAS,
        Titles.VOODOO_HOODOO,
        Titles.LETTER_TO_SANTA,
        Titles.TRAIL_OF_THE_UNICORN,
        Titles.PIXILATED_PARROT_THE,
        Titles.MAGIC_HOURGLASS_THE,
        Titles.YOU_CANT_GUESS,
        Titles.NO_SUCH_VARMINT,
        Titles.BILLIONS_TO_SNEEZE_AT,
        Titles.FINANCIAL_FABLE_A,
        Titles.TROUBLE_WITH_DIMES_THE,
        Titles.CHRISTMAS_FOR_SHACKTOWN_A,
        Titles.TERROR_OF_THE_BEAGLE_BOYS,
        Titles.BIG_BIN_ON_KILLMOTOR_HILL_THE,
        Titles.STATUESQUE_SPENDTHRIFTS,
        Titles.GLADSTONES_TERRIBLE_SECRET,
        Titles.SPENDING_MONEY,
        Titles.HYPNO_GUN_THE,
        Titles.TURKEY_WITH_ALL_THE_SCHEMINGS,
        Titles.SOME_HEIR_OVER_THE_RAINBOW,
        Titles.MONEY_STAIRS_THE,
        Titles.WISPY_WILLIE,
        Titles.TURKEY_TROT_AT_ONE_WHISTLE,
        Titles.FLOUR_FOLLIES,
        Titles.TOO_SAFE_SAFE,
        Titles.SEARCH_FOR_THE_CUSPIDORIA,
        Titles.SECRET_OF_HONDORICA,
        Titles.TROUBLE_INDEMNITY,
        Titles.SEARCHING_FOR_A_SUCCESSOR,
        Titles.SMOKE_WRITER_IN_THE_SKY,
        Titles.RUNAWAY_TRAIN_THE,
        Titles.IN_KAKIMAW_COUNTRY,
        Titles.LOST_PEG_LEG_MINE_THE,
        Titles.SAGMORE_SPRINGS_HOTEL,
        Titles.TENDERFOOT_TRAP_THE,
        Titles.BLACK_PEARLS_OF_TABU_YAMA_THE,
        Titles.SEPTEMBER_SCRIMMAGE,
        Titles.TITANIC_ANTS_THE,
        Titles.MOCKING_BIRD_RIDGE,
        Titles.FORBIDIUM_MONEY_BIN_THE,
        Titles.TRACKING_SANDY,
        Titles.FLOATING_ISLAND_THE,
        Titles.BLACK_WEDNESDAY,
        Titles.FUN_WHATS_THAT,
        Titles.STUBBORN_STORK_THE,
        Titles.CAVE_OF_THE_WINDS,
        Titles.VILLAGE_BLACKSMITH_THE,
        Titles.ROCKS_TO_RICHES,
        Titles.MADCAP_MARINER_THE,
        Titles.MR_PRIVATE_EYE,
        Titles.BOAT_BUSTER,
        Titles.TEN_CENT_VALENTINE,
        Titles.RAVEN_MAD,
        Titles.MATTER_OF_FACTORY_A,
        Titles.CHRISTMAS_CHEERS,
        Titles.ZERO_HERO,
        Titles.DUCKBURG_PET_PARADE_THE,
        Titles.DOUBLE_MASQUERADE,
        Titles.DELIVERY_DILEMMA,
    ],
    Tags.SOAPY_SLICK: [Titles.NORTH_OF_THE_YUKON],
    Tags.TERRIES: [Titles.LAND_BENEATH_THE_GROUND],
}

BARKS_TAGGED_PAGES: dict[tuple[Tags, Titles], list[str]] = {
    (Tags.BARNACLE_BAY, Titles.NO_SUCH_VARMINT): ["11"],
    (Tags.CAMERA, Titles.SECRET_RESOLUTIONS): ["8"],
    (Tags.CAMERA, Titles.VACATION_TIME): ["10"],  # plus more pages
    (Tags.CARVER_BEAKOFF, Titles.FIREBUG_THE): ["13"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.ICEBOX_ROBBER_THE): ["7"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.SWIMMING_SWINDLERS): ["1", "2", "7"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.BILL_COLLECTORS_THE): ["3"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.LOVELORN_FIREMAN_THE): ["8"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.FROZEN_GOLD): ["5", "9", "16", "17", "24"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.FIREBUG_THE): ["13"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.TERROR_OF_THE_RIVER_THE): ["1"],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.LOST_IN_THE_ANDES): [
        "20",
        "21",
        "22",
        "23",
        "24",
        "26",
        "27",
        "28",
        "29",
        "31",
    ],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.VOODOO_HOODOO): [
        "1",
        "6",
        "8",
        "9",
        "10",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "20",
        "22",
        "23",
        "31",
        "32",
    ],
    (Tags.CENSORED_STORIES_BUT_FIXED, Titles.GOLDEN_FLEECING_THE): [
        "6",
        "7",
        "9",
        "13",
        "14",
        "15",
        "16",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
    ],
    (Tags.CIGARETTES, Titles.MAD_CHEMIST_THE): ["10"],
    (Tags.CIGARETTES, Titles.SWIMMING_SWINDLERS): ["1", "2", "7"],
    (Tags.CIGARETTES, Titles.GOING_BUGGY): ["3"],
    (Tags.CIGARETTES, Titles.JAM_ROBBERS): ["7"],
    (Tags.CIGARETTES, Titles.SHERIFF_OF_BULLET_VALLEY): [
        "4",
        "5",
        "6",
        "8",
        "13",
        "14",
        "17",
        "20",
        "25",
        "26",
        "27",
    ],
    (Tags.CIGARETTES, Titles.DANGEROUS_DISGUISE): ["3"],
    (Tags.CIGARETTES, Titles.VACATION_TIME): ["8", "9", "12", "13", "29", "30"],
    (Tags.CIGARETTES, Titles.BILLIONS_TO_SNEEZE_AT): ["8"],
    (Tags.CORNELIUS_MC_COBB, Titles.VOODOO_HOODOO): ["20", "21", "22", "23"],
    (Tags.DAISY, Titles.EYES_IN_THE_DARK): ["7"],
    (Tags.EL_DORADO, Titles.GILDED_MAN_THE): [
        "8",
        "11",
        "12",
        "14",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
    ],
    (Tags.FOOLA_ZOOLA, Titles.VOODOO_HOODOO): [
        "6",
        "17",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
        "29",
        "30",
        "31",
    ],
    (Tags.GYRO_NOT_IN_GG, Titles.KNIGHTS_OF_THE_FLYING_SLEDS): ["3"],
    (Tags.GYRO_NOT_IN_GG, Titles.UNDER_THE_POLAR_ICE): ["3"],
    (Tags.NEIGHBOR_JONES, Titles.GOOD_DEEDS): ["1"],
    (Tags.P_J_MC_BRINE, Titles.FORBIDDEN_VALLEY): ["3"],
    (Tags.WEEMITE, Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY): ["3", "4", "6", "7", "8"],
}


def special_case_personal_favourites_tag_update(my_title_picks: list[Titles]) -> None:
    BARKS_TAGGED_TITLES[Tags.PERSONAL_FAVOURITES] = my_title_picks


def set_tag_alias(main_tag: Tags, alias_tag: Tags) -> None:
    assert alias_tag not in BARKS_TAGGED_TITLES
    BARKS_TAGGED_TITLES[alias_tag] = BARKS_TAGGED_TITLES[main_tag]

    main_tag_title_pages = [(k[1], v) for k, v in BARKS_TAGGED_PAGES.items() if main_tag == k[0]]
    for title, pages in main_tag_title_pages:
        assert (alias_tag, title) not in BARKS_TAGGED_PAGES
        BARKS_TAGGED_PAGES[(alias_tag, title)] = pages


set_tag_alias(Tags.CAMERA, Tags.PHOTOGRAPHY)


def is_tag_group_enum(value: str) -> bool:
    try:
        TagGroups(value)
    except ValueError:
        return False
    else:
        return True


def get_tag_group_enum(value: str) -> TagGroups | None:
    try:
        return TagGroups(value)
    except ValueError:
        return None


def is_tag_enum(value: str) -> bool:
    try:
        Tags(value)
    except ValueError:
        return False
    else:
        return True


def get_tag_enum(value: str) -> Tags | None:
    try:
        return Tags(value)
    except ValueError:
        return None


def get_num_tagged_titles() -> int:
    num = 0
    for titles_list in BARKS_TAGGED_TITLES.values():
        num += len(titles_list)

    return num


# TODO: Assert tagged pages are in tagged titles
def validate_tag_data() -> None:
    """Perform various assertions to ensure the integrity of the tag data.

    Raise AssertionError if any validation fails.
    """
    # Validate BARKS_TAGGED_TITLES keys and values
    for tag, titles_list in BARKS_TAGGED_TITLES.items():
        assert isinstance(tag, Tags), f"Invalid tag key in BARKS_TAGGED_TITLES: {tag}"
        for title in titles_list:
            assert isinstance(
                title,
                Titles,
            ), f"Invalid title '{title}' for tag '{tag.value}' in BARKS_TAGGED_TITLES"

    # Validate BARKS_TAGGED_PAGES
    for (tag, title), pages in BARKS_TAGGED_PAGES.items():
        assert isinstance(tag, Tags), f"Invalid tag key in BARKS_TAGGED_PAGES: {tag}"
        assert isinstance(title, Titles), f"Invalid title key in BARKS_TAGGED_PAGES: {title}"
        assert tag in BARKS_TAGGED_TITLES, (
            f"Tag '{tag.value}' in BARKS_TAGGED_PAGES is not in BARKS_TAGGED_TITLES."
        )
        assert title in BARKS_TAGGED_TITLES[tag], (
            f"Title '{title.value}' for tag '{tag.value}' in BARKS_TAGGED_PAGES "
            f"is not listed under that tag in BARKS_TAGGED_TITLES."
        )
        for page in pages:
            assert isinstance(
                page,
                str,
            ), f"Page '{page}' for ({tag.value}, {title.value}) must be a string."

    # Validate BARKS_TAG_CATEGORIES
    for category, tags_or_groups_list in BARKS_TAG_CATEGORIES.items():
        assert isinstance(category, TagCategories), f"Invalid category key: {category}"
        for item in tags_or_groups_list:
            assert isinstance(
                item,
                (Tags, TagGroups),
            ), f"Invalid item '{item}' in category '{category.value}'. Must be Tags or TagGroups."

    # Validate BARKS_TAG_GROUPS
    for group, tags_list in BARKS_TAG_GROUPS.items():
        assert isinstance(group, TagGroups), f"Invalid group key: {group}"
        for tag_item in tags_list:
            assert isinstance(tag_item, (Tags, TagGroups)), (
                f"Invalid tag '{tag_item}' in group '{group.value}'. Must be Tags or TagGroups."
            )


def get_tagged_titles(tag: Tags) -> list[Titles]:
    """Retrieve a sorted list of unique titles associated with a specific tag.

    Return an empty list if the tag is not found or has no titles.
    """
    if tag not in BARKS_TAGGED_TITLES:
        return []
    return sorted(set(BARKS_TAGGED_TITLES[tag]))  # Ensure uniqueness and sort


def _get_tag_categories_titles() -> dict[TagCategories, list[Titles]]:
    """Get a dictionary mapping each TagCategory to a sorted list of unique
    titles associated with the tags/groups in that category.
    """
    tag_categories_titles: dict[TagCategories, list[Titles]] = {}
    for category, items_list in BARKS_TAG_CATEGORIES.items():
        tag_categories_titles[category] = sorted(_get_titles_for_tags_or_groups(items_list))
    return tag_categories_titles


def _get_tag_groups_titles() -> dict[TagGroups, list[Titles]]:
    """Get a dictionary mapping each TagGroup to a sorted list of unique
    titles associated with the tags/groups in that tag group.
    """
    tag_groups_titles: dict[TagGroups, list[Titles]] = {}
    for tag_group, items_list in BARKS_TAG_GROUPS.items():
        tag_groups_titles[tag_group] = sorted(_get_titles_for_tags_or_groups(items_list))
    return tag_groups_titles


def _get_titles_for_tags_or_groups(items_list: list[Tags | TagGroups]) -> set[Titles]:
    """Recursively collect all unique titles for a list that may contain individual
    Tags or TagGroups.
    """
    collected_titles: set[Titles] = set()
    for item in items_list:
        if isinstance(item, TagGroups):
            # Recursively get titles for tags within this group
            if item in BARKS_TAG_GROUPS:
                collected_titles.update(_get_titles_for_tags_or_groups(BARKS_TAG_GROUPS[item]))
        elif isinstance(item, Tags) and (item in BARKS_TAGGED_TITLES):
            collected_titles.update(BARKS_TAGGED_TITLES[item])
    return collected_titles


BARKS_TAG_CATEGORIES_TITLES: dict[TagCategories, list[Titles]] = _get_tag_categories_titles()
BARKS_TAG_GROUPS_TITLES: dict[TagGroups, list[Titles]] = _get_tag_groups_titles()
