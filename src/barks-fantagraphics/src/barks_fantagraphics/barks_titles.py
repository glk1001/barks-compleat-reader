from enum import CONTINUOUS, UNIQUE, IntEnum, auto, verify

NUM_TITLES = 684 + 264 + 4 + 2  # +264 covers, +4 articles, +2 synthetic collections

GYRO_GEARLOOSE = "Gyro Gearloose"

US_1_FC_ISSUE_NUM = 386
US_2_FC_ISSUE_NUM = 456
US_3_FC_ISSUE_NUM = 495


@verify(CONTINUOUS, UNIQUE)
class Titles(IntEnum):
    DONALD_DUCK_FINDS_PIRATE_GOLD = 0
    VICTORY_GARDEN_THE = auto()
    RABBITS_FOOT_THE = auto()
    LIFEGUARD_DAZE = auto()
    GOOD_DEEDS = auto()
    LIMBER_W_GUEST_RANCH_THE = auto()
    MIGHTY_TRAPPER_THE = auto()
    DONALD_DUCK_AND_THE_MUMMYS_RING = auto()
    HARD_LOSER_THE = auto()
    TOO_MANY_PETS = auto()
    GOOD_NEIGHBORS = auto()
    SALESMAN_DONALD = auto()
    SNOW_FUN = auto()
    DUCK_IN_THE_IRON_PANTS_THE = auto()
    KITE_WEATHER = auto()
    THREE_DIRTY_LITTLE_DUCKS = auto()
    MAD_CHEMIST_THE = auto()
    RIVAL_BOATMEN = auto()
    CAMERA_CRAZY = auto()
    FARRAGUT_THE_FALCON = auto()
    PURLOINED_PUTTY_THE = auto()
    HIGH_WIRE_DAREDEVILS = auto()
    TEN_CENTS_WORTH_OF_TROUBLE = auto()
    DONALDS_BAY_LOT = auto()
    FROZEN_GOLD = auto()
    THIEVERY_AFOOT = auto()
    MYSTERY_OF_THE_SWAMP = auto()
    TRAMP_STEAMER_THE = auto()
    LONG_RACE_TO_PUMPKINBURG_THE = auto()
    WEBFOOTED_WRANGLER = auto()
    ICEBOX_ROBBER_THE = auto()
    PECKING_ORDER = auto()
    TAMING_THE_RAPIDS = auto()
    DAYS_AT_THE_LAZY_K = auto()
    RIDDLE_OF_THE_RED_HAT_THE = auto()
    EYES_IN_THE_DARK = auto()
    THUG_BUSTERS = auto()
    GREAT_SKI_RACE_THE = auto()
    FIREBUG_THE = auto()
    TEN_DOLLAR_DITHER = auto()
    DONALD_DUCKS_BEST_CHRISTMAS = auto()
    SILENT_NIGHT = auto()
    DONALD_TAMES_HIS_TEMPER = auto()
    SINGAPORE_JOE = auto()
    MASTER_ICE_FISHER = auto()
    JET_RESCUE = auto()
    DONALDS_MONSTER_KITE = auto()
    TERROR_OF_THE_RIVER_THE = auto()
    SEALS_ARE_SO_SMART = auto()
    BICEPS_BLUES = auto()
    SMUGSNORKLE_SQUATTIE_THE = auto()
    SANTAS_STORMY_VISIT = auto()
    SWIMMING_SWINDLERS = auto()
    PLAYIN_HOOKEY = auto()
    GOLD_FINDER_THE = auto()
    BILL_COLLECTORS_THE = auto()
    TURKEY_RAFFLE = auto()
    MAHARAJAH_DONALD = auto()
    CANTANKEROUS_CAT_THE = auto()
    DONALD_DUCKS_ATOM_BOMB = auto()
    GOING_BUGGY = auto()
    PEACEFUL_HILLS_THE = auto()
    JAM_ROBBERS = auto()
    PICNIC_TRICKS = auto()
    VOLCANO_VALLEY = auto()
    IF_THE_HAT_FITS = auto()
    DONALDS_POSY_PATCH = auto()
    DONALD_MINES_HIS_OWN_BUSINESS = auto()
    MAGICAL_MISERY = auto()
    THREE_GOOD_LITTLE_DUCKS = auto()
    VACATION_MISERY = auto()
    ADVENTURE_DOWN_UNDER = auto()
    GHOST_OF_THE_GROTTO_THE = auto()
    WALTZ_KING_THE = auto()
    MASTERS_OF_MELODY_THE = auto()
    FIREMAN_DONALD = auto()
    CHRISTMAS_ON_BEAR_MOUNTAIN = auto()
    FASHION_IN_FLIGHT = auto()
    TURN_FOR_THE_WORSE = auto()
    MACHINE_MIX_UP = auto()
    TERRIBLE_TURKEY_THE = auto()
    WINTERTIME_WAGER = auto()
    WATCHING_THE_WATCHMAN = auto()
    DARKEST_AFRICA = auto()
    WIRED = auto()
    GOING_APE = auto()
    OLD_CASTLES_SECRET_THE = auto()
    SPOIL_THE_ROD = auto()
    BIRD_WATCHING = auto()
    HORSESHOE_LUCK = auto()
    BEAN_TAKEN = auto()
    ROCKET_RACE_TO_THE_MOON = auto()
    DONALD_OF_THE_COAST_GUARD = auto()
    GLADSTONE_RETURNS = auto()
    SHERIFF_OF_BULLET_VALLEY = auto()
    LINKS_HIJINKS = auto()
    SORRY_TO_BE_SAFE = auto()
    BEST_LAID_PLANS = auto()
    GENUINE_ARTICLE_THE = auto()
    PEARLS_OF_WISDOM = auto()
    FOXY_RELATIONS = auto()
    CRAZY_QUIZ_SHOW_THE = auto()
    GOLDEN_CHRISTMAS_TREE_THE = auto()
    TOYLAND = auto()
    JUMPING_TO_CONCLUSIONS = auto()
    TRUE_TEST_THE = auto()
    ORNAMENTS_ON_THE_WAY = auto()
    TRUANT_OFFICER_DONALD = auto()
    DONALD_DUCKS_WORST_NIGHTMARE = auto()
    PIZEN_SPRING_DUDE_RANCH = auto()
    RIVAL_BEACHCOMBERS = auto()
    LOST_IN_THE_ANDES = auto()
    TOO_FIT_TO_FIT = auto()
    TUNNEL_VISION = auto()
    SLEEPY_SITTERS = auto()
    SUNKEN_YACHT_THE = auto()
    RACE_TO_THE_SOUTH_SEAS = auto()
    MANAGING_THE_ECHO_SYSTEM = auto()
    PLENTY_OF_PETS = auto()
    VOODOO_HOODOO = auto()
    SLIPPERY_SHINE = auto()
    FRACTIOUS_FUN = auto()
    KING_SIZE_CONE = auto()
    SUPER_SNOOPER = auto()
    GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE = auto()
    DOWSING_DUCKS = auto()
    GOLDILOCKS_GAMBIT_THE = auto()
    LETTER_TO_SANTA = auto()
    LUCK_OF_THE_NORTH = auto()
    NEW_TOYS = auto()
    TOASTY_TOYS = auto()
    NO_PLACE_TO_HIDE = auto()
    TIED_DOWN_TOOLS = auto()
    NO_NOISE_IS_GOOD_NOISE = auto()
    DONALDS_LOVE_LETTERS = auto()
    RIP_VAN_DONALD = auto()
    TRAIL_OF_THE_UNICORN = auto()
    LAND_OF_THE_TOTEM_POLES = auto()
    NOISE_NULLIFIER = auto()
    MATINEE_MADNESS = auto()
    FETCHING_PRICE_A = auto()
    SERUM_TO_CODFISH_COVE = auto()
    WILD_ABOUT_FLOWERS = auto()
    IN_ANCIENT_PERSIA = auto()
    VACATION_TIME = auto()
    DONALDS_GRANDMA_DUCK = auto()
    CAMP_COUNSELOR = auto()
    PIXILATED_PARROT_THE = auto()
    MAGIC_HOURGLASS_THE = auto()
    BIG_TOP_BEDLAM = auto()
    YOU_CANT_GUESS = auto()
    DANGEROUS_DISGUISE = auto()
    NO_SUCH_VARMINT = auto()
    BILLIONS_TO_SNEEZE_AT = auto()
    OPERATION_ST_BERNARD = auto()
    FINANCIAL_FABLE_A = auto()
    APRIL_FOOLERS_THE = auto()
    IN_OLD_CALIFORNIA = auto()
    KNIGHTLY_RIVALS = auto()
    POOL_SHARKS = auto()
    TROUBLE_WITH_DIMES_THE = auto()
    GLADSTONES_LUCK = auto()
    TEN_STAR_GENERALS = auto()
    CHRISTMAS_FOR_SHACKTOWN_A = auto()
    ATTIC_ANTICS = auto()
    TRUANT_NEPHEWS_THE = auto()
    TERROR_OF_THE_BEAGLE_BOYS = auto()
    TREEING_OFF = auto()
    CHRISTMAS_KISS = auto()
    PROJECTING_DESIRES = auto()
    BIG_BIN_ON_KILLMOTOR_HILL_THE = auto()
    GLADSTONES_USUAL_VERY_GOOD_YEAR = auto()
    SCREAMING_COWBOY_THE = auto()
    STATUESQUE_SPENDTHRIFTS = auto()
    ROCKET_WING_SAVES_THE_DAY = auto()
    GLADSTONES_TERRIBLE_SECRET = auto()
    ONLY_A_POOR_OLD_MAN = auto()
    OSOGOOD_SILVER_POLISH = auto()
    COFFEE_FOR_TWO = auto()
    SOUPLINE_EIGHT = auto()
    THINK_BOX_BOLLIX_THE = auto()
    GOLDEN_HELMET_THE = auto()
    FULL_SERVICE_WINDOWS = auto()
    RIGGED_UP_ROLLER = auto()
    AWASH_IN_SUCCESS = auto()
    HOUSEBOAT_HOLIDAY = auto()
    GEMSTONE_HUNTERS = auto()
    GILDED_MAN_THE = auto()
    STABLE_PRICES = auto()
    ARMORED_RESCUE = auto()
    CRAFTY_CORNER = auto()
    SPENDING_MONEY = auto()
    HYPNO_GUN_THE = auto()
    TRICK_OR_TREAT = auto()
    PRANK_ABOVE_A = auto()
    FRIGHTFUL_FACE = auto()
    HOBBLIN_GOBLINS = auto()
    OMELET = auto()
    CHARITABLE_CHORE_A = auto()
    TURKEY_WITH_ALL_THE_SCHEMINGS = auto()
    FLIP_DECISION = auto()
    MY_LUCKY_VALENTINE = auto()
    SOMETHIN_FISHY_HERE = auto()
    BACK_TO_THE_KLONDIKE = auto()
    FARE_DELAY = auto()
    MONEY_LADDER_THE = auto()
    CHECKER_GAME_THE = auto()
    EASTER_ELECTION_THE = auto()
    TALKING_DOG_THE = auto()
    WORM_WEARY = auto()
    MUCH_ADO_ABOUT_QUACKLY_HALL = auto()
    SOME_HEIR_OVER_THE_RAINBOW = auto()
    MASTER_RAINMAKER_THE = auto()
    MONEY_STAIRS_THE = auto()
    HORSERADISH_STORY_THE = auto()
    ROUND_MONEY_BIN_THE = auto()
    BARBER_COLLEGE = auto()
    FOLLOW_THE_RAINBOW = auto()
    ITCHING_TO_SHARE = auto()
    BEE_BUMBLES = auto()
    WISPY_WILLIE = auto()
    HAMMY_CAMEL_THE = auto()
    FIX_UP_MIX_UP = auto()
    BALLET_EVASIONS = auto()
    CHEAPEST_WEIGH_THE = auto()
    BUM_STEER = auto()
    MENEHUNE_MYSTERY_THE = auto()
    TURKEY_TROT_AT_ONE_WHISTLE = auto()
    RAFFLE_REVERSAL = auto()
    SECRET_OF_ATLANTIS_THE = auto()
    HOSPITALITY_WEEK = auto()
    MCDUCK_TAKES_A_DIVE = auto()
    SLIPPERY_SIPPER = auto()
    FLOUR_FOLLIES = auto()
    PRICE_OF_FAME_THE = auto()
    MIDGETS_MADNESS = auto()
    SALMON_DERBY = auto()
    TRALLA_LA = auto()
    OIL_THE_NEWS = auto()
    DIG_IT = auto()
    MENTAL_FEE = auto()
    OUTFOXED_FOX = auto()
    CHELTENHAMS_CHOICE = auto()
    TRAVELLING_TRUANTS = auto()
    RANTS_ABOUT_ANTS = auto()
    SEVEN_CITIES_OF_CIBOLA_THE = auto()
    MILLION_DOLLAR_PIGEON = auto()
    TEMPER_TAMPERING = auto()
    WRONG_NUMBER = auto()
    DINER_DILEMMA = auto()
    TOO_SAFE_SAFE = auto()
    SEARCH_FOR_THE_CUSPIDORIA = auto()
    NEW_YEARS_REVOLUTIONS = auto()
    ICEBOAT_TO_BEAVER_ISLAND = auto()
    MYSTERIOUS_STONE_RAY_THE = auto()
    CAMPAIGN_OF_NOTE_A = auto()
    CASH_ON_THE_BRAIN = auto()
    CLASSY_TAXI = auto()
    BLANKET_INVESTMENT = auto()
    DAFFY_TAFFY_PULL_THE = auto()
    TUCKERED_TIGER_THE = auto()
    DONALD_DUCK_TELLS_ABOUT_KITES = auto()
    LEMMING_WITH_THE_LOCKET_THE = auto()
    EASY_MOWING = auto()
    SKI_LIFT_LETDOWN = auto()
    CAST_OF_THOUSANDS = auto()
    GHOST_SHERIFF_OF_LAST_GASP_THE = auto()
    DESCENT_INTERVAL_A = auto()
    SECRET_OF_HONDORICA = auto()
    DOGCATCHER_DUCK = auto()
    COURTSIDE_HEATING = auto()
    POWER_PLOWING = auto()
    REMEMBER_THIS = auto()
    FABULOUS_PHILOSOPHERS_STONE_THE = auto()
    HEIRLOOM_WATCH = auto()
    DONALDS_RAUCOUS_ROLE = auto()
    GOOD_CANOES_AND_BAD_CANOES = auto()
    DEEP_DECISION = auto()
    SMASH_SUCCESS = auto()
    TROUBLE_INDEMNITY = auto()
    CHICKADEE_CHALLENGE_THE = auto()
    UNORTHODOX_OX_THE = auto()
    GREAT_STEAMBOAT_RACE_THE = auto()
    LUNCHEON_LAMENT = auto()
    COME_AS_YOU_ARE = auto()
    ROUNDABOUT_HANDOUT = auto()
    RICHES_RICHES_EVERYWHERE = auto()
    CUSTARD_GUN_THE = auto()
    THREE_UN_DUCKS = auto()
    SECRET_RESOLUTIONS = auto()
    ICE_TAXIS_THE = auto()
    SEARCHING_FOR_A_SUCCESSOR = auto()
    OLYMPIC_HOPEFUL_THE = auto()
    GOLDEN_FLEECING_THE = auto()
    WATT_AN_OCCASION = auto()
    DOUGHNUT_DARE = auto()
    SWEAT_DEAL_A = auto()
    GOPHER_GOOF_UPS = auto()
    IN_THE_SWIM = auto()
    LAND_BENEATH_THE_GROUND = auto()
    TRAPPED_LIGHTNING = auto()
    ART_OF_SECURITY_THE = auto()
    FASHION_FORECAST = auto()
    MUSH = auto()
    CAMPING_CONFUSION = auto()
    MASTER_THE = auto()
    WHALE_OF_A_STORY_A = auto()
    SMOKE_WRITER_IN_THE_SKY = auto()
    INVENTOR_OF_ANYTHING = auto()
    LOST_CROWN_OF_GENGHIS_KHAN_THE = auto()
    FAULTY_FORTUNE = auto()
    RUNAWAY_TRAIN_THE = auto()
    GOLD_RUSH = auto()
    FIREFLIES_ARE_FREE = auto()
    EARLY_TO_BUILD = auto()
    STATUES_OF_LIMITATIONS = auto()
    BORDERLINE_HERO = auto()
    SECOND_RICHEST_DUCK_THE = auto()
    MIGRATING_MILLIONS = auto()
    CAT_BOX_THE = auto()
    CHINA_SHOP_SHAKEUP = auto()
    BUFFO_OR_BUST = auto()
    POUND_FOR_SOUND = auto()
    FERTILE_ASSETS = auto()
    GRANDMAS_PRESENT = auto()
    KNIGHT_IN_SHINING_ARMOR = auto()
    FEARSOME_FLOWERS = auto()
    DONALDS_PET_SERVICE = auto()
    BACK_TO_LONG_AGO = auto()
    COLOSSALEST_SURPRISE_QUIZ_SHOW_THE = auto()
    FORECASTING_FOLLIES = auto()
    BACKYARD_BONANZA = auto()
    ALL_SEASON_HAT = auto()
    EYES_HAVE_IT_THE = auto()
    RELATIVE_REACTION = auto()
    SECRET_BOOK_THE = auto()
    TREE_TRICK = auto()
    FISHING_MYSTERY = auto()
    IN_KAKIMAW_COUNTRY = auto()
    LOST_PEG_LEG_MINE_THE = auto()
    LOSING_FACE = auto()
    DAY_DUCKBURG_GOT_DYED_THE = auto()
    PICNIC = auto()
    COLD_BARGAIN_A = auto()
    GYROS_IMAGINATION_INVENTION = auto()
    RED_APPLE_SAP = auto()
    SURE_FIRE_GOLD_FINDER_THE = auto()
    SPECIAL_DELIVERY = auto()
    CODE_OF_DUCKBURG_THE = auto()
    LAND_OF_THE_PYGMY_INDIANS = auto()
    NET_WORTH = auto()
    FORBIDDEN_VALLEY = auto()
    FANTASTIC_RIVER_RACE_THE = auto()
    SAGMORE_SPRINGS_HOTEL = auto()
    TENDERFOOT_TRAP_THE = auto()
    MINES_OF_KING_SOLOMON_THE = auto()
    GYRO_BUILDS_A_BETTER_HOUSE = auto()
    HISTORY_TOSSED = auto()
    BLACK_PEARLS_OF_TABU_YAMA_THE = auto()
    AUGUST_ACCIDENT = auto()
    SEPTEMBER_SCRIMMAGE = auto()
    WISHING_STONE_ISLAND = auto()
    ROCKET_RACE_AROUND_THE_WORLD = auto()
    ROSCOE_THE_ROBOT = auto()
    CITY_OF_GOLDEN_ROOFS = auto()
    DOGGED_DETERMINATION = auto()
    FORGOTTEN_PRECAUTION = auto()
    BIG_BOBBER_THE = auto()
    WINDFALL_OF_THE_MIND = auto()
    GETTING_THOR = auto()
    TITANIC_ANTS_THE = auto()
    RESCUE_ENHANCEMENT = auto()
    PERSISTENT_POSTMAN_THE = auto()
    HALF_BAKED_BAKER_THE = auto()
    DODGING_MISS_DAISY = auto()
    MONEY_WELL_THE = auto()
    MILKMAN_THE = auto()
    MOCKING_BIRD_RIDGE = auto()
    OLD_FROGGIE_CATAPULT = auto()
    DRAMATIC_DONALD = auto()
    GOING_TO_PIECES = auto()
    HIGH_RIDER = auto()
    THAT_SINKING_FEELING = auto()
    WATER_SKI_RACE = auto()
    BALMY_SWAMI_THE = auto()
    WINDY_STORY_THE = auto()
    ALL_CHOKED_UP = auto()
    GOLDEN_RIVER_THE = auto()
    MOOLA_ON_THE_MOVE = auto()
    THUMBS_UP = auto()
    KNOW_IT_ALL_MACHINE_THE = auto()
    STRANGE_SHIPWRECKS_THE = auto()
    FABULOUS_TYCOON_THE = auto()
    GYRO_GOES_FOR_A_DIP = auto()
    BILL_WIND = auto()
    TWENTY_FOUR_CARAT_MOON_THE = auto()
    HOUSE_ON_CYCLONE_HILL_THE = auto()
    FORBIDIUM_MONEY_BIN_THE = auto()
    NOBLE_PORPOISES = auto()
    MAGIC_INK_THE = auto()
    SLEEPIES_THE = auto()
    TRACKING_SANDY = auto()
    LITTLEST_CHICKEN_THIEF_THE = auto()
    BEACHCOMBERS_PICNIC_THE = auto()
    LIGHTS_OUT = auto()
    CHRISTMAS_IN_DUCKBURG = auto()
    ROCKET_ROASTED_CHRISTMAS_TURKEY = auto()
    MASTER_MOVER_THE = auto()
    SPRING_FEVER = auto()
    FLYING_DUTCHMAN_THE = auto()
    PYRAMID_SCHEME = auto()
    WISHING_WELL_THE = auto()
    RETURN_TO_PIZEN_BLUFF = auto()
    KRANKENSTEIN_GYRO = auto()
    MONEY_CHAMP_THE = auto()
    HIS_HANDY_ANDY = auto()
    FIREFLY_TRACKER_THE = auto()
    PRIZE_OF_PIZARRO_THE = auto()
    LOVELORN_FIREMAN_THE = auto()
    IMMOVABLE_MISER = auto()
    KITTY_GO_ROUND = auto()
    POOR_LOSER = auto()
    FLOATING_ISLAND_THE = auto()
    CRAWLS_FOR_CASH = auto()
    BLACK_FOREST_RESCUE_THE = auto()
    GOOD_DEEDS_THE = auto()
    BLACK_WEDNESDAY = auto()
    WATCHFUL_PARENTS_THE = auto()
    WAX_MUSEUM_THE = auto()
    PAUL_BUNYAN_MACHINE_THE = auto()
    PIED_PIPER_OF_DUCKBURG_THE = auto()
    PIED_PIPER_OF_DUCKBURG = auto()  # Jippes version
    FUN_WHATS_THAT = auto()
    WITCHING_STICK_THE = auto()
    INVENTORS_CONTEST_THE = auto()
    JUNGLE_HI_JINKS = auto()
    MASTERING_THE_MATTERHORN = auto()
    ON_THE_DREAM_PLANET = auto()
    TRAIL_TYCOON = auto()
    FLYING_FARMHAND_THE = auto()
    HONEY_OF_A_HEN_A = auto()
    WEATHER_WATCHERS_THE = auto()
    SHEEPISH_COWBOYS_THE = auto()
    GAB_MUFFER_THE = auto()
    BIRD_CAMERA_THE = auto()
    ODD_ORDER_THE = auto()
    STUBBORN_STORK_THE = auto()
    MILKTIME_MELODIES = auto()
    LOST_RABBIT_FOOT_THE = auto()
    OODLES_OF_OOMPH = auto()
    DAISYS_DAZED_DAYS = auto()
    LIBRARIAN_THE = auto()
    DOUBLE_DATE_THE = auto()
    TV_BABYSITTER_THE = auto()
    BEAUTY_QUEEN_THE = auto()
    TIGHT_SHOES = auto()
    FRAMED_MIRROR_THE = auto()
    NEW_GIRL_THE = auto()
    MASTER_GLASSER_THE = auto()
    MONEY_HAT_THE = auto()
    CHRISTMAS_CHA_CHA_THE = auto()
    DONALDS_PARTY = auto()
    ISLAND_IN_THE_SKY = auto()
    UNDER_THE_POLAR_ICE = auto()
    HOUND_OF_THE_WHISKERVILLES = auto()
    TOUCHE_TOUPEE = auto()
    FREE_SKI_SPREE = auto()
    MOPPING_UP = auto()
    SNOW_CHASER_THE = auto()
    KNIGHTS_OF_THE_FLYING_SLEDS = auto()
    RIDING_THE_PONY_EXPRESS = auto()
    CAVE_OF_THE_WINDS = auto()
    MADBALL_PITCHER_THE = auto()
    MIXED_UP_MIXER = auto()
    WANT_TO_BUY_AN_ISLAND = auto()
    FROGGY_FARMER = auto()
    CALL_OF_THE_WILD_THE = auto()
    TALE_OF_THE_TAPE = auto()
    HIS_SHINING_HOUR = auto()
    BEAR_TAMER_THE = auto()
    PIPELINE_TO_DANGER = auto()
    YOICKS_THE_FOX = auto()
    WAR_PAINT = auto()
    DOG_SITTER_THE = auto()
    MYSTERY_OF_THE_LOCH = auto()
    VILLAGE_BLACKSMITH_THE = auto()
    FRAIDY_FALCON_THE = auto()
    ROCKS_TO_RICHES = auto()
    ALL_AT_SEA = auto()
    FISHY_WARDEN = auto()
    TWO_WAY_LUCK = auto()
    BALLOONATICS = auto()
    TURKEY_TROUBLE = auto()
    MISSILE_FIZZLE = auto()
    SITTING_HIGH = auto()
    THATS_NO_FABLE = auto()
    CLOTHES_MAKE_THE_DUCK = auto()
    STICKY_SITUATION_A = auto()
    RING_LEADER_ROUNDUP = auto()
    TOO_MUCH_HELP = auto()
    RULING_THE_ROOST = auto()
    DARINGLY_DIFFERENT = auto()
    SMALL_FRYERS = auto()
    FALSE_FLATTERY = auto()
    FRIENDLY_ENEMY = auto()
    UNDERCOVER_GIRL = auto()
    INVENTIVE_GENTLEMAN_THE = auto()
    THAT_SMALL_FEELING = auto()
    MADCAP_MARINER_THE = auto()
    TERRIBLE_TOURIST = auto()
    THRIFT_GIFT_A = auto()
    LOST_FRONTIER = auto()
    WHOLE_HERD_OF_HELP_THE = auto()
    DAY_THE_FARM_STOOD_STILL_THE = auto()
    TRAINING_FARM_FUSS_THE = auto()
    REVERSED_RESCUE_THE = auto()
    YOU_CANT_WIN = auto()
    BILLIONS_IN_THE_HOLE = auto()
    BONGO_ON_THE_CONGO = auto()
    MONSTERVILLE = auto()
    CUBE_THE = auto()
    MIGHTY_BUT_MISERABLE = auto()
    BRAIN_STRAIN = auto()
    NOSE_KNOWS_THE = auto()
    OLD_TIMER_THE = auto()
    MECHANIZED_MESS = auto()
    STRANGER_THAN_FICTION = auto()
    BOXED_IN = auto()
    CHUGWAGON_DERBY = auto()
    MYTHTIC_MYSTERY = auto()
    WILY_RIVAL = auto()
    DUCK_LUCK = auto()
    MR_PRIVATE_EYE = auto()
    HOUND_HOUNDER = auto()
    GOLDEN_NUGGET_BOAT_THE = auto()
    FAST_AWAY_CASTAWAY = auto()
    GIFT_LION = auto()
    JET_WITCH = auto()
    BOAT_BUSTER = auto()
    MIDAS_TOUCH_THE = auto()
    MONEY_BAG_GOAT = auto()
    DUCKBURGS_DAY_OF_PERIL = auto()
    NORTHEASTER_ON_CAPE_QUACK = auto()
    MOVIE_MAD = auto()
    TEN_CENT_VALENTINE = auto()
    BUFFALOED_BY_BUFFALOES = auto()
    CAVE_OF_ALI_BABA = auto()
    DEEP_DOWN_DOINGS = auto()
    GREAT_POP_UP_THE = auto()
    JUNGLE_BUNGLE = auto()
    MERRY_FERRY = auto()
    UNSAFE_SAFE_THE = auto()
    MUCH_LUCK_MCDUCK = auto()
    UNCLE_SCROOGE___MONKEY_BUSINESS = auto()
    COLLECTION_DAY = auto()
    SEEING_IS_BELIEVING = auto()
    PLAYMATES = auto()
    RAGS_TO_RICHES = auto()
    ART_APPRECIATION = auto()
    FLOWERS_ARE_FLOWERS = auto()
    MADCAP_INVENTORS = auto()
    MEDALING_AROUND = auto()
    WAY_OUT_YONDER = auto()
    CANDY_KID_THE = auto()
    SPICY_TALE_A = auto()
    FINNY_FUN = auto()
    GETTING_THE_BIRD = auto()
    NEST_EGG_COLLECTOR = auto()
    MILLION_DOLLAR_SHOWER = auto()
    TRICKY_EXPERIMENT = auto()
    MASTER_WRECKER = auto()
    RAVEN_MAD = auto()
    STALWART_RANGER = auto()
    LOG_JOCKEY = auto()
    SNOW_DUSTER = auto()
    ODDBALL_ODYSSEY = auto()
    POSTHASTY_POSTMAN = auto()
    STATUS_SEEKER_THE = auto()
    CHRISTMAS_CHEERS = auto()
    MATTER_OF_FACTORY_A = auto()
    JINXED_JALOPY_RACE_THE = auto()
    FOR_OLD_DIMES_SAKE = auto()
    STONES_THROW_FROM_GHOST_TOWN_A = auto()
    SPARE_THAT_HAIR = auto()
    DUCKS_EYE_VIEW_OF_EUROPE_A = auto()
    CASE_OF_THE_STICKY_MONEY_THE = auto()
    DUELING_TYCOONS = auto()
    WISHFUL_EXCESS = auto()
    SIDEWALK_OF_THE_MIND = auto()
    NO_BARGAIN = auto()
    UP_AND_AT_IT = auto()
    GALL_OF_THE_WILD = auto()
    ZERO_HERO = auto()
    BEACH_BOY = auto()
    CROWN_OF_THE_MAYAS = auto()
    INVISIBLE_INTRUDER_THE = auto()
    ISLE_OF_GOLDEN_GEESE = auto()
    TRAVEL_TIGHTWAD_THE = auto()
    DUCKBURG_PET_PARADE_THE = auto()
    HELPERS_HELPING_HAND_A = auto()
    HAVE_GUN_WILL_DANCE = auto()
    LOST_BENEATH_THE_SEA = auto()
    LEMONADE_FLING_THE = auto()
    FIREMAN_SCROOGE = auto()
    SAVED_BY_THE_BAG = auto()
    ONCE_UPON_A_CARNIVAL = auto()
    DOUBLE_MASQUERADE = auto()
    MAN_VERSUS_MACHINE = auto()
    IT_HAPPENED_ONE_WINTER = auto()
    THRIFTY_SPENDTHRIFT_THE = auto()
    FEUD_AND_FAR_BETWEEN = auto()
    BUBBLEWEIGHT_CHAMP = auto()
    JONAH_GYRO = auto()
    MANY_FACES_OF_MAGICA_DE_SPELL_THE = auto()
    CAPN_BLIGHTS_MYSTERY_SHIP = auto()
    LOONY_LUNAR_GOLD_RUSH_THE = auto()
    OLYMPIAN_TORCH_BEARER_THE = auto()
    RUG_RIDERS_IN_THE_SKY = auto()
    HOW_GREEN_WAS_MY_LETTUCE = auto()
    GREAT_WIG_MYSTERY_THE = auto()
    HERO_OF_THE_DIKE = auto()
    INTERPLANETARY_POSTMAN = auto()
    UNFRIENDLY_ENEMIES = auto()
    BILLION_DOLLAR_SAFARI_THE = auto()
    DELIVERY_DILEMMA = auto()
    INSTANT_HERCULES = auto()
    MCDUCK_OF_ARABIA = auto()
    TICKING_DETECTOR = auto()
    MYSTERY_OF_THE_GHOST_TOWN_RAILROAD = auto()
    DUCK_OUT_OF_LUCK = auto()
    LOCK_OUT_THE = auto()
    BIGGER_THE_BEGGAR_THE = auto()
    PLUMMETING_WITH_PRECISION = auto()
    SNAKE_TAKE = auto()
    SWAMP_OF_NO_RETURN_THE = auto()
    MONKEY_BUSINESS = auto()
    GIANT_ROBOT_ROBBERS_THE = auto()
    LAUNDRY_FOR_LESS = auto()
    LONG_DISTANCE_COLLISION = auto()
    TOP_WAGES = auto()
    NORTH_OF_THE_YUKON = auto()
    DOWN_FOR_THE_COUNT = auto()
    WASTED_WORDS = auto()
    PHANTOM_OF_NOTRE_DUCK_THE = auto()
    SO_FAR_AND_NO_SAFARI = auto()
    QUEEN_OF_THE_WILD_DOG_PACK_THE = auto()
    HOUSE_OF_HAUNTS = auto()
    TREASURE_OF_MARCO_POLO = auto()
    BEAUTY_BUSINESS_THE = auto()
    MICRO_DUCKS_FROM_OUTER_SPACE = auto()
    NOT_SO_ANCIENT_MARINER_THE = auto()
    HEEDLESS_HORSEMAN_THE = auto()
    DOOM_DIAMOND_THE = auto()
    HALL_OF_THE_MERMAID_QUEEN = auto()
    CATTLE_KING_THE = auto()
    KING_SCROOGE_THE_FIRST = auto()
    PAWNS_OF_THE_LOUP_GAROU = auto()
    OFFICER_OF_THE_DAY = auto()
    PERIL_OF_THE_BLACK_FOREST = auto()
    LIFE_SAVERS = auto()
    WHALE_OF_A_GOOD_DEED = auto()
    BAD_DAY_FOR_TROOP_A = auto()
    DAY_IN_A_DUCKS_LIFE_A = auto()
    LET_SLEEPING_BONES_LIE = auto()
    SAVIORS_OF_THE_LAKE = auto()
    BOTTLED_BATTLERS = auto()
    MAPLE_SUGAR_TIME_HOW_SWEET_IT_IS = auto()
    TRAITOR_IN_THE_RANKS = auto()
    EAGLE_SAVERS = auto()
    STORM_DANCERS = auto()
    HOUND_OF_THE_MOANING_HILLS = auto()
    DAY_THE_MOUNTAIN_SHOOK_THE = auto()
    GOLD_OF_THE_49ERS = auto()
    DUCKMADE_DISASTER = auto()
    WAILING_WHALERS = auto()
    WHERE_THERES_SMOKE = auto()
    BE_LEERY_OF_LAKE_EERIE = auto()
    TEAHOUSE_OF_THE_WAGGIN_DRAGON = auto()
    NEW_ZOO_BREWS_ADO = auto()
    MUSIC_HATH_CHARMS = auto()
    PHANTOM_JOKER_THE = auto()
    HARK_HARK_THE_ARK = auto()
    CAPTAINS_OUTRAGEOUS = auto()
    # Covers (assigned titles; see barks_covers.py).
    FOUR_COLOR_189_COVER = auto()
    COMICS_AND_STORIES_95_COVER = auto()
    COMICS_AND_STORIES_96_COVER = auto()
    FOUR_COLOR_199_COVER = auto()
    FOUR_COLOR_203_COVER = auto()
    FOUR_COLOR_223_COVER = auto()
    COMICS_AND_STORIES_104_COVER = auto()
    COMICS_AND_STORIES_108_COVER = auto()
    FOUR_COLOR_238_COVER = auto()
    COMICS_AND_STORIES_109_COVER = auto()
    FOUR_COLOR_256_COVER = auto()
    FOUR_COLOR_263_COVER = auto()
    FOUR_COLOR_275_COVER = auto()
    FOUR_COLOR_282_COVER = auto()
    COMICS_AND_STORIES_130_COVER = auto()
    COMICS_AND_STORIES_131_COVER = auto()
    COMICS_AND_STORIES_132_COVER = auto()
    FOUR_COLOR_353_COVER = auto()
    FOUR_COLOR_348_COVER = auto()
    COMICS_AND_STORIES_133_COVER = auto()
    COMICS_AND_STORIES_134_COVER = auto()
    COMICS_AND_STORIES_135_COVER = auto()
    COMICS_AND_STORIES_139_COVER = auto()
    FOUR_COLOR_356_COVER = auto()
    FOUR_COLOR_367_COVER = auto()
    COMICS_AND_STORIES_136_COVER = auto()
    FOUR_COLOR_386_COVER = auto()
    COMICS_AND_STORIES_141_COVER = auto()
    FOUR_COLOR_394_COVER = auto()
    FOUR_COLOR_408_COVER = auto()
    COMICS_AND_STORIES_143_COVER = auto()
    COMICS_AND_STORIES_144_COVER = auto()
    COMICS_AND_STORIES_145_COVER = auto()
    COMICS_AND_STORIES_146_COVER = auto()
    FOUR_COLOR_422_COVER = auto()
    DONALD_DUCK_26_COVER = auto()
    DONALD_DUCK_27_COVER = auto()
    FOUR_COLOR_450_COVER = auto()
    COMICS_AND_STORIES_147_COVER = auto()
    COMICS_AND_STORIES_148_COVER = auto()
    COMICS_AND_STORIES_149_COVER = auto()
    COMICS_AND_STORIES_152_COVER = auto()
    DONALD_DUCK_28_COVER = auto()
    FOUR_COLOR_456_COVER = auto()
    COMICS_AND_STORIES_150_COVER = auto()
    COMICS_AND_STORIES_151_COVER = auto()
    COMICS_AND_STORIES_153_COVER = auto()
    COMICS_AND_STORIES_154_COVER = auto()
    DONALD_DUCK_29_COVER = auto()
    DONALD_DUCK_30_COVER = auto()
    COMICS_AND_STORIES_155_COVER = auto()
    COMICS_AND_STORIES_158_COVER = auto()
    FOUR_COLOR_495_COVER = auto()
    COMICS_AND_STORIES_157_COVER = auto()
    COMICS_AND_STORIES_156_COVER = auto()
    COMICS_AND_STORIES_159_COVER = auto()
    COMICS_AND_STORIES_164_COVER = auto()
    UNCLE_SCROOGE_4_COVER = auto()
    COMICS_AND_STORIES_160_COVER = auto()
    COMICS_AND_STORIES_161_COVER = auto()
    COMICS_AND_STORIES_162_COVER = auto()
    UNCLE_SCROOGE_5_COVER = auto()
    DONALD_DUCK_35_COVER = auto()
    UNCLE_SCROOGE_7_COVER = auto()
    UNCLE_SCROOGE_8_COVER = auto()
    UNCLE_SCROOGE_9_COVER = auto()
    COMICS_AND_STORIES_163_COVER = auto()
    COMICS_AND_STORIES_166_COVER = auto()
    COMICS_AND_STORIES_168_COVER = auto()
    COMICS_AND_STORIES_165_COVER = auto()
    COMICS_AND_STORIES_176_COVER = auto()
    COMICS_AND_STORIES_167_COVER = auto()
    COMICS_AND_STORIES_171_COVER = auto()
    COMICS_AND_STORIES_169_COVER = auto()
    COMICS_AND_STORIES_170_COVER = auto()
    COMICS_AND_STORIES_172_COVER = auto()
    COMICS_AND_STORIES_173_COVER = auto()
    UNCLE_SCROOGE_10_COVER = auto()
    COMICS_AND_STORIES_174_COVER = auto()
    COMICS_AND_STORIES_175_COVER = auto()
    COMICS_AND_STORIES_177_COVER = auto()
    COMICS_AND_STORIES_178_COVER = auto()
    UNCLE_SCROOGE_11_COVER = auto()
    UNCLE_SCROOGE_12_COVER = auto()
    DONALD_DUCK_44_COVER = auto()
    COMICS_AND_STORIES_183_COVER = auto()
    UNCLE_SCROOGE_13_COVER = auto()
    DONALD_DUCK_46_COVER = auto()
    UNCLE_SCROOGE_15_COVER = auto()
    UNCLE_SCROOGE_14_COVER = auto()
    UNCLE_SCROOGE_16_BACK_COVER = auto()
    UNCLE_SCROOGE_17_COVER = auto()
    UNCLE_SCROOGE_18_COVER = auto()
    DONALD_DUCK_52_COVER = auto()
    COMICS_AND_STORIES_198_COVER = auto()
    COMICS_AND_STORIES_199_COVER = auto()
    DONALD_DUCK_55_COVER = auto()
    UNCLE_SCROOGE_19_COVER = auto()
    COMICS_AND_STORIES_200_COVER = auto()
    COMICS_AND_STORIES_204_COVER = auto()
    COMICS_AND_STORIES_206_COVER = auto()
    COMICS_AND_STORIES_213_COVER = auto()
    COMICS_AND_STORIES_207_COVER = auto()
    UNCLE_SCROOGE_23_COVER = auto()
    UNCLE_SCROOGE_20_COVER = auto()
    COMICS_AND_STORIES_208_COVER = auto()
    UNCLE_SCROOGE_22_COVER = auto()
    DONALD_DUCK_57_COVER = auto()
    UNCLE_SCROOGE_21_COVER = auto()
    COMICS_AND_STORIES_209_COVER = auto()
    UNCLE_SCROOGE_24_COVER = auto()
    COMICS_AND_STORIES_212_COVER = auto()
    COMICS_AND_STORIES_214_COVER = auto()
    COMICS_AND_STORIES_215_COVER = auto()
    COMICS_AND_STORIES_216_COVER = auto()
    COMICS_AND_STORIES_218_COVER = auto()
    COMICS_AND_STORIES_220_COVER = auto()
    DONALD_DUCK_65_COVER = auto()
    UNCLE_SCROOGE_25_COVER = auto()
    UNCLE_SCROOGE_30_COVER = auto()
    COMICS_AND_STORIES_226_COVER = auto()
    UNCLE_SCROOGE_26_COVER = auto()
    UNCLE_SCROOGE_27_COVER = auto()
    COMICS_AND_STORIES_228_COVER = auto()
    COMICS_AND_STORIES_229_COVER = auto()
    COMICS_AND_STORIES_240_COVER = auto()
    COMICS_AND_STORIES_230_COVER = auto()
    COMICS_AND_STORIES_231_COVER = auto()
    COMICS_AND_STORIES_233_COVER = auto()
    COMICS_AND_STORIES_237_COVER = auto()
    FOUR_COLOR_1047_COVER = auto()
    FOUR_COLOR_1047_INSIDE_FRONT_COVER = auto()
    COMICS_AND_STORIES_236_COVER = auto()
    COMICS_AND_STORIES_243_COVER = auto()
    COMICS_AND_STORIES_232_COVER = auto()
    UNCLE_SCROOGE_28_COVER = auto()
    UNCLE_SCROOGE_29_COVER = auto()
    FOUR_COLOR_1073_COVER = auto()
    UNCLE_SCROOGE_32_COVER = auto()
    COMICS_AND_STORIES_235_COVER = auto()
    UNCLE_SCROOGE_31_COVER = auto()
    DONALD_DUCK_70_COVER = auto()
    FOUR_COLOR_1095_COVER = auto()
    DONALD_DUCK_71_COVER = auto()
    DONALD_DUCK_72_COVER = auto()
    FOUR_COLOR_1099_COVER = auto()
    DONALD_DUCK_73_COVER = auto()
    COMICS_AND_STORIES_238_COVER = auto()
    COMICS_AND_STORIES_242_COVER = auto()
    FOUR_COLOR_1140_COVER = auto()
    COMICS_AND_STORIES_241_COVER = auto()
    UNCLE_SCROOGE_33_COVER = auto()
    MERRY_CHRISTMAS_39_COVER = auto()
    UNCLE_DONALD_AND_HIS_NEPHEWS_FAMILY_FUN_1_COVER = auto()
    UNCLE_SCROOGE_34_COVER = auto()
    COMICS_AND_STORIES_247_COVER = auto()
    UNCLE_SCROOGE_35_COVER = auto()
    DONALD_DUCK_78_COVER = auto()
    UNCLE_SCROOGE_36_COVER = auto()
    DONALD_DUCK_77_COVER = auto()
    DONALD_DUCK_79_COVER = auto()
    COMICS_AND_STORIES_250_COVER = auto()
    COMICS_AND_STORIES_253_COVER = auto()
    FOUR_COLOR_1184_COVER = auto()
    COMICS_AND_STORIES_256_COVER = auto()
    DONALD_DUCK_80_COVER = auto()
    UNCLE_SCROOGE_37_COVER = auto()
    FOUR_COLOR_1239_COVER = auto()
    FOUR_COLOR_1267_COVER = auto()
    COMICS_AND_STORIES_261_COVER = auto()
    GYRO_GEARLOOSE_1_COVER = auto()
    COMICS_AND_STORIES_260_COVER = auto()
    UNCLE_SCROOGE_39_COVER = auto()
    DONALD_DUCK_83_COVER = auto()
    UNCLE_SCROOGE_40_COVER = auto()
    UNCLE_SCROOGE_43_COVER = auto()
    UNCLE_SCROOGE_44_COVER = auto()
    DONALD_DUCK_ALBUM_1_COVER = auto()
    COMICS_AND_STORIES_276_COVER = auto()
    UNCLE_SCROOGE_45_COVER = auto()
    COMICS_AND_STORIES_277_COVER = auto()
    COMICS_AND_STORIES_278_COVER = auto()
    UNCLE_SCROOGE_46_COVER = auto()
    COMICS_AND_STORIES_279_COVER = auto()
    COMICS_AND_STORIES_280_COVER = auto()
    UNCLE_SCROOGE_47_COVER = auto()
    COMICS_AND_STORIES_281_COVER = auto()
    COMICS_AND_STORIES_282_COVER = auto()
    UNCLE_SCROOGE_48_COVER = auto()
    COMICS_AND_STORIES_283_COVER = auto()
    UNCLE_SCROOGE_49_COVER = auto()
    UNCLE_SCROOGE_50_COVER = auto()
    UNCLE_SCROOGE_51_COVER = auto()
    UNCLE_SCROOGE_52_COVER = auto()
    COMICS_AND_STORIES_288_COVER = auto()
    UNCLE_SCROOGE_53_COVER = auto()
    COMICS_AND_STORIES_289_COVER = auto()
    UNCLE_SCROOGE_54_COVER = auto()
    COMICS_AND_STORIES_290_COVER = auto()
    COMICS_AND_STORIES_291_COVER = auto()
    COMICS_AND_STORIES_292_COVER = auto()
    UNCLE_SCROOGE_55_COVER = auto()
    UNCLE_SCROOGE_56_COVER = auto()
    UNCLE_SCROOGE_56_INSIDE_FRONT_COVER = auto()
    COMICS_AND_STORIES_295_COVER = auto()
    COMICS_AND_STORIES_296_COVER = auto()
    UNCLE_SCROOGE_57_COVER = auto()
    DONALD_DUCK_101_COVER = auto()
    COMICS_AND_STORIES_297_COVER = auto()
    UNCLE_SCROOGE_58_COVER = auto()
    COMICS_AND_STORIES_298_COVER = auto()
    UNCLE_SCROOGE_59_COVER = auto()
    DONALD_DUCK_103_COVER = auto()
    UNCLE_SCROOGE_60_COVER = auto()
    COMICS_AND_STORIES_301_COVER = auto()
    UNCLE_SCROOGE_61_COVER = auto()
    COMICS_AND_STORIES_303_COVER = auto()
    DONALD_DUCK_105_COVER = auto()
    COMICS_AND_STORIES_304_COVER = auto()
    DONALD_DUCK_106_COVER = auto()
    UNCLE_SCROOGE_62_COVER = auto()
    COMICS_AND_STORIES_306_COVER = auto()
    UNCLE_SCROOGE_63_COVER = auto()
    COMICS_AND_STORIES_307_COVER = auto()
    UNCLE_SCROOGE_64_COVER = auto()
    COMICS_AND_STORIES_309_COVER = auto()
    UNCLE_SCROOGE_65_COVER = auto()
    COMICS_AND_STORIES_310_COVER = auto()
    UNCLE_SCROOGE_66_COVER = auto()
    COMICS_AND_STORIES_313_COVER = auto()
    COMICS_AND_STORIES_314_COVER = auto()
    UNCLE_SCROOGE_70_COVER = auto()
    COMICS_AND_STORIES_315_COVER = auto()
    DONALD_DUCK_111_COVER = auto()
    COMICS_AND_STORIES_316_COVER = auto()
    UNCLE_SCROOGE_68_COVER = auto()
    UNCLE_SCROOGE_69_COVER = auto()
    COMICS_AND_STORIES_319_COVER = auto()
    COMICS_AND_STORIES_321_COVER = auto()
    COMICS_AND_STORIES_322_COVER = auto()
    UNCLE_SCROOGE_71_COVER = auto()
    COMICS_AND_STORIES_324_COVER = auto()
    COMICS_AND_STORIES_326_COVER = auto()
    COMICS_AND_STORIES_328_COVER = auto()
    COMICS_AND_STORIES_329_COVER = auto()
    COMICS_AND_STORIES_331_COVER = auto()
    COMICS_AND_STORIES_332_COVER = auto()
    COMICS_AND_STORIES_334_COVER = auto()
    COMICS_AND_STORIES_341_COVER = auto()
    COMICS_AND_STORIES_342_COVER = auto()
    DONALD_DUCK_126_COVER = auto()
    COMICS_AND_STORIES_350_COVER = auto()
    COMICS_AND_STORIES_351_COVER = auto()
    DAISY_AND_DONALD_25_COVER = auto()
    DONALD_DUCK_ALBUM_1_BACK_COVER = auto()
    HUEY_DEWEY_AND_LOUIE_JUNIOR_WOODCHUCKS_9_COVER = auto()
    UNCLE_SCROOGE_6_COVER = auto()
    UNCLE_SCROOGE_16_COVER = auto()
    UNCLE_SCROOGE_40_BACK_COVER = auto()
    COMICS_AND_STORIES_137_COVER = auto()
    COMICS_AND_STORIES_138_COVER = auto()
    COMICS_AND_STORIES_140_COVER = auto()
    COMICS_AND_STORIES_142_COVER = auto()
    COMICS_AND_STORIES_405_COVER = auto()
    # Synthetic collection (not a real Barks story) - bundles every one-pager.
    ALL_ONE_PAGERS = auto()
    # Synthetic collection (not a real Barks story) - bundles every located cover.
    ALL_COVERS = auto()
    # Not comics below!
    GEORGE_LUCAS___AN_APPRECIATION = auto()
    RICH_TOMMASO___ON_COLORING_BARKS = auto()
    DON_AULT___FANTAGRAPHICS_INTRODUCTION = auto()
    DON_AULT___LIFE_AMONG_THE_DUCKS = auto()
    MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD = auto()


