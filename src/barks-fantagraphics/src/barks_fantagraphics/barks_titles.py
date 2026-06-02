from enum import CONTINUOUS, UNIQUE, IntEnum, auto, verify

NUM_TITLES = 663 + 4 + 1  # +4 for articles, +1 for the All One-Pagers collection

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
    EYES_IN_THE_DARK = auto()
    DAYS_AT_THE_LAZY_K = auto()
    RIDDLE_OF_THE_RED_HAT_THE = auto()
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
    NO_NOISE_IS_GOOD_NOISE = auto()
    LUCK_OF_THE_NORTH = auto()
    NEW_TOYS = auto()
    TOASTY_TOYS = auto()
    NO_PLACE_TO_HIDE = auto()
    TIED_DOWN_TOOLS = auto()
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
    FARE_DELAY = auto()
    SOMETHIN_FISHY_HERE = auto()
    BACK_TO_THE_KLONDIKE = auto()
    MONEY_LADDER_THE = auto()
    CHECKER_GAME_THE = auto()
    EASTER_ELECTION_THE = auto()
    TALKING_DOG_THE = auto()
    WORM_WEARY = auto()
    MUCH_ADO_ABOUT_QUACKLY_HALL = auto()
    SOME_HEIR_OVER_THE_RAINBOW = auto()
    MASTER_RAINMAKER_THE = auto()
    MONEY_STAIRS_THE = auto()
    MILLION_DOLLAR_PIGEON = auto()
    TEMPER_TAMPERING = auto()
    DINER_DILEMMA = auto()
    HORSERADISH_STORY_THE = auto()
    ROUND_MONEY_BIN_THE = auto()
    BARBER_COLLEGE = auto()
    FOLLOW_THE_RAINBOW = auto()
    ITCHING_TO_SHARE = auto()
    WISPY_WILLIE = auto()
    HAMMY_CAMEL_THE = auto()
    BALLET_EVASIONS = auto()
    CHEAPEST_WEIGH_THE = auto()
    BUM_STEER = auto()
    BEE_BUMBLES = auto()
    MENEHUNE_MYSTERY_THE = auto()
    TURKEY_TROT_AT_ONE_WHISTLE = auto()
    RAFFLE_REVERSAL = auto()
    FIX_UP_MIX_UP = auto()
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
    WRONG_NUMBER = auto()
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
    COME_AS_YOU_ARE = auto()
    ROUNDABOUT_HANDOUT = auto()
    FAULTY_FORTUNE = auto()
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
    LUNCHEON_LAMENT = auto()
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
    IN_KAKIMAW_COUNTRY = auto()
    LOST_PEG_LEG_MINE_THE = auto()
    LOSING_FACE = auto()
    DAY_DUCKBURG_GOT_DYED_THE = auto()
    PICNIC = auto()
    FISHING_MYSTERY = auto()
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
    GETTING_THOR = auto()
    DOGGED_DETERMINATION = auto()
    FORGOTTEN_PRECAUTION = auto()
    BIG_BOBBER_THE = auto()
    WINDFALL_OF_THE_MIND = auto()
    TITANIC_ANTS_THE = auto()
    RESCUE_ENHANCEMENT = auto()
    PERSISTENT_POSTMAN_THE = auto()
    HALF_BAKED_BAKER_THE = auto()
    DODGING_MISS_DAISY = auto()
    MONEY_WELL_THE = auto()
    MILKMAN_THE = auto()
    MOCKING_BIRD_RIDGE = auto()
    OLD_FROGGIE_CATAPULT = auto()
    GOING_TO_PIECES = auto()
    HIGH_RIDER = auto()
    THAT_SINKING_FEELING = auto()
    WATER_SKI_RACE = auto()
    BALMY_SWAMI_THE = auto()
    WINDY_STORY_THE = auto()
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
    DRAMATIC_DONALD = auto()
    CHRISTMAS_IN_DUCKBURG = auto()
    ROCKET_ROASTED_CHRISTMAS_TURKEY = auto()
    MASTER_MOVER_THE = auto()
    SPRING_FEVER = auto()
    FLYING_DUTCHMAN_THE = auto()
    PYRAMID_SCHEME = auto()
    WISHING_WELL_THE = auto()
    IMMOVABLE_MISER = auto()
    RETURN_TO_PIZEN_BLUFF = auto()
    KRANKENSTEIN_GYRO = auto()
    MONEY_CHAMP_THE = auto()
    HIS_HANDY_ANDY = auto()
    FIREFLY_TRACKER_THE = auto()
    PRIZE_OF_PIZARRO_THE = auto()
    LOVELORN_FIREMAN_THE = auto()
    KITTY_GO_ROUND = auto()
    POOR_LOSER = auto()
    FLOATING_ISLAND_THE = auto()
    CRAWLS_FOR_CASH = auto()
    BLACK_FOREST_RESCUE_THE = auto()
    GOOD_DEEDS_THE = auto()
    BLACK_WEDNESDAY = auto()
    ALL_CHOKED_UP = auto()
    WATCHFUL_PARENTS_THE = auto()
    WAX_MUSEUM_THE = auto()
    PAUL_BUNYAN_MACHINE_THE = auto()
    PIED_PIPER_OF_DUCKBURG_THE = auto()
    PIED_PIPER_OF_DUCKBURG = auto()  # Jippes version
    KNIGHTS_OF_THE_FLYING_SLEDS = auto()
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
    ALL_AT_SEA = auto()
    FISHY_WARDEN = auto()
    TWO_WAY_LUCK = auto()
    BALLOONATICS = auto()
    TURKEY_TROUBLE = auto()
    MISSILE_FIZZLE = auto()
    ROCKS_TO_RICHES = auto()
    SITTING_HIGH = auto()
    THATS_NO_FABLE = auto()
    CLOTHES_MAKE_THE_DUCK = auto()
    STICKY_SITUATION_A = auto()
    RING_LEADER_ROUNDUP = auto()
    TOO_MUCH_HELP = auto()
    RULING_THE_ROOST = auto()
    DARINGLY_DIFFERENT = auto()
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
    MATTER_OF_FACTORY_A = auto()
    CHRISTMAS_CHEERS = auto()
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
    TICKING_DETECTOR = auto()
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
    HALL_OF_THE_MERMAID_QUEEN = auto()
    DOOM_DIAMOND_THE = auto()
    CATTLE_KING_THE = auto()
    KING_SCROOGE_THE_FIRST = auto()
    PERIL_OF_THE_BLACK_FOREST = auto()
    LIFE_SAVERS = auto()
    WHALE_OF_A_GOOD_DEED = auto()
    BAD_DAY_FOR_TROOP_A = auto()
    LET_SLEEPING_BONES_LIE = auto()
    SAVIORS_OF_THE_LAKE = auto()
    BOTTLED_BATTLERS = auto()
    MAPLE_SUGAR_TIME_HOW_SWEET_IT_IS = auto()
    TRAITOR_IN_THE_RANKS = auto()
    EAGLE_SAVERS = auto()
    STORM_DANCERS = auto()
    HOUND_OF_THE_MOANING_HILLS = auto()
    DAY_THE_MOUNTAIN_SHOOK_THE = auto()
    # Synthetic collection (not a real Barks story) - bundles every one-pager.
    ALL_ONE_PAGERS = auto()
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
    "GOPHER_GOOF_UPS": "Gopher Goof-Ups",
    "GRANDMAS_PRESENT": "Grandma's Present",
    "GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE": "The Great Duckburg Frog-Jumping Contest",
    "GREAT_POP_UP_THE": "The Great Pop Up",
    "GYROS_IMAGINATION_INVENTION": "Gyro's Imagination Invention",
    "HALF_BAKED_BAKER_THE": "The Half-Baked Baker",
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
    name = title.name
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


BARKS_TITLES: list[str] = [_title_name_from_enum(t) for t in Titles]
assert len(BARKS_TITLES) == NUM_TITLES, f"{len(BARKS_TITLES)} != {NUM_TITLES}"

# Reverse of BARKS_TITLES: canonical display string -> Titles enum member. BARKS_TITLES is
# indexed by enum value, so this round-trips exactly.
ENUM_FROM_BARKS_TITLE: dict[str, Titles] = {
    title_str: Titles(index) for index, title_str in enumerate(BARKS_TITLES)
}