assert len(Titles) == NUM_TITLES, f"{len(Titles)} != {NUM_TITLES}"

_SMALL_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "about",
        "but",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "nor",
        "of",
        "on",
        "or",
        "the",
        "to",
        "up",
        "with",
    }
)

# fmt: off
# Titles whose human-readable form cannot be derived algorithmically from the enum name
# (apostrophes, hyphens, punctuation, non-standard casing, etc.).
_TITLE_OVERRIDES: dict[str, str] = {
    # Covers - the '#<issue>' part cannot be derived from the enum name.
    "FOUR_COLOR_189_COVER": "Four Color #189 Cover",
    "COMICS_AND_STORIES_95_COVER": "Comics and Stories #95 Cover",
    "COMICS_AND_STORIES_96_COVER": "Comics and Stories #96 Cover",
    "FOUR_COLOR_199_COVER": "Four Color #199 Cover",
    "FOUR_COLOR_203_COVER": "Four Color #203 Cover",
    "FOUR_COLOR_223_COVER": "Four Color #223 Cover",
    "COMICS_AND_STORIES_104_COVER": "Comics and Stories #104 Cover",
    "COMICS_AND_STORIES_108_COVER": "Comics and Stories #108 Cover",
    "FOUR_COLOR_238_COVER": "Four Color #238 Cover",
    "COMICS_AND_STORIES_109_COVER": "Comics and Stories #109 Cover",
    "FOUR_COLOR_256_COVER": "Four Color #256 Cover",
    "FOUR_COLOR_263_COVER": "Four Color #263 Cover",
    "FOUR_COLOR_275_COVER": "Four Color #275 Cover",
    "FOUR_COLOR_282_COVER": "Four Color #282 Cover",
    "COMICS_AND_STORIES_130_COVER": "Comics and Stories #130 Cover",
    "COMICS_AND_STORIES_131_COVER": "Comics and Stories #131 Cover",
    "COMICS_AND_STORIES_132_COVER": "Comics and Stories #132 Cover",
    "FOUR_COLOR_353_COVER": "Four Color #353 Cover",
    "FOUR_COLOR_348_COVER": "Four Color #348 Cover",
    "COMICS_AND_STORIES_133_COVER": "Comics and Stories #133 Cover",
    "COMICS_AND_STORIES_134_COVER": "Comics and Stories #134 Cover",
    "COMICS_AND_STORIES_135_COVER": "Comics and Stories #135 Cover",
    "COMICS_AND_STORIES_139_COVER": "Comics and Stories #139 Cover",
    "FOUR_COLOR_356_COVER": "Four Color #356 Cover",
    "FOUR_COLOR_367_COVER": "Four Color #367 Cover",
    "COMICS_AND_STORIES_136_COVER": "Comics and Stories #136 Cover",
    "FOUR_COLOR_386_COVER": "Four Color #386 Cover",
    "COMICS_AND_STORIES_141_COVER": "Comics and Stories #141 Cover",
    "FOUR_COLOR_394_COVER": "Four Color #394 Cover",
    "FOUR_COLOR_408_COVER": "Four Color #408 Cover",
    "COMICS_AND_STORIES_143_COVER": "Comics and Stories #143 Cover",
    "COMICS_AND_STORIES_144_COVER": "Comics and Stories #144 Cover",
    "COMICS_AND_STORIES_145_COVER": "Comics and Stories #145 Cover",
    "COMICS_AND_STORIES_146_COVER": "Comics and Stories #146 Cover",
    "FOUR_COLOR_422_COVER": "Four Color #422 Cover",
    "DONALD_DUCK_26_COVER": "Donald Duck #26 Cover",
    "DONALD_DUCK_27_COVER": "Donald Duck #27 Cover",
    "FOUR_COLOR_450_COVER": "Four Color #450 Cover",
    "COMICS_AND_STORIES_147_COVER": "Comics and Stories #147 Cover",
    "COMICS_AND_STORIES_148_COVER": "Comics and Stories #148 Cover",
    "COMICS_AND_STORIES_149_COVER": "Comics and Stories #149 Cover",
    "COMICS_AND_STORIES_152_COVER": "Comics and Stories #152 Cover",
    "DONALD_DUCK_28_COVER": "Donald Duck #28 Cover",
    "FOUR_COLOR_456_COVER": "Four Color #456 Cover",
    "COMICS_AND_STORIES_150_COVER": "Comics and Stories #150 Cover",
    "COMICS_AND_STORIES_151_COVER": "Comics and Stories #151 Cover",
    "COMICS_AND_STORIES_153_COVER": "Comics and Stories #153 Cover",
    "COMICS_AND_STORIES_154_COVER": "Comics and Stories #154 Cover",
    "DONALD_DUCK_29_COVER": "Donald Duck #29 Cover",
    "DONALD_DUCK_30_COVER": "Donald Duck #30 Cover",
    "COMICS_AND_STORIES_155_COVER": "Comics and Stories #155 Cover",
    "COMICS_AND_STORIES_158_COVER": "Comics and Stories #158 Cover",
    "FOUR_COLOR_495_COVER": "Four Color #495 Cover",
    "COMICS_AND_STORIES_157_COVER": "Comics and Stories #157 Cover",
    "COMICS_AND_STORIES_156_COVER": "Comics and Stories #156 Cover",
    "COMICS_AND_STORIES_159_COVER": "Comics and Stories #159 Cover",
    "COMICS_AND_STORIES_164_COVER": "Comics and Stories #164 Cover",
    "UNCLE_SCROOGE_4_COVER": "Uncle Scrooge #4 Cover",
    "COMICS_AND_STORIES_160_COVER": "Comics and Stories #160 Cover",
    "COMICS_AND_STORIES_161_COVER": "Comics and Stories #161 Cover",
    "COMICS_AND_STORIES_162_COVER": "Comics and Stories #162 Cover",
    "UNCLE_SCROOGE_5_COVER": "Uncle Scrooge #5 Cover",
    "DONALD_DUCK_35_COVER": "Donald Duck #35 Cover",
    "UNCLE_SCROOGE_7_COVER": "Uncle Scrooge #7 Cover",
    "UNCLE_SCROOGE_8_COVER": "Uncle Scrooge #8 Cover",
    "UNCLE_SCROOGE_9_COVER": "Uncle Scrooge #9 Cover",
    "COMICS_AND_STORIES_163_COVER": "Comics and Stories #163 Cover",
    "COMICS_AND_STORIES_166_COVER": "Comics and Stories #166 Cover",
    "COMICS_AND_STORIES_168_COVER": "Comics and Stories #168 Cover",
    "COMICS_AND_STORIES_165_COVER": "Comics and Stories #165 Cover",
    "COMICS_AND_STORIES_176_COVER": "Comics and Stories #176 Cover",
    "COMICS_AND_STORIES_167_COVER": "Comics and Stories #167 Cover",
    "COMICS_AND_STORIES_171_COVER": "Comics and Stories #171 Cover",
    "COMICS_AND_STORIES_169_COVER": "Comics and Stories #169 Cover",
    "COMICS_AND_STORIES_170_COVER": "Comics and Stories #170 Cover",
    "COMICS_AND_STORIES_172_COVER": "Comics and Stories #172 Cover",
    "COMICS_AND_STORIES_173_COVER": "Comics and Stories #173 Cover",
    "UNCLE_SCROOGE_10_COVER": "Uncle Scrooge #10 Cover",
    "COMICS_AND_STORIES_174_COVER": "Comics and Stories #174 Cover",
    "COMICS_AND_STORIES_175_COVER": "Comics and Stories #175 Cover",
    "COMICS_AND_STORIES_177_COVER": "Comics and Stories #177 Cover",
    "COMICS_AND_STORIES_178_COVER": "Comics and Stories #178 Cover",
    "UNCLE_SCROOGE_11_COVER": "Uncle Scrooge #11 Cover",
    "UNCLE_SCROOGE_12_COVER": "Uncle Scrooge #12 Cover",
    "DONALD_DUCK_44_COVER": "Donald Duck #44 Cover",
    "COMICS_AND_STORIES_183_COVER": "Comics and Stories #183 Cover",
    "UNCLE_SCROOGE_13_COVER": "Uncle Scrooge #13 Cover",
    "DONALD_DUCK_46_COVER": "Donald Duck #46 Cover",
    "UNCLE_SCROOGE_15_COVER": "Uncle Scrooge #15 Cover",
    "UNCLE_SCROOGE_14_COVER": "Uncle Scrooge #14 Cover",
    "UNCLE_SCROOGE_16_BACK_COVER": "Uncle Scrooge #16 Back Cover",
    "UNCLE_SCROOGE_17_COVER": "Uncle Scrooge #17 Cover",
    "UNCLE_SCROOGE_18_COVER": "Uncle Scrooge #18 Cover",
    "DONALD_DUCK_52_COVER": "Donald Duck #52 Cover",
    "COMICS_AND_STORIES_198_COVER": "Comics and Stories #198 Cover",
    "COMICS_AND_STORIES_199_COVER": "Comics and Stories #199 Cover",
    "DONALD_DUCK_55_COVER": "Donald Duck #55 Cover",
    "UNCLE_SCROOGE_19_COVER": "Uncle Scrooge #19 Cover",
    "COMICS_AND_STORIES_200_COVER": "Comics and Stories #200 Cover",
    "COMICS_AND_STORIES_204_COVER": "Comics and Stories #204 Cover",
    "COMICS_AND_STORIES_206_COVER": "Comics and Stories #206 Cover",
    "COMICS_AND_STORIES_213_COVER": "Comics and Stories #213 Cover",
    "COMICS_AND_STORIES_207_COVER": "Comics and Stories #207 Cover",
    "UNCLE_SCROOGE_23_COVER": "Uncle Scrooge #23 Cover",
    "UNCLE_SCROOGE_20_COVER": "Uncle Scrooge #20 Cover",
    "COMICS_AND_STORIES_208_COVER": "Comics and Stories #208 Cover",
    "UNCLE_SCROOGE_22_COVER": "Uncle Scrooge #22 Cover",
    "DONALD_DUCK_57_COVER": "Donald Duck #57 Cover",
    "UNCLE_SCROOGE_21_COVER": "Uncle Scrooge #21 Cover",
    "COMICS_AND_STORIES_209_COVER": "Comics and Stories #209 Cover",
    "UNCLE_SCROOGE_24_COVER": "Uncle Scrooge #24 Cover",
    "COMICS_AND_STORIES_212_COVER": "Comics and Stories #212 Cover",
    "COMICS_AND_STORIES_214_COVER": "Comics and Stories #214 Cover",
    "COMICS_AND_STORIES_215_COVER": "Comics and Stories #215 Cover",
    "COMICS_AND_STORIES_216_COVER": "Comics and Stories #216 Cover",
    "COMICS_AND_STORIES_218_COVER": "Comics and Stories #218 Cover",
    "COMICS_AND_STORIES_220_COVER": "Comics and Stories #220 Cover",
    "DONALD_DUCK_65_COVER": "Donald Duck #65 Cover",
    "UNCLE_SCROOGE_25_COVER": "Uncle Scrooge #25 Cover",
    "UNCLE_SCROOGE_30_COVER": "Uncle Scrooge #30 Cover",
    "COMICS_AND_STORIES_226_COVER": "Comics and Stories #226 Cover",
    "UNCLE_SCROOGE_26_COVER": "Uncle Scrooge #26 Cover",
    "UNCLE_SCROOGE_27_COVER": "Uncle Scrooge #27 Cover",
    "COMICS_AND_STORIES_228_COVER": "Comics and Stories #228 Cover",
    "COMICS_AND_STORIES_229_COVER": "Comics and Stories #229 Cover",
    "COMICS_AND_STORIES_240_COVER": "Comics and Stories #240 Cover",
    "COMICS_AND_STORIES_230_COVER": "Comics and Stories #230 Cover",
    "COMICS_AND_STORIES_231_COVER": "Comics and Stories #231 Cover",
    "COMICS_AND_STORIES_233_COVER": "Comics and Stories #233 Cover",
    "COMICS_AND_STORIES_237_COVER": "Comics and Stories #237 Cover",
    "FOUR_COLOR_1047_COVER": "Four Color #1047 Cover",
    "FOUR_COLOR_1047_INSIDE_FRONT_COVER": "Four Color #1047 Inside Front Cover",
    "COMICS_AND_STORIES_236_COVER": "Comics and Stories #236 Cover",
    "COMICS_AND_STORIES_243_COVER": "Comics and Stories #243 Cover",
    "COMICS_AND_STORIES_232_COVER": "Comics and Stories #232 Cover",
    "UNCLE_SCROOGE_28_COVER": "Uncle Scrooge #28 Cover",
    "UNCLE_SCROOGE_29_COVER": "Uncle Scrooge #29 Cover",
    "FOUR_COLOR_1073_COVER": "Four Color #1073 Cover",
    "UNCLE_SCROOGE_32_COVER": "Uncle Scrooge #32 Cover",
    "COMICS_AND_STORIES_235_COVER": "Comics and Stories #235 Cover",
    "UNCLE_SCROOGE_31_COVER": "Uncle Scrooge #31 Cover",
    "DONALD_DUCK_70_COVER": "Donald Duck #70 Cover",
    "FOUR_COLOR_1095_COVER": "Four Color #1095 Cover",
    "DONALD_DUCK_71_COVER": "Donald Duck #71 Cover",
    "DONALD_DUCK_72_COVER": "Donald Duck #72 Cover",
    "FOUR_COLOR_1099_COVER": "Four Color #1099 Cover",
    "DONALD_DUCK_73_COVER": "Donald Duck #73 Cover",
    "COMICS_AND_STORIES_238_COVER": "Comics and Stories #238 Cover",
    "COMICS_AND_STORIES_242_COVER": "Comics and Stories #242 Cover",
    "FOUR_COLOR_1140_COVER": "Four Color #1140 Cover",
    "COMICS_AND_STORIES_241_COVER": "Comics and Stories #241 Cover",
    "UNCLE_SCROOGE_33_COVER": "Uncle Scrooge #33 Cover",
    "MERRY_CHRISTMAS_39_COVER": "Merry Christmas #39 Cover",
    "UNCLE_DONALD_AND_HIS_NEPHEWS_FAMILY_FUN_1_COVER": "Uncle Donald And His Nephews Family Fun #1 Cover",  # noqa: E501
    "UNCLE_SCROOGE_34_COVER": "Uncle Scrooge #34 Cover",
    "COMICS_AND_STORIES_247_COVER": "Comics and Stories #247 Cover",
    "UNCLE_SCROOGE_35_COVER": "Uncle Scrooge #35 Cover",
    "DONALD_DUCK_78_COVER": "Donald Duck #78 Cover",
    "UNCLE_SCROOGE_36_COVER": "Uncle Scrooge #36 Cover",
    "DONALD_DUCK_77_COVER": "Donald Duck #77 Cover",
    "DONALD_DUCK_79_COVER": "Donald Duck #79 Cover",
    "COMICS_AND_STORIES_250_COVER": "Comics and Stories #250 Cover",
    "COMICS_AND_STORIES_253_COVER": "Comics and Stories #253 Cover",
    "FOUR_COLOR_1184_COVER": "Four Color #1184 Cover",
    "COMICS_AND_STORIES_256_COVER": "Comics and Stories #256 Cover",
    "DONALD_DUCK_80_COVER": "Donald Duck #80 Cover",
    "UNCLE_SCROOGE_37_COVER": "Uncle Scrooge #37 Cover",
    "FOUR_COLOR_1239_COVER": "Four Color #1239 Cover",
    "FOUR_COLOR_1267_COVER": "Four Color #1267 Cover",
    "COMICS_AND_STORIES_261_COVER": "Comics and Stories #261 Cover",
    "GYRO_GEARLOOSE_1_COVER": "Gyro Gearloose #1 Cover",
    "COMICS_AND_STORIES_260_COVER": "Comics and Stories #260 Cover",
    "UNCLE_SCROOGE_39_COVER": "Uncle Scrooge #39 Cover",
    "DONALD_DUCK_83_COVER": "Donald Duck #83 Cover",
    "UNCLE_SCROOGE_40_COVER": "Uncle Scrooge #40 Cover",
    "UNCLE_SCROOGE_43_COVER": "Uncle Scrooge #43 Cover",
    "UNCLE_SCROOGE_44_COVER": "Uncle Scrooge #44 Cover",
    "DONALD_DUCK_ALBUM_1_COVER": "Donald Duck Album #1 Cover",
    "COMICS_AND_STORIES_276_COVER": "Comics and Stories #276 Cover",
    "UNCLE_SCROOGE_45_COVER": "Uncle Scrooge #45 Cover",
    "COMICS_AND_STORIES_277_COVER": "Comics and Stories #277 Cover",
    "COMICS_AND_STORIES_278_COVER": "Comics and Stories #278 Cover",
    "UNCLE_SCROOGE_46_COVER": "Uncle Scrooge #46 Cover",
    "COMICS_AND_STORIES_279_COVER": "Comics and Stories #279 Cover",
    "COMICS_AND_STORIES_280_COVER": "Comics and Stories #280 Cover",
    "UNCLE_SCROOGE_47_COVER": "Uncle Scrooge #47 Cover",
    "COMICS_AND_STORIES_281_COVER": "Comics and Stories #281 Cover",
    "COMICS_AND_STORIES_282_COVER": "Comics and Stories #282 Cover",
    "UNCLE_SCROOGE_48_COVER": "Uncle Scrooge #48 Cover",
    "COMICS_AND_STORIES_283_COVER": "Comics and Stories #283 Cover",
    "UNCLE_SCROOGE_49_COVER": "Uncle Scrooge #49 Cover",
    "UNCLE_SCROOGE_50_COVER": "Uncle Scrooge #50 Cover",
    "UNCLE_SCROOGE_51_COVER": "Uncle Scrooge #51 Cover",
    "UNCLE_SCROOGE_52_COVER": "Uncle Scrooge #52 Cover",
    "COMICS_AND_STORIES_288_COVER": "Comics and Stories #288 Cover",
    "UNCLE_SCROOGE_53_COVER": "Uncle Scrooge #53 Cover",
    "COMICS_AND_STORIES_289_COVER": "Comics and Stories #289 Cover",
    "UNCLE_SCROOGE_54_COVER": "Uncle Scrooge #54 Cover",
    "COMICS_AND_STORIES_290_COVER": "Comics and Stories #290 Cover",
    "COMICS_AND_STORIES_291_COVER": "Comics and Stories #291 Cover",
    "COMICS_AND_STORIES_292_COVER": "Comics and Stories #292 Cover",
    "UNCLE_SCROOGE_55_COVER": "Uncle Scrooge #55 Cover",
    "UNCLE_SCROOGE_56_COVER": "Uncle Scrooge #56 Cover",
    "UNCLE_SCROOGE_56_INSIDE_FRONT_COVER": "Uncle Scrooge #56 Inside Front Cover",
    "COMICS_AND_STORIES_295_COVER": "Comics and Stories #295 Cover",
    "COMICS_AND_STORIES_296_COVER": "Comics and Stories #296 Cover",
    "UNCLE_SCROOGE_57_COVER": "Uncle Scrooge #57 Cover",
    "DONALD_DUCK_101_COVER": "Donald Duck #101 Cover",
    "COMICS_AND_STORIES_297_COVER": "Comics and Stories #297 Cover",
    "UNCLE_SCROOGE_58_COVER": "Uncle Scrooge #58 Cover",
    "COMICS_AND_STORIES_298_COVER": "Comics and Stories #298 Cover",
    "UNCLE_SCROOGE_59_COVER": "Uncle Scrooge #59 Cover",
    "DONALD_DUCK_103_COVER": "Donald Duck #103 Cover",
    "UNCLE_SCROOGE_60_COVER": "Uncle Scrooge #60 Cover",
    "COMICS_AND_STORIES_301_COVER": "Comics and Stories #301 Cover",
    "UNCLE_SCROOGE_61_COVER": "Uncle Scrooge #61 Cover",
    "COMICS_AND_STORIES_303_COVER": "Comics and Stories #303 Cover",
    "DONALD_DUCK_105_COVER": "Donald Duck #105 Cover",
    "COMICS_AND_STORIES_304_COVER": "Comics and Stories #304 Cover",
    "DONALD_DUCK_106_COVER": "Donald Duck #106 Cover",
    "UNCLE_SCROOGE_62_COVER": "Uncle Scrooge #62 Cover",
    "COMICS_AND_STORIES_306_COVER": "Comics and Stories #306 Cover",
    "UNCLE_SCROOGE_63_COVER": "Uncle Scrooge #63 Cover",
    "COMICS_AND_STORIES_307_COVER": "Comics and Stories #307 Cover",
    "UNCLE_SCROOGE_64_COVER": "Uncle Scrooge #64 Cover",
    "COMICS_AND_STORIES_309_COVER": "Comics and Stories #309 Cover",
    "UNCLE_SCROOGE_65_COVER": "Uncle Scrooge #65 Cover",
    "COMICS_AND_STORIES_310_COVER": "Comics and Stories #310 Cover",
    "UNCLE_SCROOGE_66_COVER": "Uncle Scrooge #66 Cover",
    "COMICS_AND_STORIES_313_COVER": "Comics and Stories #313 Cover",
    "COMICS_AND_STORIES_314_COVER": "Comics and Stories #314 Cover",
    "UNCLE_SCROOGE_70_COVER": "Uncle Scrooge #70 Cover",
    "COMICS_AND_STORIES_315_COVER": "Comics and Stories #315 Cover",
    "DONALD_DUCK_111_COVER": "Donald Duck #111 Cover",
    "COMICS_AND_STORIES_316_COVER": "Comics and Stories #316 Cover",
    "UNCLE_SCROOGE_68_COVER": "Uncle Scrooge #68 Cover",
    "UNCLE_SCROOGE_69_COVER": "Uncle Scrooge #69 Cover",
    "COMICS_AND_STORIES_319_COVER": "Comics and Stories #319 Cover",
    "COMICS_AND_STORIES_321_COVER": "Comics and Stories #321 Cover",
    "COMICS_AND_STORIES_322_COVER": "Comics and Stories #322 Cover",
    "UNCLE_SCROOGE_71_COVER": "Uncle Scrooge #71 Cover",
    "COMICS_AND_STORIES_324_COVER": "Comics and Stories #324 Cover",
    "COMICS_AND_STORIES_326_COVER": "Comics and Stories #326 Cover",
    "COMICS_AND_STORIES_328_COVER": "Comics and Stories #328 Cover",
    "COMICS_AND_STORIES_329_COVER": "Comics and Stories #329 Cover",
    "COMICS_AND_STORIES_331_COVER": "Comics and Stories #331 Cover",
    "COMICS_AND_STORIES_332_COVER": "Comics and Stories #332 Cover",
    "COMICS_AND_STORIES_334_COVER": "Comics and Stories #334 Cover",
    "COMICS_AND_STORIES_341_COVER": "Comics and Stories #341 Cover",
    "COMICS_AND_STORIES_342_COVER": "Comics and Stories #342 Cover",
    "DONALD_DUCK_126_COVER": "Donald Duck #126 Cover",
    "COMICS_AND_STORIES_350_COVER": "Comics and Stories #350 Cover",
    "COMICS_AND_STORIES_351_COVER": "Comics and Stories #351 Cover",
    "DAISY_AND_DONALD_25_COVER": "Daisy And Donald #25 Cover",
    "DONALD_DUCK_ALBUM_1_BACK_COVER": "Donald Duck Album #1 Back Cover",
    "HUEY_DEWEY_AND_LOUIE_JUNIOR_WOODCHUCKS_9_COVER": "Huey, Dewey and Louie Junior Woodchucks #9 Cover",  # noqa: E501
    "UNCLE_SCROOGE_6_COVER": "Uncle Scrooge #6 Cover",
    "UNCLE_SCROOGE_16_COVER": "Uncle Scrooge #16 Cover",
    "UNCLE_SCROOGE_40_BACK_COVER": "Uncle Scrooge #40 Back Cover",
    "COMICS_AND_STORIES_137_COVER": "Comics and Stories #137 Cover",
    "COMICS_AND_STORIES_138_COVER": "Comics and Stories #138 Cover",
    "COMICS_AND_STORIES_140_COVER": "Comics and Stories #140 Cover",
    "COMICS_AND_STORIES_142_COVER": "Comics and Stories #142 Cover",
    "COMICS_AND_STORIES_405_COVER": "Comics and Stories #405 Cover",
    "ALL_CHOKED_UP": "All Choked Up",
    "ALL_ONE_PAGERS": "All One-Pagers",
    "BACK_TO_LONG_AGO": "Back to Long Ago!",
    "BAD_DAY_FOR_TROOP_A": "Bad Day for Troop 'A'",
    "BEACHCOMBERS_PICNIC_THE": "The Beachcombers' Picnic",
    "BIG_TOP_BEDLAM": "Big-Top Bedlam",
    "BILLIONS_TO_SNEEZE_AT": "Billions to Sneeze At",
    "BOXED_IN": "Boxed-In",
    "BRAIN_STRAIN": "Brain-Strain",
    "CAPN_BLIGHTS_MYSTERY_SHIP": "Cap'n Blight's Mystery Ship",
    "CHELTENHAMS_CHOICE": "Cheltenham's Choice",
    "CLASSY_TAXI": "Classy Taxi!",
    "DAISYS_DAZED_DAYS": "Daisy's Dazed Days",
    "DAY_IN_A_DUCKS_LIFE_A": "A Day in a Duck's Life",
    "DIG_IT": "Dig it!",
    "DOG_SITTER_THE": "The Dog-sitter",
    "DONALD_DUCK_AND_THE_MUMMYS_RING": "Donald Duck and the Mummy's Ring",
    "DONALD_DUCK_TELLS_ABOUT_KITES": "Donald Duck Tells About Kites",
    "DONALD_DUCKS_ATOM_BOMB": "Donald Duck's Atom Bomb",
    "DONALD_DUCKS_BEST_CHRISTMAS": "Donald Duck's Best Christmas",
    "DONALD_DUCKS_WORST_NIGHTMARE": "Donald Duck's Worst Nightmare",
    "DONALDS_BAY_LOT": "Donald's Bay Lot",
    "DONALDS_GRANDMA_DUCK": "Donald's Grandma Duck",
    "DONALDS_LOVE_LETTERS": "Donald's Love Letters",
    "DONALDS_MONSTER_KITE": "Donald's Monster Kite",
    "DONALDS_PARTY": "Donald's Party",
    "DONALDS_PET_SERVICE": "Donald's Pet Service",
    "DONALDS_POSY_PATCH": "Donald's Posy Patch",
    "DONALDS_RAUCOUS_ROLE": "Donald's Raucous Role",
    "DUCKBURGS_DAY_OF_PERIL": "Duckburg's Day of Peril",
    "DUCKS_EYE_VIEW_OF_EUROPE_A": "A Duck's-eye View of Europe",
    "EYES_HAVE_IT_THE": "The Eyes Have It",
    "FABULOUS_PHILOSOPHERS_STONE_THE": "The Fabulous Philosopher's Stone",
    "FIX_UP_MIX_UP": "Fix-up Mix-up",
    "FLOWERS_ARE_FLOWERS": "Flowers Are Flowers",
    "FOR_OLD_DIMES_SAKE": "For Old Dime's Sake",
    "FULL_SERVICE_WINDOWS": "Full-Service Windows",
    "FUN_WHATS_THAT": "Fun? What's That?",
    "GAB_MUFFER_THE": "The Gab-Muffer",
    "GLADSTONES_LUCK": "Gladstone's Luck",
    "GLADSTONES_TERRIBLE_SECRET": "Gladstone's Terrible Secret",
    "GLADSTONES_USUAL_VERY_GOOD_YEAR": "Gladstone's Usual Very Good Year",
    "GOLD_FINDER_THE": "The Gold-Finder",
    "GOLD_OF_THE_49ERS": "Gold of the '49ers",
    "GOPHER_GOOF_UPS": "Gopher Goof-Ups",
    "GRANDMAS_PRESENT": "Grandma's Present",
    "GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE": "The Great Duckburg Frog-Jumping Contest",
    "GREAT_POP_UP_THE": "The Great Pop Up",
    "GYROS_IMAGINATION_INVENTION": "Gyro's Imagination Invention",
    "HALF_BAKED_BAKER_THE": "The Half-Baked Baker",
    "HARK_HARK_THE_ARK": "Hark, Hark, the Ark",
    "HAVE_GUN_WILL_DANCE": "Have Gun, Will Dance",
    "HELPERS_HELPING_HAND_A": "A Helper's Helping Hand",
    "HIGH_WIRE_DAREDEVILS": "High-wire Daredevils",
    "HOBBLIN_GOBLINS": "Hobblin' Goblins",
    "HYPNO_GUN_THE": "The Hypno-Gun",
    "IN_OLD_CALIFORNIA": "In Old California!",
    "INVENTORS_CONTEST_THE": "The Inventors' Contest",
    "JUNGLE_HI_JINKS": "Jungle Hi-Jinks",
    "KING_SIZE_CONE": "King-Size Cone",
    "KITTY_GO_ROUND": "Kitty-Go-Round",
    "KNOW_IT_ALL_MACHINE_THE": "The Know-It-All Machine",
    "LAND_BENEATH_THE_GROUND": "Land Beneath the Ground!",
    "LIMBER_W_GUEST_RANCH_THE": "The Limber W. Guest Ranch",
    "LOST_CROWN_OF_GENGHIS_KHAN_THE": "The Lost Crown of Genghis Khan!",
    "LOST_IN_THE_ANDES": "Lost in the Andes!",
    "MACHINE_MIX_UP": "Machine Mix-Up",
    "MANY_FACES_OF_MAGICA_DE_SPELL_THE": "The Many Faces of Magica de Spell",
    "MAPLE_SUGAR_TIME_HOW_SWEET_IT_IS": "Maple Sugar Time (How Sweet It Is!)",
    "MCDUCK_OF_ARABIA": "McDuck of Arabia",
    "MCDUCK_TAKES_A_DIVE": "McDuck Takes a Dive",
    "MICRO_DUCKS_FROM_OUTER_SPACE": "Micro-Ducks from Outer Space",
    "MILLION_DOLLAR_SHOWER": "Million-Dollar Shower",
    "MIXED_UP_MIXER": "Mixed-Up Mixer",
    "MOPPING_UP": "Mopping Up",
    "MR_PRIVATE_EYE": "Mr. Private Eye",
    "MUCH_LUCK_MCDUCK": "Much Luck McDuck",
    "MUSH": "Mush!",
    "NEW_YEARS_REVOLUTIONS": "New Year's Revolutions",
    "NOT_SO_ANCIENT_MARINER_THE": "The Not-so-Ancient Mariner",
    "OLD_CASTLES_SECRET_THE": "The Old Castle's Secret",
    "OPERATION_ST_BERNARD": "Operation St. Bernard",
    "PLAYIN_HOOKEY": "Playin' Hookey",
    "RACE_TO_THE_SOUTH_SEAS": "Race to the South Seas!",
    "RANTS_ABOUT_ANTS": "Rants About Ants",
    "RABBITS_FOOT_THE": "The Rabbit's Foot",
    "RICHES_RICHES_EVERYWHERE": "Riches, Riches, Everywhere!",
    "RIGGED_UP_ROLLER": "Rigged-Up Roller",
    "ROCKET_ROASTED_CHRISTMAS_TURKEY": "Rocket-Roasted Christmas Turkey",
    "SANTAS_STORMY_VISIT": "Santa's Stormy Visit",
    "SAVED_BY_THE_BAG": "Saved by the Bag!",
    "SEALS_ARE_SO_SMART": "Seals Are So Smart!",
    "SECOND_RICHEST_DUCK_THE": "The Second-Richest Duck",
    "SOMETHIN_FISHY_HERE": "Somethin' Fishy Here",
    "SORRY_TO_BE_SAFE": "Sorry to be Safe",
    "STONES_THROW_FROM_GHOST_TOWN_A": "A Stone's Throw from Ghost Town",
    "SURE_FIRE_GOLD_FINDER_THE": "The Sure-Fire Gold Finder",
    "TEN_CENT_VALENTINE": "Ten-Cent Valentine",
    "TEN_CENTS_WORTH_OF_TROUBLE": "Ten Cents' Worth of Trouble",
    "TEN_DOLLAR_DITHER": "Ten-Dollar Dither",
    "TEAHOUSE_OF_THE_WAGGIN_DRAGON": "Teahouse of the Waggin' Dragon",
    "TEN_STAR_GENERALS": "Ten-Star Generals",
    "TERROR_OF_THE_RIVER_THE": "The Terror of the River!!",
    "THATS_NO_FABLE": "That's No Fable!",
    "THREE_UN_DUCKS": "Three Un-Ducks",
    "THUMBS_UP": "Thumbs Up",
    "TIED_DOWN_TOOLS": "Tied-Down Tools",
    "TITANIC_ANTS_THE": "The Titanic Ants!",
    "TROUBLE_WITH_DIMES_THE": "The Trouble With Dimes",
    "TV_BABYSITTER_THE": "The TV Babysitter",
    "TWENTY_FOUR_CARAT_MOON_THE": "The Twenty-four Carat Moon",
    "TWO_WAY_LUCK": "Two-Way Luck",
    "UP_AND_AT_IT": "Up and at It",
    "WANT_TO_BUY_AN_ISLAND": "Want to Buy an Island?",
    "WHERE_THERES_SMOKE": "Where There's Smoke",
    "YOICKS_THE_FOX": "Yoicks! The Fox!",
    "YOU_CANT_GUESS": "You Can't Guess!",
    "YOU_CANT_WIN": "You Can't Win",
}
# fmt: on


def _title_case_segment(segment: str) -> str:
    words = segment.split("_")
    return " ".join(
        w.capitalize() if i == 0 else (w.lower() if w.lower() in _SMALL_WORDS else w.capitalize())
        for i, w in enumerate(words)
    )


def _title_name_from_enum(title: Titles) -> str:
    """Derive the human-readable title string from a Titles enum member name."""
    # `str(...)` collapses `title.name` from a ~960-member `Literal[...]` union (one literal per
    # enum member) down to plain `str`. Without it, ty evaluates every downstream string op
    # (slicing, `+`, `.split`) element-wise across that union, taking ~30s to check this file.
    name = str(title.name)
    if name in _TITLE_OVERRIDES:
        return _TITLE_OVERRIDES[name]

    if name.endswith("_THE"):
        name = "THE_" + name[:-4]
    elif name.endswith("_A"):
        name = "A_" + name[:-2]

    parts = name.split("___")
    if len(parts) > 1:
        return " - ".join(_title_case_segment(p) for p in parts)

    return _title_case_segment(name)


ENUM_TO_STR_TITLE: list[str] = [_title_name_from_enum(t) for t in Titles]
assert len(ENUM_TO_STR_TITLE) == NUM_TITLES, f"{len(ENUM_TO_STR_TITLE)} != {NUM_TITLES}"

# Reverse of ENUM_TO_STR_TITLE: canonical display string -> Titles enum member. ENUM_TO_STR_TITLE is
# indexed by enum value, so this round-trips exactly.
STR_TITLE_TO_ENUM: dict[str, Titles] = {
    title_str: Titles(index) for index, title_str in enumerate(ENUM_TO_STR_TITLE)
}
