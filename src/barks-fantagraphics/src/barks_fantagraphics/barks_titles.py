# ruff: noqa: E501, FBT003, S105

from dataclasses import dataclass
from datetime import date
from enum import CONTINUOUS, UNIQUE, IntEnum, auto, verify
from pathlib import Path

from comic_utils.comic_consts import DEC, JAN, PanelPath

from .comic_issues import (
    ISSUE_NAME,
    ISSUE_NAME_WRAPPED,
    SHORT_ISSUE_NAME,
    Issues,
)

NUM_TITLES = 644 + 5  # +5 for articles

US_1_FC_ISSUE_NUM = 386
US_2_FC_ISSUE_NUM = 456
US_3_FC_ISSUE_NUM = 495

# fmt: off
# noinspection LongLine
ADVENTURE_DOWN_UNDER = "Adventure Down Under"
ALL_AT_SEA = "All at Sea"
ALL_CHOKED_UP = "All Choked Up"
ALL_SEASON_HAT = "All Season Hat"
APRIL_FOOLERS_THE = "The April Foolers"
ARMORED_RESCUE = "Armored Rescue"
ART_APPRECIATION = "Art Appreciation"
ART_OF_SECURITY_THE = "The Art of Security"
ATTIC_ANTICS = "Attic Antics"
AUGUST_ACCIDENT = "August Accident"
AWASH_IN_SUCCESS = "Awash in Success"
BACKYARD_BONANZA = "Backyard Bonanza"
BACK_TO_LONG_AGO = "Back to Long Ago!"
BACK_TO_THE_KLONDIKE = "Back to the Klondike"
BAD_DAY_FOR_TROOP_A = "Bad Day for Troop 'A'"
BALLET_EVASIONS = "Ballet Evasions"
BALLOONATICS = "Balloonatics"
BALMY_SWAMI_THE = "The Balmy Swami"
BARBER_COLLEGE = "Barber College"
BEACHCOMBERS_PICNIC_THE = "The Beachcombers' Picnic"
BEACH_BOY = "Beach Boy"
BEAN_TAKEN = "Bean Taken"
BEAR_TAMER_THE = "The Bear Tamer"
BEAUTY_BUSINESS_THE = "The Beauty Business"
BEAUTY_QUEEN_THE = "The Beauty Queen"
BEE_BUMBLES = "Bee Bumbles"
BEST_LAID_PLANS = "Best Laid Plans"
BICEPS_BLUES = "Biceps Blues"
BIGGER_THE_BEGGAR_THE = "The Bigger the Beggar"
BIG_BIN_ON_KILLMOTOR_HILL_THE = "The Big Bin on Killmotor Hill"
BIG_BOBBER_THE = "The Big Bobber"
BIG_TOP_BEDLAM = "Big-Top Bedlam"
BILLIONS_IN_THE_HOLE = "Billions in the Hole"
BILLIONS_TO_SNEEZE_AT = "Billions to Sneeze At"
BILLION_DOLLAR_SAFARI_THE = "The Billion Dollar Safari"
BILL_COLLECTORS_THE = "The Bill Collectors"
BILL_WIND = "Bill Wind"
BIRD_CAMERA_THE = "The Bird Camera"
BIRD_WATCHING = "Bird Watching"
BLACK_FOREST_RESCUE_THE = "The Black Forest Rescue"
BLACK_PEARLS_OF_TABU_YAMA_THE = "The Black Pearls of Tabu Yama"
BLACK_WEDNESDAY = "Black Wednesday"
BLANKET_INVESTMENT = "Blanket Investment"
BOAT_BUSTER = "Boat Buster"
BONGO_ON_THE_CONGO = "Bongo on the Congo"
BORDERLINE_HERO = "Borderline Hero"
BOXED_IN = "Boxed-In"
BUBBLEWEIGHT_CHAMP = "Bubbleweight Champ"
BUFFO_OR_BUST = "Buffo or Bust"
BUM_STEER = "Bum Steer"
CALL_OF_THE_WILD_THE = "The Call of the Wild"
CAMERA_CRAZY = "Camera Crazy"
CAMPAIGN_OF_NOTE_A = "A Campaign of Note"
CAMPING_CONFUSION = "Camping Confusion"
CAMP_COUNSELOR = "Camp Counselor"
CANDY_KID_THE = "The Candy Kid"
CANTANKEROUS_CAT_THE = "The Cantankerous Cat"
CAPN_BLIGHTS_MYSTERY_SHIP = "Cap'n Blight's Mystery Ship"
CASE_OF_THE_STICKY_MONEY_THE = "The Case of the Sticky Money"
CASH_ON_THE_BRAIN = "Cash on the Brain"
CAST_OF_THOUSANDS = "Cast of Thousands"
CATTLE_KING_THE = "The Cattle King"
CAT_BOX_THE = "The Cat Box"
CAVE_OF_ALI_BABA = "Cave of Ali Baba"
CAVE_OF_THE_WINDS = "Cave of the Winds"
CHARITABLE_CHORE_A = "A Charitable Chore"
CHEAPEST_WEIGH_THE = "The Cheapest Weigh"
CHECKER_GAME_THE = "The Checker Game"
CHELTENHAMS_CHOICE = "Cheltenham's Choice"
CHICKADEE_CHALLENGE_THE = "The Chickadee Challenge"
CHINA_SHOP_SHAKEUP = "China Shop Shakeup"
CHRISTMAS_CHA_CHA_THE = "The Christmas Cha Cha"
CHRISTMAS_CHEERS = "Christmas Cheers"
CHRISTMAS_FOR_SHACKTOWN_A = "A Christmas for Shacktown"
CHRISTMAS_IN_DUCKBURG = "Christmas in Duckburg"
CHRISTMAS_KISS = "Christmas Kiss"
CHRISTMAS_ON_BEAR_MOUNTAIN = "Christmas on Bear Mountain"
CHUGWAGON_DERBY = "Chugwagon Derby"
CITY_OF_GOLDEN_ROOFS = "City of Golden Roofs"
CLASSY_TAXI = "Classy Taxi!"
CLOTHES_MAKE_THE_DUCK = "Clothes Make the Duck"
CODE_OF_DUCKBURG_THE = "The Code of Duckburg"
COFFEE_FOR_TWO = "Coffee for Two"
COLD_BARGAIN_A = "A Cold Bargain"
COLLECTION_DAY = "Collection Day"
COLOSSALEST_SURPRISE_QUIZ_SHOW_THE = "The Colossalest Surprise Quiz Show"
COME_AS_YOU_ARE = "Come as You are"
COURTSIDE_HEATING = "Courtside Heating"
CRAFTY_CORNER = "Crafty Corner"
CRAWLS_FOR_CASH = "Crawls for Cash"
CRAZY_QUIZ_SHOW_THE = "The Crazy Quiz Show"
CROWN_OF_THE_MAYAS = "Crown of the Mayas"
CUSTARD_GUN_THE = "The Custard Gun"
DAFFY_TAFFY_PULL_THE = "The Daffy Taffy Pull"
DAISYS_DAZED_DAYS = "Daisy's Dazed Days"
DANGEROUS_DISGUISE = "Dangerous Disguise"
DARKEST_AFRICA = "Darkest Africa"
DAY_THE_FARM_STOOD_STILL_THE = "The Day the Farm Stood Still"
DAYS_AT_THE_LAZY_K = "Days at the Lazy K"
DAY_DUCKBURG_GOT_DYED_THE = "The Day Duckburg Got Dyed"
DEEP_DECISION = "Deep Decision"
DEEP_DOWN_DOINGS = "Deep Down Doings"
DELIVERY_DILEMMA = "Delivery Dilemma"
DESCENT_INTERVAL_A = "A Descent Interval"
DIG_IT = "Dig it!"
DINER_DILEMMA = "Diner Dilemma"
DODGING_MISS_DAISY = "Dodging Miss Daisy"
DOGCATCHER_DUCK = "Dogcatcher Duck"
DOGGED_DETERMINATION = "Dogged Determination"
DOG_SITTER_THE = "The Dog-sitter"
DONALDS_BAY_LOT = "Donald's Bay Lot"
DONALDS_GRANDMA_DUCK = "Donald's Grandma Duck"
DONALDS_LOVE_LETTERS = "Donald's Love Letters"
DONALDS_MONSTER_KITE = "Donald's Monster Kite"
DONALDS_PET_SERVICE = "Donald's Pet Service"
DONALDS_POSY_PATCH = "Donald's Posy Patch"
DONALDS_RAUCOUS_ROLE = "Donald's Raucous Role"
DONALD_DUCKS_ATOM_BOMB = "Donald Duck's Atom Bomb"
DONALD_DUCKS_BEST_CHRISTMAS = "Donald Duck's Best Christmas"
DONALD_DUCKS_WORST_NIGHTMARE = "Donald Duck's Worst Nightmare"
DONALD_DUCK_AND_THE_MUMMYS_RING = "Donald Duck and the Mummy's Ring"
DONALD_DUCK_FINDS_PIRATE_GOLD = "Donald Duck Finds Pirate Gold"
DONALD_DUCK_TELLS_ABOUT_KITES = "Donald Duck Tells About Kites"
DONALD_MINES_HIS_OWN_BUSINESS = "Donald Mines His Own Business"
DONALD_OF_THE_COAST_GUARD = "Donald of the Coast Guard"
DONALD_TAMES_HIS_TEMPER = "Donald Tames His Temper"
DONALDS_PARTY = "Donald's Party"
DOOM_DIAMOND_THE = "The Doom Diamond"
DOUBLE_DATE_THE = "The Double Date"
DOUBLE_MASQUERADE = "Double Masquerade"
DOUGHNUT_DARE = "Doughnut Dare"
DOWN_FOR_THE_COUNT = "Down for the Count"
DOWSING_DUCKS = "Dowsing Ducks"
DRAMATIC_DONALD = "Dramatic Donald"
ON_THE_DREAM_PLANET = "On the Dream Planet"
DUCKBURGS_DAY_OF_PERIL = "Duckburg's Day of Peril"
DUCKBURG_PET_PARADE_THE = "The Duckburg Pet Parade"
DUCKS_EYE_VIEW_OF_EUROPE_A = "A Duck's-eye View of Europe"
DUCK_IN_THE_IRON_PANTS_THE = "The Duck in the Iron Pants"
DUCK_LUCK = "Duck Luck"
DUCK_OUT_OF_LUCK = "Duck Out of Luck"
DUELING_TYCOONS = "Dueling Tycoons"
EARLY_TO_BUILD = "Early to Build"
EASTER_ELECTION_THE = "The Easter Election"
EASY_MOWING = "Easy Mowing"
EYES_HAVE_IT_THE = "The Eyes Have It"
EYES_IN_THE_DARK = "Eyes in the Dark"
FABULOUS_PHILOSOPHERS_STONE_THE = "The Fabulous Philosopher's Stone"
FABULOUS_TYCOON_THE = "The Fabulous Tycoon"
FANTASTIC_RIVER_RACE_THE = "The Fantastic River Race"
FARE_DELAY = "Fare Delay"
FARRAGUT_THE_FALCON = "Farragut the Falcon"
FASHION_FORECAST = "Fashion Forecast"
FASHION_IN_FLIGHT = "Fashion in Flight"
FAST_AWAY_CASTAWAY = "Fast Away Castaway"
FAULTY_FORTUNE = "Faulty Fortune"
FEARSOME_FLOWERS = "Fearsome Flowers"
FERTILE_ASSETS = "Fertile Assets"
FETCHING_PRICE_A = "A Fetching Price"
FEUD_AND_FAR_BETWEEN = "Feud and Far Between"
FINANCIAL_FABLE_A = "A Financial Fable"
FINNY_FUN = "Finny Fun"
FIREBUG_THE = "The Firebug"
FIREFLIES_ARE_FREE = "Fireflies are Free"
FIREFLY_TRACKER_THE = "The Firefly Tracker"
FIREMAN_DONALD = "Fireman Donald"
FIREMAN_SCROOGE = "Fireman Scrooge"
FISHING_MYSTERY = "Fishing Mystery"
FISHY_WARDEN = "Fishy Warden"
FIX_UP_MIX_UP = "Fix-up Mix-up"
FLIP_DECISION = "Flip Decision"
FLOATING_ISLAND_THE = "The Floating Island"
FLOUR_FOLLIES = "Flour Follies"
FLOWERS_ARE_FLOWERS = "Flowers Are Flowers"
FLYING_DUTCHMAN_THE = "The Flying Dutchman"
FLYING_FARMHAND_THE = "The Flying Farmhand"
FOLLOW_THE_RAINBOW = "Follow the Rainbow"
FORBIDDEN_VALLEY = "Forbidden Valley"
FORBIDIUM_MONEY_BIN_THE = "The Forbidium Money Bin"
FORECASTING_FOLLIES = "Forecasting Follies"
FORGOTTEN_PRECAUTION = "Forgotten Precaution"
FOR_OLD_DIMES_SAKE = "For Old Dime's Sake"
FOXY_RELATIONS = "Foxy Relations"
FRACTIOUS_FUN = "Fractious Fun"
FRAIDY_FALCON_THE = "The Fraidy Falcon"
FRAMED_MIRROR_THE = "The Framed Mirror"
FREE_SKI_SPREE = "Free Ski Spree"
FRIGHTFUL_FACE = "Frightful Face"
FROGGY_FARMER = "Froggy Farmer"
FROZEN_GOLD = "Frozen Gold"
FULL_SERVICE_WINDOWS = "Full-Service Windows"
FUN_WHATS_THAT = "Fun? What's That?"
GAB_MUFFER_THE = "The Gab-Muffer"
GALL_OF_THE_WILD = "Gall of the Wild"
GEMSTONE_HUNTERS = "Gemstone Hunters"
GENUINE_ARTICLE_THE = "The Genuine Article"
GETTING_THE_BIRD = "Getting the Bird"
GETTING_THOR = "Getting Thor"
GHOST_OF_THE_GROTTO_THE = "The Ghost of the Grotto"
GHOST_SHERIFF_OF_LAST_GASP_THE = "The Ghost Sheriff of Last Gasp"
GIANT_ROBOT_ROBBERS_THE = "The Giant Robot Robbers"
GIFT_LION = "Gift Lion"
GILDED_MAN_THE = "The Gilded Man"
GLADSTONES_LUCK = "Gladstone's Luck"
GLADSTONES_TERRIBLE_SECRET = "Gladstone's Terrible Secret"
GLADSTONES_USUAL_VERY_GOOD_YEAR = "Gladstone's Usual Very Good Year"
GLADSTONE_RETURNS = "Gladstone Returns"
GOING_APE = "Going Ape"
GOING_BUGGY = "Going Buggy"
GOING_TO_PIECES = "Going to Pieces"
GOLDEN_CHRISTMAS_TREE_THE = "The Golden Christmas Tree"
GOLDEN_FLEECING_THE = "The Golden Fleecing"
GOLDEN_HELMET_THE = "The Golden Helmet"
GOLDEN_NUGGET_BOAT_THE = "The Golden Nugget Boat"
GOLDEN_RIVER_THE = "The Golden River"
GOLDILOCKS_GAMBIT_THE = "The Goldilocks Gambit"
GOLD_FINDER_THE = "The Gold-Finder"
GOLD_RUSH = "Gold Rush"
GOOD_CANOES_AND_BAD_CANOES = "Good Canoes and Bad Canoes"
GOOD_DEEDS = "Good Deeds"
GOOD_DEEDS_THE = "The Good Deeds"
GOOD_NEIGHBORS = "Good Neighbors"
GOPHER_GOOF_UPS = "Gopher Goof-Ups"
GRANDMAS_PRESENT = "Grandma's Present"
GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE = "The Great Duckburg Frog-Jumping Contest"
GREAT_POP_UP_THE = "The Great Pop Up"
GREAT_SKI_RACE_THE = "The Great Ski Race"
GREAT_STEAMBOAT_RACE_THE = "The Great Steamboat Race"
GREAT_WIG_MYSTERY_THE = "The Great Wig Mystery"
GYROS_IMAGINATION_INVENTION = "Gyro's Imagination Invention"
GYRO_BUILDS_A_BETTER_HOUSE = "Gyro Builds a Better House"
GYRO_GOES_FOR_A_DIP = "Gyro Goes for a Dip"
HALF_BAKED_BAKER_THE = "The Half-Baked Baker"
HALL_OF_THE_MERMAID_QUEEN = "Hall of the Mermaid Queen"
HAMMY_CAMEL_THE = "The Hammy Camel"
HARD_LOSER_THE = "The Hard Loser"
HAVE_GUN_WILL_DANCE = "Have Gun, Will Dance"
HEEDLESS_HORSEMAN_THE = "The Heedless Horseman"
HEIRLOOM_WATCH = "Heirloom Watch"
HELPERS_HELPING_HAND_A = "A Helper's Helping Hand"
HERO_OF_THE_DIKE = "Hero of the Dike"
HIGH_RIDER = "High Rider"
HIGH_WIRE_DAREDEVILS = "High-wire Daredevils"
HISTORY_TOSSED = "History Tossed"
HIS_HANDY_ANDY = "His Handy Andy"
HIS_SHINING_HOUR = "His Shining Hour"
HOBBLIN_GOBLINS = "Hobblin' Goblins"
HONEY_OF_A_HEN_A = "A Honey of a Hen"
HORSERADISH_STORY_THE = "The Horseradish Story"
HORSESHOE_LUCK = "Horseshoe Luck"
HOSPITALITY_WEEK = "Hospitality Week"
HOUND_HOUNDER = "Hound Hounder"
HOUND_OF_THE_WHISKERVILLES = "Hound of the Whiskervilles"
HOUSEBOAT_HOLIDAY = "Houseboat Holiday"
HOUSE_OF_HAUNTS = "House of Haunts"
HOUSE_ON_CYCLONE_HILL_THE = "The House on Cyclone Hill"
HOW_GREEN_WAS_MY_LETTUCE = "How Green Was My Lettuce"
HYPNO_GUN_THE = "The Hypno-Gun"
ICEBOAT_TO_BEAVER_ISLAND = "Iceboat to Beaver Island"
ICEBOX_ROBBER_THE = "The Icebox Robber"
ICE_TAXIS_THE = "The Ice Taxis"
IF_THE_HAT_FITS = "If the Hat Fits"
IMMOVABLE_MISER = "Immovable Miser"
INSTANT_HERCULES = "Instant Hercules"
INTERPLANETARY_POSTMAN = "Interplanetary Postman"
INVENTORS_CONTEST_THE = "The Inventors' Contest"
INVENTOR_OF_ANYTHING = "Inventor of Anything"
INVISIBLE_INTRUDER_THE = "The Invisible Intruder"
IN_ANCIENT_PERSIA = "In Ancient Persia"
IN_KAKIMAW_COUNTRY = "In Kakimaw Country"
IN_OLD_CALIFORNIA = "In Old California!"
IN_THE_SWIM = "In the Swim"
ISLAND_IN_THE_SKY = "Island in the Sky"
ISLE_OF_GOLDEN_GEESE = "Isle of Golden Geese"
ITCHING_TO_SHARE = "Itching to Share"
IT_HAPPENED_ONE_WINTER = "It Happened One Winter"
JAM_ROBBERS = "Jam Robbers"
JET_RESCUE = "Jet Rescue"
JET_WITCH = "Jet Witch"
JINXED_JALOPY_RACE_THE = "The Jinxed Jalopy Race"
JONAH_GYRO = "Jonah Gyro"
JUMPING_TO_CONCLUSIONS = "Jumping to Conclusions"
JUNGLE_BUNGLE = "Jungle Bungle"
JUNGLE_HI_JINKS = "Jungle Hi-Jinks"
KING_SCROOGE_THE_FIRST = "King Scrooge the First"
KING_SIZE_CONE = "King-Size Cone"
KITE_WEATHER = "Kite Weather"
KITTY_GO_ROUND = "Kitty-Go-Round"
KNIGHTLY_RIVALS = "Knightly Rivals"
KNIGHTS_OF_THE_FLYING_SLEDS = "Knights of the Flying Sleds"
KNIGHT_IN_SHINING_ARMOR = "Knight in Shining Armor"
KNOW_IT_ALL_MACHINE_THE = "The Know-It-All Machine"
KRANKENSTEIN_GYRO = "Krankenstein Gyro"
LAND_BENEATH_THE_GROUND = "Land Beneath the Ground!"
LAND_OF_THE_PYGMY_INDIANS = "Land of the Pygmy Indians"
LAND_OF_THE_TOTEM_POLES = "Land of the Totem Poles"
LAUNDRY_FOR_LESS = "Laundry for Less"
LEMMING_WITH_THE_LOCKET_THE = "The Lemming with the Locket"
LEMONADE_FLING_THE = "The Lemonade Fling"
LET_SLEEPING_BONES_LIE = "Let Sleeping Bones Lie"
LETTER_TO_SANTA = "Letter to Santa"
LIBRARIAN_THE = "The Librarian"
LIFE_SAVERS = "Life Savers"
LIFEGUARD_DAZE = "Lifeguard Daze"
LIGHTS_OUT = "Lights Out"
LIMBER_W_GUEST_RANCH_THE = "The Limber W. Guest Ranch"
LINKS_HIJINKS = "Links Hijinks"
LITTLEST_CHICKEN_THIEF_THE = "The Littlest Chicken Thief"
LOCK_OUT_THE = "The Lock Out"
LOG_JOCKEY = "Log Jockey"
LONG_DISTANCE_COLLISION = "Long Distance Collision"
LONG_RACE_TO_PUMPKINBURG_THE = "The Long Race to Pumpkinburg"
LOONY_LUNAR_GOLD_RUSH_THE = "The Loony Lunar Gold Rush"
LOSING_FACE = "Losing Face"
LOST_BENEATH_THE_SEA = "Lost Beneath the Sea"
LOST_CROWN_OF_GENGHIS_KHAN_THE = "The Lost Crown of Genghis Khan!"
LOST_FRONTIER = "Lost Frontier"
LOST_IN_THE_ANDES = "Lost in the Andes!"
LOST_PEG_LEG_MINE_THE = "The Lost Peg Leg Mine"
LOST_RABBIT_FOOT_THE = "The Lost Rabbit Foot"
LOVELORN_FIREMAN_THE = "The Lovelorn Fireman"
LUCK_OF_THE_NORTH = "Luck of the North"
LUNCHEON_LAMENT = "Luncheon Lament"
MACHINE_MIX_UP = "Machine Mix-Up"
MADCAP_INVENTORS = "Madcap Inventors"
MADCAP_MARINER_THE = "The Madcap Mariner"
MAD_CHEMIST_THE = "The Mad Chemist"
MADBALL_PITCHER_THE = "The Madball Pitcher"
MAGICAL_MISERY = "Magical Misery"
MAGIC_HOURGLASS_THE = "The Magic Hourglass"
MAGIC_INK_THE = "The Magic Ink"
MAHARAJAH_DONALD = "Maharajah Donald"
MANAGING_THE_ECHO_SYSTEM = "Managing the Echo System"
MANY_FACES_OF_MAGICA_DE_SPELL_THE = "The Many Faces of Magica de Spell"
MAN_VERSUS_MACHINE = "Man Versus Machine"
MASTERING_THE_MATTERHORN = "Mastering the Matterhorn"
MASTERS_OF_MELODY_THE = "The Masters of Melody"
MASTER_GLASSER_THE = "The Master Glasser"
MASTER_ICE_FISHER = "Master Ice Fisher"
MASTER_MOVER_THE = "The Master Mover"
MASTER_RAINMAKER_THE = "The Master Rainmaker"
MASTER_THE = "The Master"
MASTER_WRECKER = "Master Wrecker"
MATINEE_MADNESS = "Matinee Madness"
MATTER_OF_FACTORY_A = "A Matter of Factory"
MCDUCK_OF_ARABIA = "McDuck of Arabia"
MCDUCK_TAKES_A_DIVE = "McDuck Takes a Dive"
MEDALING_AROUND = "Medaling Around"
MENEHUNE_MYSTERY_THE = "The Menehune Mystery"
MENTAL_FEE = "Mental Fee"
MERRY_FERRY = "Merry Ferry"
MICRO_DUCKS_FROM_OUTER_SPACE = "Micro-Ducks from Outer Space"
MIDAS_TOUCH_THE = "The Midas Touch"
MIDGETS_MADNESS = "Midgets Madness"
MIGHTY_TRAPPER_THE = "The Mighty Trapper"
MIGRATING_MILLIONS = "Migrating Millions"
MILKMAN_THE = "The Milkman"
MILKTIME_MELODIES = "Milktime Melodies"
MILLION_DOLLAR_PIGEON = "Million Dollar Pigeon"
MILLION_DOLLAR_SHOWER = "Million-Dollar Shower"
MINES_OF_KING_SOLOMON_THE = "The Mines of King Solomon"
MISSILE_FIZZLE = "Missile Fizzle"
MIXED_UP_MIXER = "Mixed-up Mixer"
MOCKING_BIRD_RIDGE = "Mocking Bird Ridge"
MONEY_BAG_GOAT = "Money Bag Goat"
MONEY_CHAMP_THE = "The Money Champ"
MONEY_HAT_THE = "The Money Hat"
MONEY_LADDER_THE = "The Money Ladder"
MONEY_STAIRS_THE = "The Money Stairs"
MONEY_WELL_THE = "The Money Well"
MONKEY_BUSINESS = "Monkey Business"
MOOLA_ON_THE_MOVE = "Moola on the Move"
MOPPING_UP = "Mopping Up"
MOVIE_MAD = "Movie Mad"
MR_PRIVATE_EYE = "Mr. Private Eye"
MUCH_ADO_ABOUT_QUACKLY_HALL = "Much Ado about Quackly Hall"
MUCH_LUCK_MCDUCK = "Much Luck McDuck"
MUSH = "Mush!"
MYSTERIOUS_STONE_RAY_THE = "The Mysterious Stone Ray"
MYSTERY_OF_THE_GHOST_TOWN_RAILROAD = "Mystery of the Ghost Town Railroad"
MYSTERY_OF_THE_LOCH = "Mystery of the Loch"
MYSTERY_OF_THE_SWAMP = "Mystery of the Swamp"
MYTHTIC_MYSTERY = "Mythtic Mystery"
MY_LUCKY_VALENTINE = "My Lucky Valentine"
NEST_EGG_COLLECTOR = "Nest Egg Collector"
NET_WORTH = "Net Worth"
NEW_GIRL_THE = "The New Girl"
NEW_TOYS = "New Toys"
NEW_YEARS_REVOLUTIONS = "New Year's Revolutions"
NOBLE_PORPOISES = "Noble Porpoises"
NOISE_NULLIFIER = "Noise Nullifier"
NORTHEASTER_ON_CAPE_QUACK = "Northeaster on Cape Quack"
NORTH_OF_THE_YUKON = "North of the Yukon"
NOT_SO_ANCIENT_MARINER_THE = "The Not-so-Ancient Mariner"
NO_BARGAIN = "No Bargain"
NO_NOISE_IS_GOOD_NOISE = "No Noise is Good Noise"
NO_PLACE_TO_HIDE = "No Place to Hide"
NO_SUCH_VARMINT = "No Such Varmint"
ODD_ORDER_THE = "The Odd Order"
ODDBALL_ODYSSEY = "Oddball Odyssey"
OIL_THE_NEWS = "Oil the News"
OLD_CASTLES_SECRET_THE = "The Old Castle's Secret"
OLD_FROGGIE_CATAPULT = "Old Froggie Catapult"
OLYMPIAN_TORCH_BEARER_THE = "The Olympian Torch Bearer"
OLYMPIC_HOPEFUL_THE = "The Olympic Hopeful"
OMELET = "Omelet"
ONCE_UPON_A_CARNIVAL = "Once Upon a Carnival"
ONLY_A_POOR_OLD_MAN = "Only a Poor Old Man"
OODLES_OF_OOMPH = "Oodles of Oomph"
OPERATION_ST_BERNARD = "Operation St. Bernard"
ORNAMENTS_ON_THE_WAY = "Ornaments on the Way"
OSOGOOD_SILVER_POLISH = "Osogood Silver Polish"
OUTFOXED_FOX = "Outfoxed Fox"
PAUL_BUNYAN_MACHINE_THE = "The Paul Bunyan Machine"
PEACEFUL_HILLS_THE = "The Peaceful Hills"
PEARLS_OF_WISDOM = "Pearls of Wisdom"
PECKING_ORDER = "Pecking Order"
PERIL_OF_THE_BLACK_FOREST = "Peril of the Black Forest"
PERSISTENT_POSTMAN_THE = "The Persistent Postman"
PHANTOM_OF_NOTRE_DUCK_THE = "The Phantom of Notre Duck"
PICNIC = "Picnic"
PICNIC_TRICKS = "Picnic Tricks"
PIED_PIPER_OF_DUCKBURG_THE = "The Pied Piper of Duckburg"
PIPELINE_TO_DANGER = "Pipeline to Danger"
PIXILATED_PARROT_THE = "The Pixilated Parrot"
PIZEN_SPRING_DUDE_RANCH = "Pizen Spring Dude Ranch"
PLAYIN_HOOKEY = "Playin' Hookey"
PLAYMATES = "Playmates"
PLENTY_OF_PETS = "Plenty of Pets"
PLUMMETING_WITH_PRECISION = "Plummeting with Precision"
POOL_SHARKS = "Pool Sharks"
POOR_LOSER = "Poor Loser"
POSTHASTY_POSTMAN = "Posthasty Postman"
POUND_FOR_SOUND = "Pound for Sound"
POWER_PLOWING = "Power Plowing"
PRANK_ABOVE_A = "A Prank Above"
PRICE_OF_FAME_THE = "The Price of Fame"
PRIZE_OF_PIZARRO_THE = "The Prize of Pizarro"
PROJECTING_DESIRES = "Projecting Desires"
PURLOINED_PUTTY_THE = "The Purloined Putty"
PYRAMID_SCHEME = "Pyramid Scheme"
QUEEN_OF_THE_WILD_DOG_PACK_THE = "The Queen of the Wild Dog Pack"
RABBITS_FOOT_THE = "The Rabbit's Foot"
RACE_TO_THE_SOUTH_SEAS = "Race to the South Seas!"
RAFFLE_REVERSAL = "Raffle Reversal"
RAGS_TO_RICHES = "Rags to Riches"
RANTS_ABOUT_ANTS = "Rants About Ants"
RAVEN_MAD = "Raven Mad"
RED_APPLE_SAP = "Red Apple Sap"
RELATIVE_REACTION = "Relative Reaction"
REMEMBER_THIS = "Remember This"
RESCUE_ENHANCEMENT = "Rescue Enhancement"
RETURN_TO_PIZEN_BLUFF = "Return to Pizen Bluff"
REVERSED_RESCUE_THE = "The Reversed Rescue"
RICHES_RICHES_EVERYWHERE = "Riches, Riches, Everywhere!"
RIDDLE_OF_THE_RED_HAT_THE = "The Riddle of the Red Hat"
RIDING_THE_PONY_EXPRESS = "Riding the Pony Express"
RIGGED_UP_ROLLER = "Rigged-Up Roller"
RIP_VAN_DONALD = "Rip Van Donald"
RIVAL_BEACHCOMBERS = "Rival Beachcombers"
RIVAL_BOATMEN = "Rival Boatmen"
ROCKET_RACE_AROUND_THE_WORLD = "Rocket Race Around the World"
ROCKET_RACE_TO_THE_MOON = "Rocket Race to the Moon"
ROCKET_ROASTED_CHRISTMAS_TURKEY = "Rocket-Roasted Christmas Turkey"
ROCKET_WING_SAVES_THE_DAY = "Rocket Wing Saves the Day"
ROCKS_TO_RICHES = "Rocks to Riches"
ROSCOE_THE_ROBOT = "Roscoe the Robot"
ROUNDABOUT_HANDOUT = "Roundabout Handout"
ROUND_MONEY_BIN_THE = "The Round Money Bin"
RUG_RIDERS_IN_THE_SKY = "Rug Riders in the Sky"
RUNAWAY_TRAIN_THE = "The Runaway Train"
SAGMORE_SPRINGS_HOTEL = "Sagmore Springs Hotel"
SALESMAN_DONALD = "Salesman Donald"
SALMON_DERBY = "Salmon Derby"
SANTAS_STORMY_VISIT = "Santa's Stormy Visit"
SAVED_BY_THE_BAG = "Saved by the Bag!"
SCREAMING_COWBOY_THE = "The Screaming Cowboy"
SEALS_ARE_SO_SMART = "Seals Are So Smart!"
SEARCHING_FOR_A_SUCCESSOR = "Searching for a Successor"
SEARCH_FOR_THE_CUSPIDORIA = "Search for the Cuspidoria"
SECOND_RICHEST_DUCK_THE = "The Second-Richest Duck"
SECRET_BOOK_THE = "The Secret Book"
SECRET_OF_ATLANTIS_THE = "The Secret of Atlantis"
SECRET_OF_HONDORICA = "Secret of Hondorica"
SECRET_RESOLUTIONS = "Secret Resolutions"
SEEING_IS_BELIEVING = "Seeing is Believing"
SEPTEMBER_SCRIMMAGE = "September Scrimmage"
SERUM_TO_CODFISH_COVE = "Serum to Codfish Cove"
SEVEN_CITIES_OF_CIBOLA_THE = "The Seven Cities of Cibola"
SHEEPISH_COWBOYS_THE = "The Sheepish Cowboys"
SHERIFF_OF_BULLET_VALLEY = "Sheriff of Bullet Valley"
SIDEWALK_OF_THE_MIND = "Sidewalk of the Mind"
SILENT_NIGHT = "Silent Night"
SINGAPORE_JOE = "Singapore Joe"
SITTING_HIGH = "Sitting High"
SKI_LIFT_LETDOWN = "Ski Lift Letdown"
SLEEPIES_THE = "The Sleepies"
SLEEPY_SITTERS = "Sleepy Sitters"
SLIPPERY_SHINE = "Slippery Shine"
SLIPPERY_SIPPER = "Slippery Sipper"
SMASH_SUCCESS = "Smash Success"
SMOKE_WRITER_IN_THE_SKY = "Smoke Writer in the Sky"
SMUGSNORKLE_SQUATTIE_THE = "The Smugsnorkle Squattie"
SNAKE_TAKE = "Snake Take"
SNOW_CHASER_THE = "The Snow Chaser"
SNOW_DUSTER = "Snow Duster"
SNOW_FUN = "Snow Fun"
SOMETHIN_FISHY_HERE = "Somethin' Fishy Here"
SOME_HEIR_OVER_THE_RAINBOW = "Some Heir Over the Rainbow"
SORRY_TO_BE_SAFE = "Sorry to be Safe"
SOUPLINE_EIGHT = "Soupline Eight"
SO_FAR_AND_NO_SAFARI = "So Far and No Safari"
SPARE_THAT_HAIR = "Spare That Hair"
SPECIAL_DELIVERY = "Special Delivery"
SPENDING_MONEY = "Spending Money"
SPICY_TALE_A = "A Spicy Tale"
SPOIL_THE_ROD = "Spoil the Rod"
SPRING_FEVER = "Spring Fever"
STABLE_PRICES = "Stable Prices"
STALWART_RANGER = "Stalwart Ranger"
STATUESQUE_SPENDTHRIFTS = "Statuesque Spendthrifts"
STATUES_OF_LIMITATIONS = "Statues of Limitations"
STATUS_SEEKER_THE = "The Status Seeker"
STONES_THROW_FROM_GHOST_TOWN_A = "A Stone's Throw from Ghost Town"
STRANGER_THAN_FICTION = "Stranger than Fiction"
STRANGE_SHIPWRECKS_THE = "The Strange Shipwrecks"
STUBBORN_STORK_THE = "The Stubborn Stork"
SUNKEN_YACHT_THE = "The Sunken Yacht"
SUPER_SNOOPER = "Super Snooper"
SURE_FIRE_GOLD_FINDER_THE = "The Sure-Fire Gold Finder"
SWAMP_OF_NO_RETURN_THE = "The Swamp of No Return"
SWEAT_DEAL_A = "A Sweat Deal"
SWIMMING_SWINDLERS = "Swimming Swindlers"
TALE_OF_THE_TAPE = "Tale of the Tape"
TALKING_DOG_THE = "The Talking Dog"
TALKING_PARROT = "Talking Parrot"
TAMING_THE_RAPIDS = "Taming the Rapids"
TEMPER_TAMPERING = "Temper Tampering"
TENDERFOOT_TRAP_THE = "The Tenderfoot Trap"
TEN_CENTS_WORTH_OF_TROUBLE = "Ten Cents' Worth of Trouble"
TEN_CENT_VALENTINE = "Ten-Cent Valentine"
TEN_DOLLAR_DITHER = "Ten-Dollar Dither"
TEN_STAR_GENERALS = "Ten-Star Generals"
TERRIBLE_TOURIST = "Terrible Tourist"
TERRIBLE_TURKEY_THE = "The Terrible Turkey"
TERROR_OF_THE_BEAGLE_BOYS = "Terror of the Beagle Boys"
TERROR_OF_THE_RIVER_THE = "The Terror of the River!!"
THATS_NO_FABLE = "That's No Fable!"
THAT_SINKING_FEELING = "That Sinking Feeling"
THAT_SMALL_FEELING = "That Small Feeling"
THIEVERY_AFOOT = "Thievery Afoot"
THINK_BOX_BOLLIX_THE = "The Think Box Bollix"
THREE_DIRTY_LITTLE_DUCKS = "Three Dirty Little Ducks"
THREE_GOOD_LITTLE_DUCKS = "Three Good Little Ducks"
THREE_UN_DUCKS = "Three Un-Ducks"
THRIFTY_SPENDTHRIFT_THE = "The Thrifty Spendthrift"
THRIFT_GIFT_A = "A Thrift Gift"
THUG_BUSTERS = "Thug Busters"
THUMBS_UP = "Thumbs Up"
TICKING_DETECTOR = "Ticking Detector"
TIED_DOWN_TOOLS = "Tied-Down Tools"
TIGHT_SHOES = "Tight Shoes"
TITANIC_ANTS_THE = "The Titanic Ants!"
TOASTY_TOYS = "Toasty Toys"
TOO_FIT_TO_FIT = "Too Fit to Fit"
TOO_MANY_PETS = "Too Many Pets"
TOO_SAFE_SAFE = "Too Safe Safe"
TOP_WAGES = "Top Wages"
TOUCHE_TOUPEE = "Touche Toupee"
TOYLAND = "Toyland"
TRACKING_SANDY = "Tracking Sandy"
TRAIL_OF_THE_UNICORN = "Trail of the Unicorn"
TRAIL_TYCOON = "Trail Tycoon"
TRAINING_FARM_FUSS_THE = "The Training Farm Fuss"
TRALLA_LA = "Tralla La"
TRAMP_STEAMER_THE = "The Tramp Steamer"
TRAPPED_LIGHTNING = "Trapped Lightning"
TRAVELLING_TRUANTS = "Travelling Truants"
TRAVEL_TIGHTWAD_THE = "The Travel Tightwad"
TREASURE_OF_MARCO_POLO = "Treasure of Marco Polo"
TREEING_OFF = "Treeing Off"
TREE_TRICK = "Tree Trick"
TRICKY_EXPERIMENT = "Tricky Experiment"
TRICK_OR_TREAT = "Trick or Treat"
TROUBLE_INDEMNITY = "Trouble Indemnity"
TROUBLE_WITH_DIMES_THE = "The Trouble With Dimes"
TRUANT_NEPHEWS_THE = "The Truant Nephews"
TRUANT_OFFICER_DONALD = "Truant Officer Donald"
TRUE_TEST_THE = "The True Test"
TUCKERED_TIGER_THE = "The Tuckered Tiger"
TUNNEL_VISION = "Tunnel Vision"
TURKEY_RAFFLE = "Turkey Raffle"
TURKEY_TROT_AT_ONE_WHISTLE = "Turkey Trot at One Whistle"
TURKEY_TROUBLE = "Turkey Trouble"
TURKEY_WITH_ALL_THE_SCHEMINGS = "Turkey with All the Schemings"
TURN_FOR_THE_WORSE = "Turn for the Worse"
TV_BABYSITTER_THE = "The TV Babysitter"
TWENTY_FOUR_CARAT_MOON_THE = "The Twenty-four Carat Moon"
TWO_WAY_LUCK = "Two-Way Luck"
UNCLE_SCROOGE___MONKEY_BUSINESS = "Uncle Scrooge - Monkey Business"
UNDER_THE_POLAR_ICE = "Under the Polar Ice"
UNFRIENDLY_ENEMIES = "Unfriendly Enemies"
UNORTHODOX_OX_THE = "The Unorthodox Ox"
UNSAFE_SAFE_THE = "The Unsafe Safe"
UP_AND_AT_IT = "Up and at It"
VACATION_MISERY = "Vacation Misery"
VACATION_TIME = "Vacation Time"
VICTORY_GARDEN_THE = "The Victory Garden"
VILLAGE_BLACKSMITH_THE = "The Village Blacksmith"
VOLCANO_VALLEY = "Volcano Valley"
VOODOO_HOODOO = "Voodoo Hoodoo"
WALTZ_KING_THE = "The Waltz King"
WANT_TO_BUY_AN_ISLAND = "Want to Buy an Island?"
WAR_PAINT = "War Paint"
WASTED_WORDS = "Wasted Words"
WATCHFUL_PARENTS_THE = "The Watchful Parents"
WATCHING_THE_WATCHMAN = "Watching the Watchman"
WATER_SKI_RACE = "Water Ski Race"
WATT_AN_OCCASION = "Watt an Occasion"
WAX_MUSEUM_THE = "The Wax Museum"
WAY_OUT_YONDER = "Way Out Yonder"
WEATHER_WATCHERS_THE = "The Weather Watchers"
WEBFOOTED_WRANGLER = "Webfooted Wrangler"
WHALE_OF_A_GOOD_DEED = "Whale of a Good Deed"
WHALE_OF_A_STORY_A = "A Whale of a Story"
WILD_ABOUT_FLOWERS = "Wild about Flowers"
WILY_RIVAL = "Wily Rival"
WINDFALL_OF_THE_MIND = "Windfall of the Mind"
WINDY_STORY_THE = "The Windy Story"
WINTERTIME_WAGER = "Wintertime Wager"
WIRED = "Wired"
WISHFUL_EXCESS = "Wishful Excess"
WISHING_STONE_ISLAND = "Wishing Stone Island"
WISHING_WELL_THE = "The Wishing Well"
WISPY_WILLIE = "Wispy Willie"
WITCHING_STICK_THE = "The Witching Stick"
WHOLE_HERD_OF_HELP_THE = "The Whole Herd of Help"
WORM_WEARY = "Worm Weary"
WRONG_NUMBER = "Wrong Number"
YOICKS_THE_FOX = "Yoicks! The Fox!"
YOU_CANT_GUESS = "You Can't Guess!"
YOU_CANT_WIN = "You Can't Win"
ZERO_HERO = "Zero Hero"
# Not comics below!
RICH_TOMASSO___ON_COLORING_BARKS = "Rich Tomasso - On Coloring Barks"
DON_AULT___FANTAGRAPHICS_INTRODUCTION = "Don Ault - Fantagraphics Introduction"
DON_AULT___LIFE_AMONG_THE_DUCKS = "Don Ault - Life Among the Ducks"
# noinspection LongLine
MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD = "Maggie Thompson - Comics Readers Find Comic Book Gold"
GEORGE_LUCAS___AN_APPRECIATION = "George Lucas - An Appreciation"
CENSORSHIP_FIXES_AND_OTHER_CHANGES = "Censorship Fixes and Other Changes"
# fmt: on


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
    TALKING_PARROT = auto()
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
    # Not comics below!
    RICH_TOMASSO___ON_COLORING_BARKS = auto()
    DON_AULT___FANTAGRAPHICS_INTRODUCTION = auto()
    DON_AULT___LIFE_AMONG_THE_DUCKS = auto()
    MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD = auto()
    GEORGE_LUCAS___AN_APPRECIATION = auto()
    CENSORSHIP_FIXES_AND_OTHER_CHANGES = auto()


assert len(Titles) == NUM_TITLES, f"{len(Titles)} != {NUM_TITLES}"

BARKS_TITLES = [
    DONALD_DUCK_FINDS_PIRATE_GOLD,
    VICTORY_GARDEN_THE,
    RABBITS_FOOT_THE,
    LIFEGUARD_DAZE,
    GOOD_DEEDS,
    LIMBER_W_GUEST_RANCH_THE,
    MIGHTY_TRAPPER_THE,
    DONALD_DUCK_AND_THE_MUMMYS_RING,
    HARD_LOSER_THE,
    TOO_MANY_PETS,
    GOOD_NEIGHBORS,
    SALESMAN_DONALD,
    SNOW_FUN,
    DUCK_IN_THE_IRON_PANTS_THE,
    KITE_WEATHER,
    THREE_DIRTY_LITTLE_DUCKS,
    MAD_CHEMIST_THE,
    RIVAL_BOATMEN,
    CAMERA_CRAZY,
    FARRAGUT_THE_FALCON,
    PURLOINED_PUTTY_THE,
    HIGH_WIRE_DAREDEVILS,
    TEN_CENTS_WORTH_OF_TROUBLE,
    DONALDS_BAY_LOT,
    FROZEN_GOLD,
    THIEVERY_AFOOT,
    MYSTERY_OF_THE_SWAMP,
    TRAMP_STEAMER_THE,
    LONG_RACE_TO_PUMPKINBURG_THE,
    WEBFOOTED_WRANGLER,
    ICEBOX_ROBBER_THE,
    PECKING_ORDER,
    TAMING_THE_RAPIDS,
    EYES_IN_THE_DARK,
    DAYS_AT_THE_LAZY_K,
    RIDDLE_OF_THE_RED_HAT_THE,
    THUG_BUSTERS,
    GREAT_SKI_RACE_THE,
    FIREBUG_THE,
    TEN_DOLLAR_DITHER,
    DONALD_DUCKS_BEST_CHRISTMAS,
    SILENT_NIGHT,
    DONALD_TAMES_HIS_TEMPER,
    SINGAPORE_JOE,
    MASTER_ICE_FISHER,
    JET_RESCUE,
    DONALDS_MONSTER_KITE,
    TERROR_OF_THE_RIVER_THE,
    SEALS_ARE_SO_SMART,
    BICEPS_BLUES,
    SMUGSNORKLE_SQUATTIE_THE,
    SANTAS_STORMY_VISIT,
    SWIMMING_SWINDLERS,
    PLAYIN_HOOKEY,
    GOLD_FINDER_THE,
    BILL_COLLECTORS_THE,
    TURKEY_RAFFLE,
    MAHARAJAH_DONALD,
    CANTANKEROUS_CAT_THE,
    DONALD_DUCKS_ATOM_BOMB,
    GOING_BUGGY,
    PEACEFUL_HILLS_THE,
    JAM_ROBBERS,
    PICNIC_TRICKS,
    VOLCANO_VALLEY,
    IF_THE_HAT_FITS,
    DONALDS_POSY_PATCH,
    DONALD_MINES_HIS_OWN_BUSINESS,
    MAGICAL_MISERY,
    THREE_GOOD_LITTLE_DUCKS,
    VACATION_MISERY,
    ADVENTURE_DOWN_UNDER,
    GHOST_OF_THE_GROTTO_THE,
    WALTZ_KING_THE,
    MASTERS_OF_MELODY_THE,
    FIREMAN_DONALD,
    CHRISTMAS_ON_BEAR_MOUNTAIN,
    FASHION_IN_FLIGHT,
    TURN_FOR_THE_WORSE,
    MACHINE_MIX_UP,
    TERRIBLE_TURKEY_THE,
    WINTERTIME_WAGER,
    WATCHING_THE_WATCHMAN,
    DARKEST_AFRICA,
    WIRED,
    GOING_APE,
    OLD_CASTLES_SECRET_THE,
    SPOIL_THE_ROD,
    BIRD_WATCHING,
    HORSESHOE_LUCK,
    BEAN_TAKEN,
    ROCKET_RACE_TO_THE_MOON,
    DONALD_OF_THE_COAST_GUARD,
    GLADSTONE_RETURNS,
    SHERIFF_OF_BULLET_VALLEY,
    LINKS_HIJINKS,
    SORRY_TO_BE_SAFE,
    BEST_LAID_PLANS,
    GENUINE_ARTICLE_THE,
    PEARLS_OF_WISDOM,
    FOXY_RELATIONS,
    CRAZY_QUIZ_SHOW_THE,
    GOLDEN_CHRISTMAS_TREE_THE,
    TOYLAND,
    JUMPING_TO_CONCLUSIONS,
    TRUE_TEST_THE,
    ORNAMENTS_ON_THE_WAY,
    TRUANT_OFFICER_DONALD,
    DONALD_DUCKS_WORST_NIGHTMARE,
    PIZEN_SPRING_DUDE_RANCH,
    RIVAL_BEACHCOMBERS,
    LOST_IN_THE_ANDES,
    TOO_FIT_TO_FIT,
    TUNNEL_VISION,
    SLEEPY_SITTERS,
    SUNKEN_YACHT_THE,
    RACE_TO_THE_SOUTH_SEAS,
    MANAGING_THE_ECHO_SYSTEM,
    PLENTY_OF_PETS,
    VOODOO_HOODOO,
    SLIPPERY_SHINE,
    FRACTIOUS_FUN,
    KING_SIZE_CONE,
    SUPER_SNOOPER,
    GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE,
    DOWSING_DUCKS,
    GOLDILOCKS_GAMBIT_THE,
    LETTER_TO_SANTA,
    NO_NOISE_IS_GOOD_NOISE,
    LUCK_OF_THE_NORTH,
    NEW_TOYS,
    TOASTY_TOYS,
    NO_PLACE_TO_HIDE,
    TIED_DOWN_TOOLS,
    DONALDS_LOVE_LETTERS,
    RIP_VAN_DONALD,
    TRAIL_OF_THE_UNICORN,
    LAND_OF_THE_TOTEM_POLES,
    NOISE_NULLIFIER,
    MATINEE_MADNESS,
    FETCHING_PRICE_A,
    SERUM_TO_CODFISH_COVE,
    WILD_ABOUT_FLOWERS,
    IN_ANCIENT_PERSIA,
    VACATION_TIME,
    DONALDS_GRANDMA_DUCK,
    CAMP_COUNSELOR,
    PIXILATED_PARROT_THE,
    MAGIC_HOURGLASS_THE,
    BIG_TOP_BEDLAM,
    YOU_CANT_GUESS,
    DANGEROUS_DISGUISE,
    NO_SUCH_VARMINT,
    BILLIONS_TO_SNEEZE_AT,
    OPERATION_ST_BERNARD,
    FINANCIAL_FABLE_A,
    APRIL_FOOLERS_THE,
    IN_OLD_CALIFORNIA,
    KNIGHTLY_RIVALS,
    POOL_SHARKS,
    TROUBLE_WITH_DIMES_THE,
    GLADSTONES_LUCK,
    TEN_STAR_GENERALS,
    CHRISTMAS_FOR_SHACKTOWN_A,
    ATTIC_ANTICS,
    TRUANT_NEPHEWS_THE,
    TERROR_OF_THE_BEAGLE_BOYS,
    TALKING_PARROT,
    TREEING_OFF,
    CHRISTMAS_KISS,
    PROJECTING_DESIRES,
    BIG_BIN_ON_KILLMOTOR_HILL_THE,
    GLADSTONES_USUAL_VERY_GOOD_YEAR,
    SCREAMING_COWBOY_THE,
    STATUESQUE_SPENDTHRIFTS,
    ROCKET_WING_SAVES_THE_DAY,
    GLADSTONES_TERRIBLE_SECRET,
    ONLY_A_POOR_OLD_MAN,
    OSOGOOD_SILVER_POLISH,
    COFFEE_FOR_TWO,
    SOUPLINE_EIGHT,
    THINK_BOX_BOLLIX_THE,
    GOLDEN_HELMET_THE,
    FULL_SERVICE_WINDOWS,
    RIGGED_UP_ROLLER,
    AWASH_IN_SUCCESS,
    HOUSEBOAT_HOLIDAY,
    GEMSTONE_HUNTERS,
    GILDED_MAN_THE,
    STABLE_PRICES,
    ARMORED_RESCUE,
    CRAFTY_CORNER,
    SPENDING_MONEY,
    HYPNO_GUN_THE,
    TRICK_OR_TREAT,
    PRANK_ABOVE_A,
    FRIGHTFUL_FACE,
    HOBBLIN_GOBLINS,
    OMELET,
    CHARITABLE_CHORE_A,
    TURKEY_WITH_ALL_THE_SCHEMINGS,
    FLIP_DECISION,
    MY_LUCKY_VALENTINE,
    FARE_DELAY,
    SOMETHIN_FISHY_HERE,
    BACK_TO_THE_KLONDIKE,
    MONEY_LADDER_THE,
    CHECKER_GAME_THE,
    EASTER_ELECTION_THE,
    TALKING_DOG_THE,
    WORM_WEARY,
    MUCH_ADO_ABOUT_QUACKLY_HALL,
    SOME_HEIR_OVER_THE_RAINBOW,
    MASTER_RAINMAKER_THE,
    MONEY_STAIRS_THE,
    MILLION_DOLLAR_PIGEON,
    TEMPER_TAMPERING,
    DINER_DILEMMA,
    HORSERADISH_STORY_THE,
    ROUND_MONEY_BIN_THE,
    BARBER_COLLEGE,
    FOLLOW_THE_RAINBOW,
    ITCHING_TO_SHARE,
    WISPY_WILLIE,
    HAMMY_CAMEL_THE,
    BALLET_EVASIONS,
    CHEAPEST_WEIGH_THE,
    BUM_STEER,
    BEE_BUMBLES,
    MENEHUNE_MYSTERY_THE,
    TURKEY_TROT_AT_ONE_WHISTLE,
    RAFFLE_REVERSAL,
    FIX_UP_MIX_UP,
    SECRET_OF_ATLANTIS_THE,
    HOSPITALITY_WEEK,
    MCDUCK_TAKES_A_DIVE,
    SLIPPERY_SIPPER,
    FLOUR_FOLLIES,
    PRICE_OF_FAME_THE,
    MIDGETS_MADNESS,
    SALMON_DERBY,
    TRALLA_LA,
    OIL_THE_NEWS,
    DIG_IT,
    MENTAL_FEE,
    OUTFOXED_FOX,
    CHELTENHAMS_CHOICE,
    TRAVELLING_TRUANTS,
    RANTS_ABOUT_ANTS,
    SEVEN_CITIES_OF_CIBOLA_THE,
    WRONG_NUMBER,
    TOO_SAFE_SAFE,
    SEARCH_FOR_THE_CUSPIDORIA,
    NEW_YEARS_REVOLUTIONS,
    ICEBOAT_TO_BEAVER_ISLAND,
    MYSTERIOUS_STONE_RAY_THE,
    CAMPAIGN_OF_NOTE_A,
    CASH_ON_THE_BRAIN,
    CLASSY_TAXI,
    BLANKET_INVESTMENT,
    DAFFY_TAFFY_PULL_THE,
    TUCKERED_TIGER_THE,
    DONALD_DUCK_TELLS_ABOUT_KITES,
    LEMMING_WITH_THE_LOCKET_THE,
    EASY_MOWING,
    SKI_LIFT_LETDOWN,
    CAST_OF_THOUSANDS,
    GHOST_SHERIFF_OF_LAST_GASP_THE,
    DESCENT_INTERVAL_A,
    SECRET_OF_HONDORICA,
    DOGCATCHER_DUCK,
    COURTSIDE_HEATING,
    POWER_PLOWING,
    REMEMBER_THIS,
    FABULOUS_PHILOSOPHERS_STONE_THE,
    HEIRLOOM_WATCH,
    DONALDS_RAUCOUS_ROLE,
    GOOD_CANOES_AND_BAD_CANOES,
    DEEP_DECISION,
    SMASH_SUCCESS,
    TROUBLE_INDEMNITY,
    CHICKADEE_CHALLENGE_THE,
    UNORTHODOX_OX_THE,
    GREAT_STEAMBOAT_RACE_THE,
    COME_AS_YOU_ARE,
    ROUNDABOUT_HANDOUT,
    FAULTY_FORTUNE,
    RICHES_RICHES_EVERYWHERE,
    CUSTARD_GUN_THE,
    THREE_UN_DUCKS,
    SECRET_RESOLUTIONS,
    ICE_TAXIS_THE,
    SEARCHING_FOR_A_SUCCESSOR,
    OLYMPIC_HOPEFUL_THE,
    GOLDEN_FLEECING_THE,
    WATT_AN_OCCASION,
    DOUGHNUT_DARE,
    SWEAT_DEAL_A,
    GOPHER_GOOF_UPS,
    IN_THE_SWIM,
    LAND_BENEATH_THE_GROUND,
    TRAPPED_LIGHTNING,
    ART_OF_SECURITY_THE,
    FASHION_FORECAST,
    MUSH,
    CAMPING_CONFUSION,
    MASTER_THE,
    WHALE_OF_A_STORY_A,
    SMOKE_WRITER_IN_THE_SKY,
    INVENTOR_OF_ANYTHING,
    LOST_CROWN_OF_GENGHIS_KHAN_THE,
    LUNCHEON_LAMENT,
    RUNAWAY_TRAIN_THE,
    GOLD_RUSH,
    FIREFLIES_ARE_FREE,
    EARLY_TO_BUILD,
    STATUES_OF_LIMITATIONS,
    BORDERLINE_HERO,
    SECOND_RICHEST_DUCK_THE,
    MIGRATING_MILLIONS,
    CAT_BOX_THE,
    CHINA_SHOP_SHAKEUP,
    BUFFO_OR_BUST,
    POUND_FOR_SOUND,
    FERTILE_ASSETS,
    GRANDMAS_PRESENT,
    KNIGHT_IN_SHINING_ARMOR,
    FEARSOME_FLOWERS,
    DONALDS_PET_SERVICE,
    BACK_TO_LONG_AGO,
    COLOSSALEST_SURPRISE_QUIZ_SHOW_THE,
    FORECASTING_FOLLIES,
    BACKYARD_BONANZA,
    ALL_SEASON_HAT,
    EYES_HAVE_IT_THE,
    RELATIVE_REACTION,
    SECRET_BOOK_THE,
    TREE_TRICK,
    IN_KAKIMAW_COUNTRY,
    LOST_PEG_LEG_MINE_THE,
    LOSING_FACE,
    DAY_DUCKBURG_GOT_DYED_THE,
    PICNIC,
    FISHING_MYSTERY,
    COLD_BARGAIN_A,
    GYROS_IMAGINATION_INVENTION,
    RED_APPLE_SAP,
    SURE_FIRE_GOLD_FINDER_THE,
    SPECIAL_DELIVERY,
    CODE_OF_DUCKBURG_THE,
    LAND_OF_THE_PYGMY_INDIANS,
    NET_WORTH,
    FORBIDDEN_VALLEY,
    FANTASTIC_RIVER_RACE_THE,
    SAGMORE_SPRINGS_HOTEL,
    TENDERFOOT_TRAP_THE,
    MINES_OF_KING_SOLOMON_THE,
    GYRO_BUILDS_A_BETTER_HOUSE,
    HISTORY_TOSSED,
    BLACK_PEARLS_OF_TABU_YAMA_THE,
    AUGUST_ACCIDENT,
    SEPTEMBER_SCRIMMAGE,
    WISHING_STONE_ISLAND,
    ROCKET_RACE_AROUND_THE_WORLD,
    ROSCOE_THE_ROBOT,
    CITY_OF_GOLDEN_ROOFS,
    GETTING_THOR,
    DOGGED_DETERMINATION,
    FORGOTTEN_PRECAUTION,
    BIG_BOBBER_THE,
    WINDFALL_OF_THE_MIND,
    TITANIC_ANTS_THE,
    RESCUE_ENHANCEMENT,
    PERSISTENT_POSTMAN_THE,
    HALF_BAKED_BAKER_THE,
    DODGING_MISS_DAISY,
    MONEY_WELL_THE,
    MILKMAN_THE,
    MOCKING_BIRD_RIDGE,
    OLD_FROGGIE_CATAPULT,
    GOING_TO_PIECES,
    HIGH_RIDER,
    THAT_SINKING_FEELING,
    WATER_SKI_RACE,
    BALMY_SWAMI_THE,
    WINDY_STORY_THE,
    GOLDEN_RIVER_THE,
    MOOLA_ON_THE_MOVE,
    THUMBS_UP,
    KNOW_IT_ALL_MACHINE_THE,
    STRANGE_SHIPWRECKS_THE,
    FABULOUS_TYCOON_THE,
    GYRO_GOES_FOR_A_DIP,
    BILL_WIND,
    TWENTY_FOUR_CARAT_MOON_THE,
    HOUSE_ON_CYCLONE_HILL_THE,
    FORBIDIUM_MONEY_BIN_THE,
    NOBLE_PORPOISES,
    MAGIC_INK_THE,
    SLEEPIES_THE,
    TRACKING_SANDY,
    LITTLEST_CHICKEN_THIEF_THE,
    BEACHCOMBERS_PICNIC_THE,
    LIGHTS_OUT,
    DRAMATIC_DONALD,
    CHRISTMAS_IN_DUCKBURG,
    ROCKET_ROASTED_CHRISTMAS_TURKEY,
    MASTER_MOVER_THE,
    SPRING_FEVER,
    FLYING_DUTCHMAN_THE,
    PYRAMID_SCHEME,
    WISHING_WELL_THE,
    IMMOVABLE_MISER,
    RETURN_TO_PIZEN_BLUFF,
    KRANKENSTEIN_GYRO,
    MONEY_CHAMP_THE,
    HIS_HANDY_ANDY,
    FIREFLY_TRACKER_THE,
    PRIZE_OF_PIZARRO_THE,
    LOVELORN_FIREMAN_THE,
    KITTY_GO_ROUND,
    POOR_LOSER,
    FLOATING_ISLAND_THE,
    CRAWLS_FOR_CASH,
    BLACK_FOREST_RESCUE_THE,
    GOOD_DEEDS_THE,
    BLACK_WEDNESDAY,
    ALL_CHOKED_UP,
    WATCHFUL_PARENTS_THE,
    WAX_MUSEUM_THE,
    PAUL_BUNYAN_MACHINE_THE,
    PIED_PIPER_OF_DUCKBURG_THE,
    KNIGHTS_OF_THE_FLYING_SLEDS,
    FUN_WHATS_THAT,
    WITCHING_STICK_THE,
    INVENTORS_CONTEST_THE,
    JUNGLE_HI_JINKS,
    MASTERING_THE_MATTERHORN,
    ON_THE_DREAM_PLANET,
    TRAIL_TYCOON,
    FLYING_FARMHAND_THE,
    HONEY_OF_A_HEN_A,
    WEATHER_WATCHERS_THE,
    SHEEPISH_COWBOYS_THE,
    GAB_MUFFER_THE,
    BIRD_CAMERA_THE,
    ODD_ORDER_THE,
    STUBBORN_STORK_THE,
    MILKTIME_MELODIES,
    LOST_RABBIT_FOOT_THE,
    OODLES_OF_OOMPH,
    DAISYS_DAZED_DAYS,
    LIBRARIAN_THE,
    DOUBLE_DATE_THE,
    TV_BABYSITTER_THE,
    BEAUTY_QUEEN_THE,
    TIGHT_SHOES,
    FRAMED_MIRROR_THE,
    NEW_GIRL_THE,
    MASTER_GLASSER_THE,
    MONEY_HAT_THE,
    CHRISTMAS_CHA_CHA_THE,
    DONALDS_PARTY,
    ISLAND_IN_THE_SKY,
    UNDER_THE_POLAR_ICE,
    HOUND_OF_THE_WHISKERVILLES,
    TOUCHE_TOUPEE,
    FREE_SKI_SPREE,
    MOPPING_UP,
    SNOW_CHASER_THE,
    RIDING_THE_PONY_EXPRESS,
    CAVE_OF_THE_WINDS,
    MADBALL_PITCHER_THE,
    MIXED_UP_MIXER,
    WANT_TO_BUY_AN_ISLAND,
    FROGGY_FARMER,
    CALL_OF_THE_WILD_THE,
    TALE_OF_THE_TAPE,
    HIS_SHINING_HOUR,
    BEAR_TAMER_THE,
    PIPELINE_TO_DANGER,
    YOICKS_THE_FOX,
    WAR_PAINT,
    DOG_SITTER_THE,
    MYSTERY_OF_THE_LOCH,
    VILLAGE_BLACKSMITH_THE,
    FRAIDY_FALCON_THE,
    ALL_AT_SEA,
    FISHY_WARDEN,
    TWO_WAY_LUCK,
    BALLOONATICS,
    TURKEY_TROUBLE,
    MISSILE_FIZZLE,
    ROCKS_TO_RICHES,
    SITTING_HIGH,
    THATS_NO_FABLE,
    CLOTHES_MAKE_THE_DUCK,
    THAT_SMALL_FEELING,
    MADCAP_MARINER_THE,
    TERRIBLE_TOURIST,
    THRIFT_GIFT_A,
    LOST_FRONTIER,
    WHOLE_HERD_OF_HELP_THE,
    DAY_THE_FARM_STOOD_STILL_THE,
    TRAINING_FARM_FUSS_THE,
    REVERSED_RESCUE_THE,
    YOU_CANT_WIN,
    BILLIONS_IN_THE_HOLE,
    BONGO_ON_THE_CONGO,
    STRANGER_THAN_FICTION,
    BOXED_IN,
    CHUGWAGON_DERBY,
    MYTHTIC_MYSTERY,
    WILY_RIVAL,
    DUCK_LUCK,
    MR_PRIVATE_EYE,
    HOUND_HOUNDER,
    GOLDEN_NUGGET_BOAT_THE,
    FAST_AWAY_CASTAWAY,
    GIFT_LION,
    JET_WITCH,
    BOAT_BUSTER,
    MIDAS_TOUCH_THE,
    MONEY_BAG_GOAT,
    DUCKBURGS_DAY_OF_PERIL,
    NORTHEASTER_ON_CAPE_QUACK,
    MOVIE_MAD,
    TEN_CENT_VALENTINE,
    CAVE_OF_ALI_BABA,
    DEEP_DOWN_DOINGS,
    GREAT_POP_UP_THE,
    JUNGLE_BUNGLE,
    MERRY_FERRY,
    UNSAFE_SAFE_THE,
    MUCH_LUCK_MCDUCK,
    UNCLE_SCROOGE___MONKEY_BUSINESS,
    COLLECTION_DAY,
    SEEING_IS_BELIEVING,
    PLAYMATES,
    RAGS_TO_RICHES,
    ART_APPRECIATION,
    FLOWERS_ARE_FLOWERS,
    MADCAP_INVENTORS,
    MEDALING_AROUND,
    WAY_OUT_YONDER,
    CANDY_KID_THE,
    SPICY_TALE_A,
    FINNY_FUN,
    GETTING_THE_BIRD,
    NEST_EGG_COLLECTOR,
    MILLION_DOLLAR_SHOWER,
    TRICKY_EXPERIMENT,
    MASTER_WRECKER,
    RAVEN_MAD,
    STALWART_RANGER,
    LOG_JOCKEY,
    SNOW_DUSTER,
    ODDBALL_ODYSSEY,
    POSTHASTY_POSTMAN,
    STATUS_SEEKER_THE,
    MATTER_OF_FACTORY_A,
    CHRISTMAS_CHEERS,
    JINXED_JALOPY_RACE_THE,
    FOR_OLD_DIMES_SAKE,
    STONES_THROW_FROM_GHOST_TOWN_A,
    SPARE_THAT_HAIR,
    DUCKS_EYE_VIEW_OF_EUROPE_A,
    CASE_OF_THE_STICKY_MONEY_THE,
    DUELING_TYCOONS,
    WISHFUL_EXCESS,
    SIDEWALK_OF_THE_MIND,
    NO_BARGAIN,
    UP_AND_AT_IT,
    GALL_OF_THE_WILD,
    ZERO_HERO,
    BEACH_BOY,
    CROWN_OF_THE_MAYAS,
    INVISIBLE_INTRUDER_THE,
    ISLE_OF_GOLDEN_GEESE,
    TRAVEL_TIGHTWAD_THE,
    DUCKBURG_PET_PARADE_THE,
    HELPERS_HELPING_HAND_A,
    HAVE_GUN_WILL_DANCE,
    LOST_BENEATH_THE_SEA,
    LEMONADE_FLING_THE,
    FIREMAN_SCROOGE,
    SAVED_BY_THE_BAG,
    ONCE_UPON_A_CARNIVAL,
    DOUBLE_MASQUERADE,
    MAN_VERSUS_MACHINE,
    TICKING_DETECTOR,
    IT_HAPPENED_ONE_WINTER,
    THRIFTY_SPENDTHRIFT_THE,
    FEUD_AND_FAR_BETWEEN,
    BUBBLEWEIGHT_CHAMP,
    JONAH_GYRO,
    MANY_FACES_OF_MAGICA_DE_SPELL_THE,
    CAPN_BLIGHTS_MYSTERY_SHIP,
    LOONY_LUNAR_GOLD_RUSH_THE,
    OLYMPIAN_TORCH_BEARER_THE,
    RUG_RIDERS_IN_THE_SKY,
    HOW_GREEN_WAS_MY_LETTUCE,
    GREAT_WIG_MYSTERY_THE,
    HERO_OF_THE_DIKE,
    INTERPLANETARY_POSTMAN,
    UNFRIENDLY_ENEMIES,
    BILLION_DOLLAR_SAFARI_THE,
    DELIVERY_DILEMMA,
    INSTANT_HERCULES,
    MCDUCK_OF_ARABIA,
    MYSTERY_OF_THE_GHOST_TOWN_RAILROAD,
    DUCK_OUT_OF_LUCK,
    LOCK_OUT_THE,
    BIGGER_THE_BEGGAR_THE,
    PLUMMETING_WITH_PRECISION,
    SNAKE_TAKE,
    SWAMP_OF_NO_RETURN_THE,
    MONKEY_BUSINESS,
    GIANT_ROBOT_ROBBERS_THE,
    LAUNDRY_FOR_LESS,
    LONG_DISTANCE_COLLISION,
    TOP_WAGES,
    NORTH_OF_THE_YUKON,
    DOWN_FOR_THE_COUNT,
    WASTED_WORDS,
    PHANTOM_OF_NOTRE_DUCK_THE,
    SO_FAR_AND_NO_SAFARI,
    QUEEN_OF_THE_WILD_DOG_PACK_THE,
    HOUSE_OF_HAUNTS,
    TREASURE_OF_MARCO_POLO,
    BEAUTY_BUSINESS_THE,
    MICRO_DUCKS_FROM_OUTER_SPACE,
    NOT_SO_ANCIENT_MARINER_THE,
    HEEDLESS_HORSEMAN_THE,
    HALL_OF_THE_MERMAID_QUEEN,
    DOOM_DIAMOND_THE,
    CATTLE_KING_THE,
    KING_SCROOGE_THE_FIRST,
    PERIL_OF_THE_BLACK_FOREST,
    LIFE_SAVERS,
    WHALE_OF_A_GOOD_DEED,
    BAD_DAY_FOR_TROOP_A,
    LET_SLEEPING_BONES_LIE,
    # Not comics below!
    RICH_TOMASSO___ON_COLORING_BARKS,
    DON_AULT___FANTAGRAPHICS_INTRODUCTION,
    DON_AULT___LIFE_AMONG_THE_DUCKS,
    MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD,
    GEORGE_LUCAS___AN_APPRECIATION,
    CENSORSHIP_FIXES_AND_OTHER_CHANGES,
]

assert len(BARKS_TITLES) == NUM_TITLES, f"{len(BARKS_TITLES)} != {NUM_TITLES}"


@dataclass
class ComicBookInfo:
    title: Titles
    is_barks_title: bool
    issue_name: Issues
    issue_number: int
    issue_month: int
    issue_year: int
    submitted_day: int
    submitted_month: int
    submitted_year: int

    @property
    def chronological_number(self) -> int:
        return self.title + 1

    def get_title_str(self) -> str:
        return BARKS_TITLES[self.title]

    def get_issue_name(self) -> str:
        return ISSUE_NAME[self.issue_name]

    def get_short_issue_title(self) -> str:
        short_issue_name = SHORT_ISSUE_NAME[self.issue_name]
        return f"{short_issue_name} {self.issue_number}"

    def get_title_from_issue_name(self) -> str:
        if self.title in USEFUL_TITLES:
            return USEFUL_TITLES[self.title]

        return f"{self.get_issue_name()} #{self.issue_number}"

    def get_formatted_title_from_issue_name(self) -> str:
        if self.issue_name in ISSUE_NAME_WRAPPED:
            issue_name_str = ISSUE_NAME_WRAPPED[self.issue_name] + " #"
        else:
            issue_name_str = self.get_issue_name() + "\n"

        return f"{issue_name_str}{self.issue_number}"

    def get_display_title(self) -> str:
        return self.get_title_str() if self.is_barks_title else f"({self.get_title_str()})"

    @staticmethod
    def get_title_str_from_display_title(display_title: str) -> str:
        return display_title.strip(")(")


# fmt: off
# noinspection LongLine
BARKS_TITLE_INFO: list[ComicBookInfo] = [
    ComicBookInfo(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, True, Issues.FC, 9, 10, 1942, -1, 5, 1942),
    ComicBookInfo(Titles.VICTORY_GARDEN_THE, False, Issues.CS, 31, 4, 1943, -1, 12, 1942),
    ComicBookInfo(Titles.RABBITS_FOOT_THE, False, Issues.CS, 32, 5, 1943, 23, 12, 1942),
    ComicBookInfo(Titles.LIFEGUARD_DAZE, False, Issues.CS, 33, 6, 1943, 29, 1, 1943),
    ComicBookInfo(Titles.GOOD_DEEDS, False, Issues.CS, 34, 7, 1943, 24, 2, 1943),
    ComicBookInfo(Titles.LIMBER_W_GUEST_RANCH_THE, False, Issues.CS, 35, 8, 1943, 17, 3, 1943),
    ComicBookInfo(Titles.MIGHTY_TRAPPER_THE, True, Issues.CS, 36, 9, 1943, 20, 4, 1943),
    ComicBookInfo(Titles.DONALD_DUCK_AND_THE_MUMMYS_RING, True, Issues.FC, 29, 9, 1943, 10, 5, 1943),
    ComicBookInfo(Titles.HARD_LOSER_THE, True, Issues.FC, 29, 9, 1943, 10, 5, 1943),
    ComicBookInfo(Titles.TOO_MANY_PETS, True, Issues.FC, 29, 9, 1943, 29, 5, 1943),
    ComicBookInfo(Titles.GOOD_NEIGHBORS, True, Issues.CS, 38, 11, 1943, 22, 6, 1943),
    ComicBookInfo(Titles.SALESMAN_DONALD, True, Issues.CS, 39, 12, 1943, 23, 7, 1943),
    ComicBookInfo(Titles.SNOW_FUN, True, Issues.CS, 40, 1, 1944, 28, 8, 1943),
    ComicBookInfo(Titles.DUCK_IN_THE_IRON_PANTS_THE, True, Issues.CS, 41, 2, 1944, 22, 9, 1943),
    ComicBookInfo(Titles.KITE_WEATHER, True, Issues.CS, 42, 3, 1944, 20, 10, 1943),
    ComicBookInfo(Titles.THREE_DIRTY_LITTLE_DUCKS, True, Issues.CS, 43, 4, 1944, 27, 11, 1943),
    ComicBookInfo(Titles.MAD_CHEMIST_THE, True, Issues.CS, 44, 5, 1944, 30, 12, 1943),
    ComicBookInfo(Titles.RIVAL_BOATMEN, True, Issues.CS, 45, 6, 1944, 19, 1, 1944),
    ComicBookInfo(Titles.CAMERA_CRAZY, True, Issues.CS, 46, 7, 1944, 29, 2, 1944),
    ComicBookInfo(Titles.FARRAGUT_THE_FALCON, False, Issues.CS, 47, 8, 1944, 1, 4, 1944),
    ComicBookInfo(Titles.PURLOINED_PUTTY_THE, False, Issues.CS, 48, 9, 1944, 26, 4, 1944),
    ComicBookInfo(Titles.HIGH_WIRE_DAREDEVILS, False, Issues.CS, 49, 10, 1944, 26, 5, 1944),
    ComicBookInfo(Titles.TEN_CENTS_WORTH_OF_TROUBLE, False, Issues.CS, 50, 11, 1944, 22, 6, 1944),
    ComicBookInfo(Titles.DONALDS_BAY_LOT, False, Issues.CS, 51, 12, 1944, 27, 7, 1944),
    ComicBookInfo(Titles.FROZEN_GOLD, True, Issues.FC, 62, 1, 1945, 9, 8, 1944),
    ComicBookInfo(Titles.THIEVERY_AFOOT, False, Issues.CS, 52, 1, 1945, 26, 8, 1944),
    ComicBookInfo(Titles.MYSTERY_OF_THE_SWAMP, True, Issues.FC, 62, 1, 1945, 23, 9, 1944),
    ComicBookInfo(Titles.TRAMP_STEAMER_THE, False, Issues.CS, 53, 2, 1945, 6, 10, 1944),
    ComicBookInfo(Titles.LONG_RACE_TO_PUMPKINBURG_THE, False, Issues.CS, 54, 3, 1945, 27, 10, 1944),
    ComicBookInfo(Titles.WEBFOOTED_WRANGLER, False, Issues.CS, 55, 4, 1945, 1, 12, 1944),
    ComicBookInfo(Titles.ICEBOX_ROBBER_THE, False, Issues.CS, 56, 5, 1945, -1, 1, 1945),
    ComicBookInfo(Titles.PECKING_ORDER, False, Issues.CS, 57, 6, 1945, 2, 2, 1945),
    ComicBookInfo(Titles.TAMING_THE_RAPIDS, False, Issues.CS, 58, 7, 1945, 9, 3, 1945),
    ComicBookInfo(Titles.EYES_IN_THE_DARK, False, Issues.CS, 60, 9, 1945, 12, 3, 1945),
    ComicBookInfo(Titles.DAYS_AT_THE_LAZY_K, False, Issues.CS, 59, 8, 1945, 3, 4, 1945),
    ComicBookInfo(Titles.RIDDLE_OF_THE_RED_HAT_THE, True, Issues.FC, 79, 8, 1945, 27, 4, 1945),
    ComicBookInfo(Titles.THUG_BUSTERS, False, Issues.CS, 61, 10, 1945, 31, 5, 1945),
    ComicBookInfo(Titles.GREAT_SKI_RACE_THE, False, Issues.CS, 62, 11, 1945, 27, 6, 1945),
    ComicBookInfo(Titles.FIREBUG_THE, True, Issues.FC, 108, 4, 1946, 19, 7, 1945),
    ComicBookInfo(Titles.TEN_DOLLAR_DITHER, False, Issues.CS, 63, 12, 1945, 2, 8, 1945),
    ComicBookInfo(Titles.DONALD_DUCKS_BEST_CHRISTMAS, True, Issues.FG, 45, 12, 1945, 31, 8, 1945),
    ComicBookInfo(Titles.SILENT_NIGHT, False, Issues.CS, 64, 1, 1946, 31, 8, 1945),
    ComicBookInfo(Titles.DONALD_TAMES_HIS_TEMPER, False, Issues.CS, 64, 1, 1946, 19, 9, 1945),
    ComicBookInfo(Titles.SINGAPORE_JOE, False, Issues.CS, 65, 2, 1946, 4, 10, 1945),
    ComicBookInfo(Titles.MASTER_ICE_FISHER, False, Issues.CS, 66, 3, 1946, 27, 10, 1945),
    ComicBookInfo(Titles.JET_RESCUE, False, Issues.CS, 67, 4, 1946, 23, 11, 1945),
    ComicBookInfo(Titles.DONALDS_MONSTER_KITE, False, Issues.CS, 68, 5, 1946, 4, 1, 1946),
    ComicBookInfo(Titles.TERROR_OF_THE_RIVER_THE, True, Issues.FC, 108, 4, 1946, 25, 1, 1946),
    ComicBookInfo(Titles.SEALS_ARE_SO_SMART, True, Issues.FC, 108, 4, 1946, 25, 1, 1946),
    ComicBookInfo(Titles.BICEPS_BLUES, False, Issues.CS, 69, 6, 1946, 1, 2, 1946),
    ComicBookInfo(Titles.SMUGSNORKLE_SQUATTIE_THE, False, Issues.CS, 70, 7, 1946, 28, 2, 1946),
    ComicBookInfo(Titles.SANTAS_STORMY_VISIT, True, Issues.FG, 46, 12, 1946, 8, 3, 1946),
    ComicBookInfo(Titles.SWIMMING_SWINDLERS, False, Issues.CS, 71, 8, 1946, 26, 3, 1946),
    ComicBookInfo(Titles.PLAYIN_HOOKEY, False, Issues.CS, 72, 9, 1946, 25, 4, 1946),
    ComicBookInfo(Titles.GOLD_FINDER_THE, False, Issues.CS, 73, 10, 1946, 27, 5, 1946),
    ComicBookInfo(Titles.BILL_COLLECTORS_THE, False, Issues.CS, 74, 11, 1946, 14, 6, 1946),
    ComicBookInfo(Titles.TURKEY_RAFFLE, False, Issues.CS, 75, 12, 1946, 8, 7, 1946),
    ComicBookInfo(Titles.MAHARAJAH_DONALD, True, Issues.MC, 4, -1, 1947, 13, 8, 1946),
    ComicBookInfo(Titles.CANTANKEROUS_CAT_THE, False, Issues.CS, 76, 1, 1947, 29, 8, 1946),
    ComicBookInfo(Titles.DONALD_DUCKS_ATOM_BOMB, True, Issues.CH, 1, -1, 1947, 9, 9, 1946),
    ComicBookInfo(Titles.GOING_BUGGY, False, Issues.CS, 77, 2, 1947, 25, 9, 1946),
    ComicBookInfo(Titles.PEACEFUL_HILLS_THE, True, Issues.MC, 4, -1, 1947, 4, 10, 1946),
    ComicBookInfo(Titles.JAM_ROBBERS, False, Issues.CS, 78, 3, 1947, 28, 10, 1946),
    ComicBookInfo(Titles.PICNIC_TRICKS, False, Issues.CS, 79, 4, 1947, 18, 11, 1946),
    ComicBookInfo(Titles.VOLCANO_VALLEY, True, Issues.FC, 147, 5, 1947, 9, 12, 1946),
    ComicBookInfo(Titles.IF_THE_HAT_FITS, False, Issues.FC, 147, 5, 1947, 30, 12, 1946),
    ComicBookInfo(Titles.DONALDS_POSY_PATCH, False, Issues.CS, 80, 5, 1947, 10, 1, 1947),
    ComicBookInfo(Titles.DONALD_MINES_HIS_OWN_BUSINESS, False, Issues.CS, 81, 6, 1947, 28, 1, 1947),
    ComicBookInfo(Titles.MAGICAL_MISERY, False, Issues.CS, 82, 7, 1947, 19, 2, 1947),
    ComicBookInfo(Titles.THREE_GOOD_LITTLE_DUCKS, True, Issues.FG, 47, 12, 1947, 28, 2, 1947),
    ComicBookInfo(Titles.VACATION_MISERY, False, Issues.CS, 83, 8, 1947, 19, 3, 1947),
    ComicBookInfo(Titles.ADVENTURE_DOWN_UNDER, True, Issues.FC, 159, 8, 1947, 4, 4, 1947),
    ComicBookInfo(Titles.GHOST_OF_THE_GROTTO_THE, True, Issues.FC, 159, 8, 1947, 15, 4, 1947),
    ComicBookInfo(Titles.WALTZ_KING_THE, False, Issues.CS, 84, 9, 1947, 1, 5, 1947),
    ComicBookInfo(Titles.MASTERS_OF_MELODY_THE, False, Issues.CS, 85, 10, 1947, 5, 5, 1947),
    ComicBookInfo(Titles.FIREMAN_DONALD, False, Issues.CS, 86, 11, 1947, 23, 6, 1947),
    ComicBookInfo(Titles.CHRISTMAS_ON_BEAR_MOUNTAIN, True, Issues.FC, 178, 12, 1947, 22, 7, 1947),
    ComicBookInfo(Titles.FASHION_IN_FLIGHT, False, Issues.FC, 178, 12, 1947, 22, 7, 1947),
    ComicBookInfo(Titles.TURN_FOR_THE_WORSE, False, Issues.FC, 178, 12, 1947, 22, 7, 1947),
    ComicBookInfo(Titles.MACHINE_MIX_UP, False, Issues.FC, 178, 12, 1947, 22, 7, 1947),
    ComicBookInfo(Titles.TERRIBLE_TURKEY_THE, False, Issues.CS, 87, 12, 1947, 31, 7, 1947),
    ComicBookInfo(Titles.WINTERTIME_WAGER, False, Issues.CS, 88, 1, 1948, 15, 8, 1947),
    ComicBookInfo(Titles.WATCHING_THE_WATCHMAN, False, Issues.CS, 89, 2, 1948, 4, 9, 1947),
    ComicBookInfo(Titles.DARKEST_AFRICA, True, Issues.MC, 20, -1, 1948, 26, 9, 1947),
    ComicBookInfo(Titles.WIRED, False, Issues.CS, 90, 3, 1948, 9, 10, 1947),
    ComicBookInfo(Titles.GOING_APE, False, Issues.CS, 91, 4, 1948, 28, 10, 1947),
    ComicBookInfo(Titles.OLD_CASTLES_SECRET_THE, True, Issues.FC, 189, 6, 1948, 3, 12, 1947),
    ComicBookInfo(Titles.SPOIL_THE_ROD, False, Issues.CS, 92, 5, 1948, 30, 12, 1947),
    ComicBookInfo(Titles.BIRD_WATCHING, False, Issues.FC, 189, 6, 1948, 6, 1, 1948),
    ComicBookInfo(Titles.HORSESHOE_LUCK, False, Issues.FC, 189, 6, 1948, 6, 1, 1948),
    ComicBookInfo(Titles.BEAN_TAKEN, False, Issues.FC, 189, 6, 1948, 6, 1, 1948),
    ComicBookInfo(Titles.ROCKET_RACE_TO_THE_MOON, False, Issues.CS, 93, 6, 1948, 16, 1, 1948),
    ComicBookInfo(Titles.DONALD_OF_THE_COAST_GUARD, False, Issues.CS, 94, 7, 1948, 3, 2, 1948),
    ComicBookInfo(Titles.GLADSTONE_RETURNS, False, Issues.CS, 95, 8, 1948, 19, 2, 1948),
    ComicBookInfo(Titles.SHERIFF_OF_BULLET_VALLEY, True, Issues.FC, 199, 10, 1948, 16, 3, 1948),
    ComicBookInfo(Titles.LINKS_HIJINKS, False, Issues.CS, 96, 9, 1948, 25, 3, 1948),
    ComicBookInfo(Titles.SORRY_TO_BE_SAFE, False, Issues.FC, 199, 10, 1948, 22, 4, 1948),
    ComicBookInfo(Titles.BEST_LAID_PLANS, False, Issues.FC, 199, 10, 1948, 22, 4, 1948),
    ComicBookInfo(Titles.GENUINE_ARTICLE_THE, False, Issues.FC, 199, 10, 1948, 22, 4, 1948),
    ComicBookInfo(Titles.PEARLS_OF_WISDOM, False, Issues.CS, 97, 10, 1948, 29, 4, 1948),
    ComicBookInfo(Titles.FOXY_RELATIONS, False, Issues.CS, 98, 11, 1948, 28, 5, 1948),
    ComicBookInfo(Titles.CRAZY_QUIZ_SHOW_THE, False, Issues.CS, 99, 12, 1948, 10, 6, 1948),
    ComicBookInfo(Titles.GOLDEN_CHRISTMAS_TREE_THE, True, Issues.FC, 203, 12, 1948, 30, 6, 1948),
    ComicBookInfo(Titles.TOYLAND, True, Issues.FG, 48, 12, 1948, 8, 7, 1948),
    ComicBookInfo(Titles.JUMPING_TO_CONCLUSIONS, False, Issues.FC, 203, 12, 1948, 22, 7, 1948),
    ComicBookInfo(Titles.TRUE_TEST_THE, False, Issues.FC, 203, 12, 1948, 22, 7, 1948),
    ComicBookInfo(Titles.ORNAMENTS_ON_THE_WAY, False, Issues.FC, 203, 12, 1948, 22, 7, 1948),
    ComicBookInfo(Titles.TRUANT_OFFICER_DONALD, False, Issues.CS, 100, 1, 1949, 29, 7, 1948),
    ComicBookInfo(Titles.DONALD_DUCKS_WORST_NIGHTMARE, False, Issues.CS, 101, 2, 1949, 26, 8, 1948),
    ComicBookInfo(Titles.PIZEN_SPRING_DUDE_RANCH, False, Issues.CS, 102, 3, 1949, 9, 9, 1948),
    ComicBookInfo(Titles.RIVAL_BEACHCOMBERS, False, Issues.CS, 103, 4, 1949, 23, 9, 1948),
    ComicBookInfo(Titles.LOST_IN_THE_ANDES, True, Issues.FC, 223, 4, 1949, 21, 10, 1948),
    ComicBookInfo(Titles.TOO_FIT_TO_FIT, False, Issues.FC, 223, 4, 1949, 24, 11, 1948),
    ComicBookInfo(Titles.TUNNEL_VISION, False, Issues.FC, 223, 4, 1949, 24, 11, 1948),
    ComicBookInfo(Titles.SLEEPY_SITTERS, False, Issues.FC, 223, 4, 1949, 24, 11, 1948),
    ComicBookInfo(Titles.SUNKEN_YACHT_THE, False, Issues.CS, 104, 5, 1949, 24, 11, 1948),
    ComicBookInfo(Titles.RACE_TO_THE_SOUTH_SEAS, True, Issues.MC, 41, -1, 1949, 15, 12, 1948),
    ComicBookInfo(Titles.MANAGING_THE_ECHO_SYSTEM, False, Issues.CS, 105, 6, 1949, 13, 1, 1949),
    ComicBookInfo(Titles.PLENTY_OF_PETS, False, Issues.CS, 106, 7, 1949, 27, 1, 1949),
    ComicBookInfo(Titles.VOODOO_HOODOO, True, Issues.FC, 238, 8, 1949, 3, 3, 1949),
    ComicBookInfo(Titles.SLIPPERY_SHINE, False, Issues.FC, 238, 8, 1949, 17, 3, 1949),
    ComicBookInfo(Titles.FRACTIOUS_FUN, False, Issues.FC, 238, 8, 1949, 17, 3, 1949),
    ComicBookInfo(Titles.KING_SIZE_CONE, False, Issues.FC, 238, 8, 1949, 17, 3, 1949),
    ComicBookInfo(Titles.SUPER_SNOOPER, False, Issues.CS, 107, 8, 1949, 22, 3, 1949),
    ComicBookInfo(Titles.GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE, False, Issues.CS, 108, 9, 1949, 14, 4, 1949),
    ComicBookInfo(Titles.DOWSING_DUCKS, False, Issues.CS, 109, 10, 1949, 28, 4, 1949),
    ComicBookInfo(Titles.GOLDILOCKS_GAMBIT_THE, False, Issues.CS, 110, 11, 1949, 12, 5, 1949),
    ComicBookInfo(Titles.LETTER_TO_SANTA, True, Issues.CP, 1, 11, 1949, 1, 6, 1949),
    ComicBookInfo(Titles.NO_NOISE_IS_GOOD_NOISE, False, Issues.CP, 1, 11, 1949, 1, 6, 1949),
    ComicBookInfo(Titles.LUCK_OF_THE_NORTH, True, Issues.FC, 256, 12, 1949, 29, 6, 1949),
    ComicBookInfo(Titles.NEW_TOYS, True, Issues.FG, 49, 12, 1949, 7, 7, 1949),
    ComicBookInfo(Titles.TOASTY_TOYS, False, Issues.FC, 256, 12, 1949, 21, 7, 1949),
    ComicBookInfo(Titles.NO_PLACE_TO_HIDE, False, Issues.FC, 256, 12, 1949, 21, 7, 1949),
    ComicBookInfo(Titles.TIED_DOWN_TOOLS, False, Issues.FC, 256, 12, 1949, 21, 7, 1949),
    ComicBookInfo(Titles.DONALDS_LOVE_LETTERS, False, Issues.CS, 111, 12, 1949, 4, 8, 1949),
    ComicBookInfo(Titles.RIP_VAN_DONALD, False, Issues.CS, 112, 1, 1950, 24, 8, 1949),
    ComicBookInfo(Titles.TRAIL_OF_THE_UNICORN, True, Issues.FC, 263, 2, 1950, 8, 9, 1949),
    ComicBookInfo(Titles.LAND_OF_THE_TOTEM_POLES, True, Issues.FC, 263, 2, 1950, 29, 9, 1949),
    ComicBookInfo(Titles.NOISE_NULLIFIER, False, Issues.FC, 263, 2, 1950, 6, 10, 1949),
    ComicBookInfo(Titles.MATINEE_MADNESS, False, Issues.FC, 263, 2, 1950, 6, 10, 1949),
    ComicBookInfo(Titles.FETCHING_PRICE_A, False, Issues.FC, 263, 2, 1950, 6, 10, 1949),
    ComicBookInfo(Titles.SERUM_TO_CODFISH_COVE, False, Issues.CS, 114, 3, 1950, 13, 10, 1949),
    ComicBookInfo(Titles.WILD_ABOUT_FLOWERS, False, Issues.CS, 117, 6, 1950, 27, 10, 1949),
    ComicBookInfo(Titles.IN_ANCIENT_PERSIA, True, Issues.FC, 275, 5, 1950, 23, 11, 1949),
    ComicBookInfo(Titles.VACATION_TIME, True, Issues.VP, 1, 7, 1950, 5, 1, 1950),
    ComicBookInfo(Titles.DONALDS_GRANDMA_DUCK, True, Issues.VP, 1, 7, 1950, 19, 1, 1950),
    ComicBookInfo(Titles.CAMP_COUNSELOR, True, Issues.VP, 1, 7, 1950, 27, 1, 1950),
    ComicBookInfo(Titles.PIXILATED_PARROT_THE, True, Issues.FC, 282, 7, 1950, 23, 2, 1950),
    ComicBookInfo(Titles.MAGIC_HOURGLASS_THE, True, Issues.FC, 291, 9, 1950, 16, 3, 1950),
    ComicBookInfo(Titles.BIG_TOP_BEDLAM, True, Issues.FC, 300, 11, 1950, 20, 4, 1950),
    ComicBookInfo(Titles.YOU_CANT_GUESS, True, Issues.CP, 2, 11, 1950, 24, 5, 1950),
    ComicBookInfo(Titles.DANGEROUS_DISGUISE, True, Issues.FC, 308, 1, 1951, 29, 6, 1950),
    ComicBookInfo(Titles.NO_SUCH_VARMINT, True, Issues.FC, 318, 3, 1951, 27, 7, 1950),
    ComicBookInfo(Titles.BILLIONS_TO_SNEEZE_AT, False, Issues.CS, 124, 1, 1951, 10, 8, 1950),
    ComicBookInfo(Titles.OPERATION_ST_BERNARD, False, Issues.CS, 125, 2, 1951, 31, 8, 1950),
    ComicBookInfo(Titles.FINANCIAL_FABLE_A, False, Issues.CS, 126, 3, 1951, 14, 9, 1950),
    ComicBookInfo(Titles.APRIL_FOOLERS_THE, False, Issues.CS, 127, 4, 1951, 28, 9, 1950),
    ComicBookInfo(Titles.IN_OLD_CALIFORNIA, True, Issues.FC, 328, 5, 1951, 2, 11, 1950),
    ComicBookInfo(Titles.KNIGHTLY_RIVALS, False, Issues.CS, 128, 5, 1951, 30, 11, 1950),
    ComicBookInfo(Titles.POOL_SHARKS, False, Issues.CS, 129, 6, 1951, 7, 12, 1950),
    ComicBookInfo(Titles.TROUBLE_WITH_DIMES_THE, False, Issues.CS, 130, 7, 1951, 28, 12, 1950),
    ComicBookInfo(Titles.GLADSTONES_LUCK, False, Issues.CS, 131, 8, 1951, 11, 1, 1951),
    ComicBookInfo(Titles.TEN_STAR_GENERALS, False, Issues.CS, 132, 9, 1951, 25, 1, 1951),
    ComicBookInfo(Titles.CHRISTMAS_FOR_SHACKTOWN_A, True, Issues.FC, 367, 1, 1952, 15, 3, 1951),
    ComicBookInfo(Titles.ATTIC_ANTICS, False, Issues.CS, 132, 9, 1951, 29, 3, 1951),
    ComicBookInfo(Titles.TRUANT_NEPHEWS_THE, False, Issues.CS, 133, 10, 1951, 12, 4, 1951),
    ComicBookInfo(Titles.TERROR_OF_THE_BEAGLE_BOYS, False, Issues.CS, 134, 11, 1951, 5, 5, 1951),
    ComicBookInfo(Titles.TALKING_PARROT, False, Issues.FC, 356, 11, 1951, 24, 5, 1951),
    ComicBookInfo(Titles.TREEING_OFF, False, Issues.FC, 367, 1, 1952, 24, 5, 1951),
    ComicBookInfo(Titles.CHRISTMAS_KISS, False, Issues.FC, 367, 1, 1952, 24, 5, 1951),
    ComicBookInfo(Titles.PROJECTING_DESIRES, False, Issues.FC, 367, 1, 1952, 24, 5, 1951),
    ComicBookInfo(Titles.BIG_BIN_ON_KILLMOTOR_HILL_THE, False, Issues.CS, 135, 12, 1951, 31, 5, 1951),
    ComicBookInfo(Titles.GLADSTONES_USUAL_VERY_GOOD_YEAR, False, Issues.CS, 136, 1, 1952, 7, 6, 1951),
    ComicBookInfo(Titles.SCREAMING_COWBOY_THE, False, Issues.CS, 137, 2, 1952, 21, 6, 1951),
    ComicBookInfo(Titles.STATUESQUE_SPENDTHRIFTS, False, Issues.CS, 138, 3, 1952, 12, 7, 1951),
    ComicBookInfo(Titles.ROCKET_WING_SAVES_THE_DAY, False, Issues.CS, 139, 4, 1952, 26, 7, 1951),
    ComicBookInfo(Titles.GLADSTONES_TERRIBLE_SECRET, False, Issues.CS, 140, 5, 1952, 23, 8, 1951),
    ComicBookInfo(Titles.ONLY_A_POOR_OLD_MAN, True, Issues.FC, US_1_FC_ISSUE_NUM, 3, 1952, 27, 9, 1951),
    ComicBookInfo(Titles.OSOGOOD_SILVER_POLISH, False, Issues.FC, US_1_FC_ISSUE_NUM, 3, 1952, 27, 9, 1951),
    ComicBookInfo(Titles.COFFEE_FOR_TWO, False, Issues.FC, US_1_FC_ISSUE_NUM, 3, 1952, 27, 9, 1951),
    ComicBookInfo(Titles.SOUPLINE_EIGHT, False, Issues.FC, US_1_FC_ISSUE_NUM, 3, 1952, 27, 9, 1951),
    ComicBookInfo(Titles.THINK_BOX_BOLLIX_THE, False, Issues.CS, 141, 6, 1952, 18, 10, 1951),
    ComicBookInfo(Titles.GOLDEN_HELMET_THE, True, Issues.FC, 408, 7, 1952, 3, 12, 1951),
    ComicBookInfo(Titles.FULL_SERVICE_WINDOWS, False, Issues.FC, 408, 7, 1952, 3, 1, 1952),
    ComicBookInfo(Titles.RIGGED_UP_ROLLER, False, Issues.FC, 408, 7, 1952, 3, 1, 1952),
    ComicBookInfo(Titles.AWASH_IN_SUCCESS, False, Issues.FC, 408, 7, 1952, 3, 1, 1952),
    ComicBookInfo(Titles.HOUSEBOAT_HOLIDAY, False, Issues.CS, 142, 7, 1952, 10, 1, 1952),
    ComicBookInfo(Titles.GEMSTONE_HUNTERS, False, Issues.CS, 143, 8, 1952, 10, 1, 1952),
    ComicBookInfo(Titles.GILDED_MAN_THE, True, Issues.FC, 422, 9, 1952, 31, 1, 1952),
    ComicBookInfo(Titles.STABLE_PRICES, False, Issues.FC, 422, 9, 1952, 31, 1, 1952),
    ComicBookInfo(Titles.ARMORED_RESCUE, False, Issues.FC, 422, 9, 1952, 31, 1, 1952),
    ComicBookInfo(Titles.CRAFTY_CORNER, False, Issues.FC, 422, 9, 1952, 31, 1, 1952),
    ComicBookInfo(Titles.SPENDING_MONEY, False, Issues.CS, 144, 9, 1952, 21, 2, 1952),
    ComicBookInfo(Titles.HYPNO_GUN_THE, False, Issues.CS, 145, 10, 1952, 6, 3, 1952),
    ComicBookInfo(Titles.TRICK_OR_TREAT, True, Issues.DD, 26, 11, 1952, 31, 3, 1952),
    ComicBookInfo(Titles.PRANK_ABOVE_A, False, Issues.DD, 26, 11, 1952, 10, 4, 1952),
    ComicBookInfo(Titles.FRIGHTFUL_FACE, False, Issues.DD, 26, 11, 1952, 10, 4, 1952),
    ComicBookInfo(Titles.HOBBLIN_GOBLINS, True, Issues.DD, 26, 11, 1952, 8, 5, 1952),
    ComicBookInfo(Titles.OMELET, False, Issues.CS, 146, 11, 1952, 15, 5, 1952),
    ComicBookInfo(Titles.CHARITABLE_CHORE_A, False, Issues.CS, 147, 12, 1952, 29, 5, 1952),
    ComicBookInfo(Titles.TURKEY_WITH_ALL_THE_SCHEMINGS, False, Issues.CS, 148, 1, 1953, 12, 6, 1952),
    ComicBookInfo(Titles.FLIP_DECISION, False, Issues.CS, 149, 2, 1953, 30, 6, 1952),
    ComicBookInfo(Titles.MY_LUCKY_VALENTINE, False, Issues.CS, 150, 3, 1953, 30, 6, 1952),
    ComicBookInfo(Titles.FARE_DELAY, False, Issues.FC, US_2_FC_ISSUE_NUM, 3, 1953, 28, 8, 1952),
    ComicBookInfo(Titles.SOMETHIN_FISHY_HERE, True, Issues.FC, US_2_FC_ISSUE_NUM, 3, 1953, -1, 9, 1952),
    ComicBookInfo(Titles.BACK_TO_THE_KLONDIKE, True, Issues.FC, US_2_FC_ISSUE_NUM, 3, 1953, 18, 9, 1952),
    ComicBookInfo(Titles.MONEY_LADDER_THE, False, Issues.FC, US_2_FC_ISSUE_NUM, 3, 1953, 16, 10, 1952),
    ComicBookInfo(Titles.CHECKER_GAME_THE, False, Issues.FC, US_2_FC_ISSUE_NUM, 3, 1953, 16, 10, 1952),
    ComicBookInfo(Titles.EASTER_ELECTION_THE, False, Issues.CS, 151, 4, 1953, 23, 10, 1952),
    ComicBookInfo(Titles.TALKING_DOG_THE, False, Issues.CS, 152, 5, 1953, 30, 10, 1952),
    ComicBookInfo(Titles.WORM_WEARY, False, Issues.CS, 153, 6, 1953, 27, 11, 1952),
    ComicBookInfo(Titles.MUCH_ADO_ABOUT_QUACKLY_HALL, False, Issues.CS, 154, 7, 1953, 27, 11, 1952),
    ComicBookInfo(Titles.SOME_HEIR_OVER_THE_RAINBOW, False, Issues.CS, 155, 8, 1953, 24, 12, 1952),
    ComicBookInfo(Titles.MASTER_RAINMAKER_THE, False, Issues.CS, 156, 9, 1953, 31, 12, 1952),
    ComicBookInfo(Titles.MONEY_STAIRS_THE, False, Issues.CS, 157, 10, 1953, 15, 1, 1953),
    ComicBookInfo(Titles.MILLION_DOLLAR_PIGEON, False, Issues.US, 7, 9, 1954, 25, 2, 1953),
    ComicBookInfo(Titles.TEMPER_TAMPERING, False, Issues.US, 7, 9, 1954, 25, 2, 1953),
    ComicBookInfo(Titles.DINER_DILEMMA, False, Issues.US, 7, 9, 1954, 25, 2, 1953),
    ComicBookInfo(Titles.HORSERADISH_STORY_THE, False, Issues.FC, US_3_FC_ISSUE_NUM, 9, 1953, 26, 2, 1953),
    ComicBookInfo(Titles.ROUND_MONEY_BIN_THE, False, Issues.FC, US_3_FC_ISSUE_NUM, 9, 1953, 26, 2, 1953),
    ComicBookInfo(Titles.BARBER_COLLEGE, False, Issues.FC, US_3_FC_ISSUE_NUM, 9, 1953, 26, 2, 1953),
    ComicBookInfo(Titles.FOLLOW_THE_RAINBOW, False, Issues.FC, US_3_FC_ISSUE_NUM, 9, 1953, 26, 2, 1953),
    ComicBookInfo(Titles.ITCHING_TO_SHARE, False, Issues.FC, US_3_FC_ISSUE_NUM, 9, 1953, 26, 2, 1953),
    ComicBookInfo(Titles.WISPY_WILLIE, False, Issues.CS, 159, 12, 1953, 6, 4, 1953),
    ComicBookInfo(Titles.HAMMY_CAMEL_THE, False, Issues.CS, 160, 1, 1954, 23, 4, 1953),
    ComicBookInfo(Titles.BALLET_EVASIONS, False, Issues.US, 4, 12, 1953, 21, 5, 1953),
    ComicBookInfo(Titles.CHEAPEST_WEIGH_THE, False, Issues.US, 4, 12, 1953, 21, 5, 1953),
    ComicBookInfo(Titles.BUM_STEER, False, Issues.US, 4, 12, 1953, 21, 5, 1953),
    ComicBookInfo(Titles.BEE_BUMBLES, False, Issues.CS, 158, 11, 1953, 26, 5, 1953),
    ComicBookInfo(Titles.MENEHUNE_MYSTERY_THE, False, Issues.US, 4, 12, 1953, 28, 5, 1953),
    ComicBookInfo(Titles.TURKEY_TROT_AT_ONE_WHISTLE, False, Issues.CS, 162, 3, 1954, 25, 6, 1953),
    ComicBookInfo(Titles.RAFFLE_REVERSAL, False, Issues.CS, 163, 4, 1954, 2, 7, 1953),
    ComicBookInfo(Titles.FIX_UP_MIX_UP, False, Issues.CS, 161, 2, 1954, 9, 7, 1953),
    ComicBookInfo(Titles.SECRET_OF_ATLANTIS_THE, False, Issues.US, 5, 3, 1954, 30, 7, 1953),
    ComicBookInfo(Titles.HOSPITALITY_WEEK, False, Issues.US, 5, 3, 1954, 30, 7, 1953),
    ComicBookInfo(Titles.MCDUCK_TAKES_A_DIVE, False, Issues.US, 5, 3, 1954, 30, 7, 1953),
    ComicBookInfo(Titles.SLIPPERY_SIPPER, False, Issues.US, 5, 3, 1954, 30, 7, 1953),
    ComicBookInfo(Titles.FLOUR_FOLLIES, False, Issues.CS, 164, 5, 1954, 27, 8, 1953),
    ComicBookInfo(Titles.PRICE_OF_FAME_THE, False, Issues.CS, 165, 6, 1954, 27, 8, 1953),
    ComicBookInfo(Titles.MIDGETS_MADNESS, False, Issues.CS, 166, 7, 1954, 17, 9, 1953),
    ComicBookInfo(Titles.SALMON_DERBY, False, Issues.CS, 167, 8, 1954, 1, 10, 1953),
    ComicBookInfo(Titles.TRALLA_LA, False, Issues.US, 6, 6, 1954, 29, 10, 1953),
    ComicBookInfo(Titles.OIL_THE_NEWS, False, Issues.US, 6, 6, 1954, 29, 10, 1953),
    ComicBookInfo(Titles.DIG_IT, False, Issues.US, 6, 6, 1954, 29, 10, 1953),
    ComicBookInfo(Titles.MENTAL_FEE, False, Issues.US, 6, 6, 1954, 29, 10, 1953),
    ComicBookInfo(Titles.OUTFOXED_FOX, False, Issues.US, 6, 6, 1954, 26, 11, 1953),
    ComicBookInfo(Titles.CHELTENHAMS_CHOICE, False, Issues.CS, 168, 9, 1954, 3, 12, 1953),
    ComicBookInfo(Titles.TRAVELLING_TRUANTS, False, Issues.CS, 169, 10, 1954, 7, 1, 1954),
    ComicBookInfo(Titles.RANTS_ABOUT_ANTS, False, Issues.CS, 170, 11, 1954, 7, 1, 1954),
    ComicBookInfo(Titles.SEVEN_CITIES_OF_CIBOLA_THE, False, Issues.US, 7, 9, 1954, 28, 1, 1954),
    ComicBookInfo(Titles.WRONG_NUMBER, False, Issues.US, 7, 9, 1954, 25, 2, 1954),
    ComicBookInfo(Titles.TOO_SAFE_SAFE, False, Issues.CS, 171, 12, 1954, 4, 3, 1954),
    ComicBookInfo(Titles.SEARCH_FOR_THE_CUSPIDORIA, False, Issues.CS, 172, 1, 1955, 18, 3, 1954),
    ComicBookInfo(Titles.NEW_YEARS_REVOLUTIONS, False, Issues.CS, 173, 2, 1955, 25, 3, 1954),
    ComicBookInfo(Titles.ICEBOAT_TO_BEAVER_ISLAND, False, Issues.CS, 174, 3, 1955, 22, 4, 1954),
    ComicBookInfo(Titles.MYSTERIOUS_STONE_RAY_THE, False, Issues.US, 8, 12, 1954, 20, 5, 1954),
    ComicBookInfo(Titles.CAMPAIGN_OF_NOTE_A, False, Issues.US, 8, 12, 1954, 10, 6, 1954),
    ComicBookInfo(Titles.CASH_ON_THE_BRAIN, False, Issues.US, 8, 12, 1954, 10, 6, 1954),
    ComicBookInfo(Titles.CLASSY_TAXI, False, Issues.US, 8, 12, 1954, 10, 6, 1954),
    ComicBookInfo(Titles.BLANKET_INVESTMENT, False, Issues.US, 8, 12, 1954, 10, 6, 1954),
    ComicBookInfo(Titles.DAFFY_TAFFY_PULL_THE, False, Issues.CS, 175, 4, 1955, 17, 6, 1954),
    ComicBookInfo(Titles.TUCKERED_TIGER_THE, True, Issues.US, 9, 3, 1955, 24, 6, 1954),
    ComicBookInfo(Titles.DONALD_DUCK_TELLS_ABOUT_KITES, True, Issues.KI, 2, 11, 1954, 8, 7, 1954),
    ComicBookInfo(Titles.LEMMING_WITH_THE_LOCKET_THE, True, Issues.US, 9, 3, 1955, 15, 7, 1954),
    ComicBookInfo(Titles.EASY_MOWING, False, Issues.US, 9, 3, 1955, 22, 7, 1954),
    ComicBookInfo(Titles.SKI_LIFT_LETDOWN, False, Issues.US, 9, 3, 1955, 22, 7, 1954),
    ComicBookInfo(Titles.CAST_OF_THOUSANDS, False, Issues.US, 9, 3, 1955, 22, 7, 1954),
    ComicBookInfo(Titles.GHOST_SHERIFF_OF_LAST_GASP_THE, False, Issues.CS, 176, 5, 1955, 22, 7, 1954),
    ComicBookInfo(Titles.DESCENT_INTERVAL_A, False, Issues.CS, 177, 6, 1955, 29, 7, 1954),
    ComicBookInfo(Titles.SECRET_OF_HONDORICA, True, Issues.DD, 46, 3, 1956, 30, 9, 1954),
    ComicBookInfo(Titles.DOGCATCHER_DUCK, False, Issues.DD, 45, 1, 1956, 14, 10, 1954),
    ComicBookInfo(Titles.COURTSIDE_HEATING, False, Issues.DD, 45, 1, 1956, 14, 10, 1954),
    ComicBookInfo(Titles.POWER_PLOWING, False, Issues.DD, 45, 1, 1956, 14, 10, 1954),
    ComicBookInfo(Titles.REMEMBER_THIS, False, Issues.DD, 45, 1, 1956, 17, 10, 1954),
    ComicBookInfo(Titles.FABULOUS_PHILOSOPHERS_STONE_THE, True, Issues.US, 10, 6, 1955, 28, 10, 1954),
    ComicBookInfo(Titles.HEIRLOOM_WATCH, True, Issues.US, 10, 6, 1955, 11, 11, 1954),
    ComicBookInfo(Titles.DONALDS_RAUCOUS_ROLE, False, Issues.CS, 178, 7, 1955, 26, 11, 1954),
    ComicBookInfo(Titles.GOOD_CANOES_AND_BAD_CANOES, False, Issues.CS, 179, 8, 1955, 26, 11, 1954),
    ComicBookInfo(Titles.DEEP_DECISION, False, Issues.US, 10, 6, 1955, 9, 12, 1954),
    ComicBookInfo(Titles.SMASH_SUCCESS, False, Issues.US, 10, 6, 1955, 9, 12, 1954),
    ComicBookInfo(Titles.TROUBLE_INDEMNITY, False, Issues.CS, 180, 9, 1955, 6, 1, 1955),
    ComicBookInfo(Titles.CHICKADEE_CHALLENGE_THE, False, Issues.CS, 181, 10, 1955, 6, 1, 1955),
    ComicBookInfo(Titles.UNORTHODOX_OX_THE, False, Issues.CS, 182, 11, 1955, 6, 1, 1955),
    ComicBookInfo(Titles.GREAT_STEAMBOAT_RACE_THE, True, Issues.US, 11, 9, 1955, 3, 2, 1955),
    ComicBookInfo(Titles.COME_AS_YOU_ARE, False, Issues.US, 11, 9, 1955, 24, 2, 1955),
    ComicBookInfo(Titles.ROUNDABOUT_HANDOUT, False, Issues.US, 11, 9, 1955, 24, 2, 1955),
    ComicBookInfo(Titles.FAULTY_FORTUNE, False, Issues.US, 14, 6, 1956, 24, 2, 1955),
    ComicBookInfo(Titles.RICHES_RICHES_EVERYWHERE, True, Issues.US, 11, 9, 1955, 10, 3, 1955),
    ComicBookInfo(Titles.CUSTARD_GUN_THE, False, Issues.CS, 183, 12, 1955, 17, 3, 1955),
    ComicBookInfo(Titles.THREE_UN_DUCKS, False, Issues.CS, 184, 1, 1956, 31, 3, 1955),
    ComicBookInfo(Titles.SECRET_RESOLUTIONS, False, Issues.CS, 185, 2, 1956, 21, 4, 1955),
    ComicBookInfo(Titles.ICE_TAXIS_THE, False, Issues.CS, 186, 3, 1956, 21, 4, 1955),
    ComicBookInfo(Titles.SEARCHING_FOR_A_SUCCESSOR, False, Issues.CS, 187, 4, 1956, 28, 4, 1955),
    ComicBookInfo(Titles.OLYMPIC_HOPEFUL_THE, False, Issues.CS, 188, 5, 1956, 28, 4, 1955),
    ComicBookInfo(Titles.GOLDEN_FLEECING_THE, True, Issues.US, 12, 12, 1955, 2, 6, 1955),
    ComicBookInfo(Titles.WATT_AN_OCCASION, False, Issues.US, 12, 12, 1955, 2, 6, 1955),
    ComicBookInfo(Titles.DOUGHNUT_DARE, False, Issues.US, 12, 12, 1955, 2, 6, 1955),
    ComicBookInfo(Titles.SWEAT_DEAL_A, False, Issues.US, 12, 12, 1955, 2, 6, 1955),
    ComicBookInfo(Titles.GOPHER_GOOF_UPS, False, Issues.CS, 189, 6, 1956, 30, 6, 1955),
    ComicBookInfo(Titles.IN_THE_SWIM, False, Issues.CS, 190, 7, 1956, 14, 7, 1955),
    ComicBookInfo(Titles.LAND_BENEATH_THE_GROUND, True, Issues.US, 13, 3, 1956, 18, 8, 1955),
    ComicBookInfo(Titles.TRAPPED_LIGHTNING, False, Issues.US, 13, 3, 1956, 1, 9, 1955),
    ComicBookInfo(Titles.ART_OF_SECURITY_THE, False, Issues.US, 13, 3, 1956, 1, 9, 1955),
    ComicBookInfo(Titles.FASHION_FORECAST, False, Issues.US, 13, 3, 1956, 1, 9, 1955),
    ComicBookInfo(Titles.MUSH, False, Issues.US, 13, 3, 1956, 1, 9, 1955),
    ComicBookInfo(Titles.CAMPING_CONFUSION, False, Issues.CS, 191, 8, 1956, 1, 9, 1955),
    ComicBookInfo(Titles.MASTER_THE, False, Issues.CS, 192, 9, 1956, 22, 9, 1955),
    ComicBookInfo(Titles.WHALE_OF_A_STORY_A, False, Issues.CS, 193, 10, 1956, 29, 9, 1955),
    ComicBookInfo(Titles.SMOKE_WRITER_IN_THE_SKY, False, Issues.CS, 194, 11, 1956, 29, 9, 1955),
    ComicBookInfo(Titles.INVENTOR_OF_ANYTHING, True, Issues.US, 14, 6, 1956, 1, 10, 1955),
    ComicBookInfo(Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE, True, Issues.US, 14, 6, 1956, 3, 11, 1955),
    ComicBookInfo(Titles.LUNCHEON_LAMENT, False, Issues.US, 14, 6, 1956, 17, 11, 1955),
    ComicBookInfo(Titles.RUNAWAY_TRAIN_THE, False, Issues.CS, 195, 12, 1956, 23, 11, 1955),
    ComicBookInfo(Titles.GOLD_RUSH, False, Issues.US, 14, 6, 1956, 8, 12, 1955),
    ComicBookInfo(Titles.FIREFLIES_ARE_FREE, False, Issues.US, 14, 6, 1956, 8, 12, 1955),
    ComicBookInfo(Titles.EARLY_TO_BUILD, False, Issues.US, 17, 3, 1957, 8, 12, 1955),
    ComicBookInfo(Titles.STATUES_OF_LIMITATIONS, False, Issues.CS, 196, 1, 1957, 22, 12, 1955),
    ComicBookInfo(Titles.BORDERLINE_HERO, False, Issues.CS, 197, 2, 1957, 5, 1, 1956),
    ComicBookInfo(Titles.SECOND_RICHEST_DUCK_THE, True, Issues.US, 15, 9, 1956, 2, 2, 1956),
    ComicBookInfo(Titles.MIGRATING_MILLIONS, False, Issues.US, 15, 9, 1956, 9, 2, 1956),
    ComicBookInfo(Titles.CAT_BOX_THE, False, Issues.US, 15, 9, 1956, 9, 2, 1956),
    ComicBookInfo(Titles.CHINA_SHOP_SHAKEUP, False, Issues.US, 17, 3, 1957, 13, 2, 1956),
    ComicBookInfo(Titles.BUFFO_OR_BUST, False, Issues.US, 15, 9, 1956, 23, 2, 1956),
    ComicBookInfo(Titles.POUND_FOR_SOUND, False, Issues.US, 15, 9, 1956, 23, 2, 1956),
    ComicBookInfo(Titles.FERTILE_ASSETS, False, Issues.US, 16, 12, 1956, 23, 2, 1956),
    ComicBookInfo(Titles.GRANDMAS_PRESENT, True, Issues.CP, 8, 12, 1956, 1, 3, 1956),
    ComicBookInfo(Titles.KNIGHT_IN_SHINING_ARMOR, False, Issues.CS, 198, 3, 1957, 15, 3, 1956),
    ComicBookInfo(Titles.FEARSOME_FLOWERS, False, Issues.CS, 214, 7, 1958, 15, 3, 1956),
    ComicBookInfo(Titles.DONALDS_PET_SERVICE, False, Issues.CS, 200, 5, 1957, 5, 4, 1956),
    ComicBookInfo(Titles.BACK_TO_LONG_AGO, True, Issues.US, 16, 12, 1956, 26, 4, 1956),
    ComicBookInfo(Titles.COLOSSALEST_SURPRISE_QUIZ_SHOW_THE, False, Issues.US, 16, 12, 1956, 17, 5, 1956),
    ComicBookInfo(Titles.FORECASTING_FOLLIES, False, Issues.US, 16, 12, 1956, 17, 5, 1956),
    ComicBookInfo(Titles.BACKYARD_BONANZA, False, Issues.US, 16, 12, 1956, 24, 5, 1956),
    ComicBookInfo(Titles.ALL_SEASON_HAT, False, Issues.DD, 51, 1, 1957, 24, 5, 1956),
    ComicBookInfo(Titles.EYES_HAVE_IT_THE, False, Issues.US, 17, 3, 1957, 24, 5, 1956),
    ComicBookInfo(Titles.RELATIVE_REACTION, False, Issues.US, 18, 6, 1957, 24, 5, 1956),
    ComicBookInfo(Titles.SECRET_BOOK_THE, False, Issues.US, 31, 9, 1960, 24, 5, 1956),
    ComicBookInfo(Titles.TREE_TRICK, False, Issues.US, 33, 3, 1961, 24, 5, 1956),
    ComicBookInfo(Titles.IN_KAKIMAW_COUNTRY, False, Issues.CS, 202, 7, 1957, 31, 5, 1956),
    ComicBookInfo(Titles.LOST_PEG_LEG_MINE_THE, True, Issues.DD, 52, 3, 1957, 14, 6, 1956),
    ComicBookInfo(Titles.LOSING_FACE, False, Issues.CS, 204, 9, 1957, 21, 6, 1956),
    ComicBookInfo(Titles.DAY_DUCKBURG_GOT_DYED_THE, False, Issues.CS, 201, 6, 1957, 5, 7, 1956),
    ComicBookInfo(Titles.PICNIC, True, Issues.VP, 8, 7, 1957, 12, 7, 1956),
    ComicBookInfo(Titles.FISHING_MYSTERY, False, Issues.US, 17, 3, 1957, -1, 8, 1956),
    ComicBookInfo(Titles.COLD_BARGAIN_A, True, Issues.US, 17, 3, 1957, 2, 8, 1956),
    ComicBookInfo(Titles.GYROS_IMAGINATION_INVENTION, False, Issues.CS, 199, 4, 1957, 20, 9, 1956),
    ComicBookInfo(Titles.RED_APPLE_SAP, False, Issues.CS, 205, 10, 1957, 25, 9, 1956),
    ComicBookInfo(Titles.SURE_FIRE_GOLD_FINDER_THE, False, Issues.US, 18, 6, 1957, 11, 10, 1956),
    ComicBookInfo(Titles.SPECIAL_DELIVERY, False, Issues.CS, 203, 8, 1957, 11, 10, 1956),
    ComicBookInfo(Titles.CODE_OF_DUCKBURG_THE, False, Issues.CS, 208, 1, 1958, 18, 10, 1956),
    ComicBookInfo(Titles.LAND_OF_THE_PYGMY_INDIANS, True, Issues.US, 18, 6, 1957, 15, 11, 1956),
    ComicBookInfo(Titles.NET_WORTH, False, Issues.US, 18, 6, 1957, 15, 11, 1956),
    ComicBookInfo(Titles.FORBIDDEN_VALLEY, True, Issues.DD, 54, 7, 1957, 13, 12, 1956),
    ComicBookInfo(Titles.FANTASTIC_RIVER_RACE_THE, False, Issues.USGTD, 1, 8, 1957, 10, 1, 1957),
    ComicBookInfo(Titles.SAGMORE_SPRINGS_HOTEL, False, Issues.CS, 206, 11, 1957, 17, 1, 1957),
    ComicBookInfo(Titles.TENDERFOOT_TRAP_THE, False, Issues.CS, 207, 12, 1957, 17, 1, 1957),
    ComicBookInfo(Titles.MINES_OF_KING_SOLOMON_THE, True, Issues.US, 19, 9, 1957, 15, 2, 1957),
    ComicBookInfo(Titles.GYRO_BUILDS_A_BETTER_HOUSE, False, Issues.US, 19, 9, 1957, 28, 2, 1957),
    ComicBookInfo(Titles.HISTORY_TOSSED, False, Issues.US, 19, 9, 1957, 28, 2, 1957),
    ComicBookInfo(Titles.BLACK_PEARLS_OF_TABU_YAMA_THE, False, Issues.CID, 1, 10, 1957, 14, 3, 1957),
    ComicBookInfo(Titles.AUGUST_ACCIDENT, True, Issues.MMA, 1, 12, 1957, 21, 3, 1957),
    ComicBookInfo(Titles.SEPTEMBER_SCRIMMAGE, True, Issues.MMA, 1, 12, 1957, 21, 3, 1957),
    ComicBookInfo(Titles.WISHING_STONE_ISLAND, False, Issues.CS, 211, 4, 1958, 18, 4, 1957),
    ComicBookInfo(Titles.ROCKET_RACE_AROUND_THE_WORLD, False, Issues.CS, 212, 5, 1958, 18, 4, 1957),
    ComicBookInfo(Titles.ROSCOE_THE_ROBOT, False, Issues.US, 20, 12, 1957, 25, 4, 1957),
    ComicBookInfo(Titles.CITY_OF_GOLDEN_ROOFS, True, Issues.US, 20, 12, 1957, 23, 5, 1957),
    ComicBookInfo(Titles.GETTING_THOR, False, Issues.US, 21, 3, 1958, 6, 6, 1957),
    ComicBookInfo(Titles.DOGGED_DETERMINATION, False, Issues.US, 21, 3, 1958, 6, 6, 1957),
    ComicBookInfo(Titles.FORGOTTEN_PRECAUTION, False, Issues.US, 21, 3, 1958, 6, 6, 1957),
    ComicBookInfo(Titles.BIG_BOBBER_THE, False, Issues.US, 33, 3, 1961, 6, 6, 1957),
    ComicBookInfo(Titles.WINDFALL_OF_THE_MIND, False, Issues.US, 21, 3, 1958, 20, 6, 1957),
    ComicBookInfo(Titles.TITANIC_ANTS_THE, True, Issues.DD, 60, 7, 1958, 20, 6, 1957),
    ComicBookInfo(Titles.RESCUE_ENHANCEMENT, False, Issues.US, 20, 12, 1957, 25, 7, 1957),
    ComicBookInfo(Titles.PERSISTENT_POSTMAN_THE, False, Issues.CS, 209, 2, 1958, 25, 7, 1957),
    ComicBookInfo(Titles.HALF_BAKED_BAKER_THE, False, Issues.CS, 210, 3, 1958, 25, 7, 1957),
    ComicBookInfo(Titles.DODGING_MISS_DAISY, False, Issues.CS, 213, 6, 1958, 25, 7, 1957),
    ComicBookInfo(Titles.MONEY_WELL_THE, True, Issues.US, 21, 3, 1958, 22, 8, 1957),
    ComicBookInfo(Titles.MILKMAN_THE, False, Issues.CS, 215, 8, 1958, 19, 9, 1957),
    ComicBookInfo(Titles.MOCKING_BIRD_RIDGE, False, Issues.CS, 215, 8, 1958, 19, 9, 1957),
    ComicBookInfo(Titles.OLD_FROGGIE_CATAPULT, False, Issues.CS, 216, 9, 1958, 1, 10, 1957),
    ComicBookInfo(Titles.GOING_TO_PIECES, False, Issues.US, 22, 6, 1958, 31, 10, 1957),
    ComicBookInfo(Titles.HIGH_RIDER, False, Issues.US, 22, 6, 1958, 31, 10, 1957),
    ComicBookInfo(Titles.THAT_SINKING_FEELING, False, Issues.US, 22, 6, 1958, 31, 10, 1957),
    ComicBookInfo(Titles.WATER_SKI_RACE, True, Issues.DD, 60, 7, 1958, 31, 10, 1957),
    ComicBookInfo(Titles.BALMY_SWAMI_THE, False, Issues.US, 31, 9, 1960, 31, 10, 1957),
    ComicBookInfo(Titles.WINDY_STORY_THE, False, Issues.US, 37, 3, 1962, 31, 10, 1957),
    ComicBookInfo(Titles.GOLDEN_RIVER_THE, True, Issues.US, 22, 6, 1958, 21, 11, 1957),
    ComicBookInfo(Titles.MOOLA_ON_THE_MOVE, False, Issues.US, 23, 9, 1958, 5, 12, 1957),
    ComicBookInfo(Titles.THUMBS_UP, False, Issues.US, 33, 3, 1961, 5, 12, 1957),
    # Typo in original US issue number, was 22, should be 24 for Dec
    ComicBookInfo(Titles.KNOW_IT_ALL_MACHINE_THE, False, Issues.US, 22, 3, 1958, 12, 12, 1957),
    ComicBookInfo(Titles.STRANGE_SHIPWRECKS_THE, True, Issues.US, 23, 9, 1958, 31, 12, 1957),
    ComicBookInfo(Titles.FABULOUS_TYCOON_THE, True, Issues.US, 23, 9, 1958, 9, 1, 1958),
    ComicBookInfo(Titles.GYRO_GOES_FOR_A_DIP, False, Issues.US, 23, 9, 1958, 9, 1, 1958),
    ComicBookInfo(Titles.BILL_WIND, False, Issues.US, 25, 3, 1959, 10, 1, 1958),
    ComicBookInfo(Titles.TWENTY_FOUR_CARAT_MOON_THE, True, Issues.US, 24, 12, 1958, 20, 1, 1958),
    ComicBookInfo(Titles.HOUSE_ON_CYCLONE_HILL_THE, False, Issues.US, 24, 12, 1958, 20, 1, 1958),
    ComicBookInfo(Titles.FORBIDIUM_MONEY_BIN_THE, False, Issues.DIBP, 1, 10, 1958, 4, 2, 1958),
    ComicBookInfo(Titles.NOBLE_PORPOISES, False, Issues.CS, 218, 11, 1958, 14, 2, 1958),
    ComicBookInfo(Titles.MAGIC_INK_THE, True, Issues.US, 24, 12, 1958, 17, 2, 1958),
    ComicBookInfo(Titles.SLEEPIES_THE, False, Issues.DD, 81, 1, 1962, 17, 2, 1958),
    ComicBookInfo(Titles.TRACKING_SANDY, False, Issues.CS, 221, 2, 1959, 5, 3, 1958),
    ComicBookInfo(Titles.LITTLEST_CHICKEN_THIEF_THE, False, Issues.CS, 219, 12, 1958, 12, 3, 1958),
    ComicBookInfo(Titles.BEACHCOMBERS_PICNIC_THE, False, Issues.CS, 224, 5, 1959, 19, 3, 1958),
    # US issue 23 was Sep
    ComicBookInfo(Titles.LIGHTS_OUT, False, Issues.US, 23, 9, 1958, 25, 3, 1958),
    ComicBookInfo(Titles.DRAMATIC_DONALD, False, Issues.CS, 217, 10, 1958, 4, 4, 1958),
    ComicBookInfo(Titles.CHRISTMAS_IN_DUCKBURG, True, Issues.CP, 9, 12, 1958, 6, 4, 1958),
    ComicBookInfo(Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY, False, Issues.CS, 220, 1, 1959, 14, 4, 1958),
    ComicBookInfo(Titles.MASTER_MOVER_THE, False, Issues.CS, 222, 3, 1959, 14, 4, 1958),
    ComicBookInfo(Titles.SPRING_FEVER, False, Issues.CS, 223, 4, 1959, 18, 4, 1958),
    ComicBookInfo(Titles.FLYING_DUTCHMAN_THE, True, Issues.US, 25, 3, 1959, 20, 4, 1958),
    ComicBookInfo(Titles.PYRAMID_SCHEME, False, Issues.US, 25, 3, 1959, 20, 4, 1958),
    ComicBookInfo(Titles.WISHING_WELL_THE, False, Issues.US, 25, 3, 1959, 9, 6, 1958),
    ComicBookInfo(Titles.IMMOVABLE_MISER, False, Issues.US, 25, 3, 1959, 9, 6, 1958),
    ComicBookInfo(Titles.RETURN_TO_PIZEN_BLUFF, False, Issues.US, 26, 6, 1959, 16, 6, 1958),
    ComicBookInfo(Titles.KRANKENSTEIN_GYRO, True, Issues.US, 26, 6, 1959, 16, 6, 1958),
    ComicBookInfo(Titles.MONEY_CHAMP_THE, True, Issues.US, 27, 9, 1959, 12, 7, 1958),
    ComicBookInfo(Titles.HIS_HANDY_ANDY, True, Issues.US, 27, 9, 1959, 12, 7, 1958),
    ComicBookInfo(Titles.FIREFLY_TRACKER_THE, True, Issues.US, 27, 9, 1959, 15, 7, 1958),
    ComicBookInfo(Titles.PRIZE_OF_PIZARRO_THE, True, Issues.US, 26, 6, 1959, 11, 8, 1958),
    ComicBookInfo(Titles.LOVELORN_FIREMAN_THE, False, Issues.CS, 225, 6, 1959, 15, 8, 1958),
    ComicBookInfo(Titles.KITTY_GO_ROUND, False, Issues.US, 25, 3, 1959, 9, 9, 1958),
    ComicBookInfo(Titles.POOR_LOSER, False, Issues.DD, 79, 9, 1961, 9, 9, 1958),
    ComicBookInfo(Titles.FLOATING_ISLAND_THE, False, Issues.CS, 226, 7, 1959, 16, 9, 1958),
    ComicBookInfo(Titles.CRAWLS_FOR_CASH, False, Issues.US, 27, 9, 1959, 1, 10, 1958),
    ComicBookInfo(Titles.BLACK_FOREST_RESCUE_THE, False, Issues.CS, 227, 8, 1959, 10, 10, 1958),
    ComicBookInfo(Titles.GOOD_DEEDS_THE, True, Issues.CS, 229, 10, 1959, 15, 10, 1958),
    ComicBookInfo(Titles.BLACK_WEDNESDAY, True, Issues.CS, 230, 11, 1959, 30, 10, 1958),
    ComicBookInfo(Titles.ALL_CHOKED_UP, False, Issues.US, 23, 9, 1958, 31, 10, 1958),
    ComicBookInfo(Titles.WATCHFUL_PARENTS_THE, False, Issues.CS, 228, 9, 1959, 10, 11, 1958),
    ComicBookInfo(Titles.WAX_MUSEUM_THE, True, Issues.CS, 231, 12, 1959, 17, 11, 1958),
    ComicBookInfo(Titles.PAUL_BUNYAN_MACHINE_THE, True, Issues.US, 28, 12, 1959, 15, 12, 1958),
    ComicBookInfo(Titles.PIED_PIPER_OF_DUCKBURG_THE, True, Issues.USA, 21, 5, 1990, 1, 1, 1959),  # Unfinished story no submission date
    ComicBookInfo(Titles.KNIGHTS_OF_THE_FLYING_SLEDS, True, Issues.CS, 233, 2, 1960, 2, 1, 1959),
    ComicBookInfo(Titles.FUN_WHATS_THAT, True, Issues.SF, 2, 8, 1959, 8, 1, 1959),
    ComicBookInfo(Titles.WITCHING_STICK_THE, True, Issues.US, 28, 12, 1959, 16, 1, 1959),
    ComicBookInfo(Titles.INVENTORS_CONTEST_THE, True, Issues.US, 28, 12, 1959, 16, 1, 1959),
    ComicBookInfo(Titles.JUNGLE_HI_JINKS, True, Issues.SF, 2, 8, 1959, 30, 1, 1959),
    ComicBookInfo(Titles.MASTERING_THE_MATTERHORN, True, Issues.FC, 1025, 8, 1959, 14, 2, 1959),
    ComicBookInfo(Titles.ON_THE_DREAM_PLANET, True, Issues.FC, 1025, 8, 1959, 14, 2, 1959),
    ComicBookInfo(Titles.TRAIL_TYCOON, True, Issues.FC, 1025, 8, 1959, 14, 2, 1959),
    ComicBookInfo(Titles.FLYING_FARMHAND_THE, True, Issues.FC, 1010, 7, 1959, 6, 3, 1959),
    ComicBookInfo(Titles.HONEY_OF_A_HEN_A, True, Issues.FC, 1010, 7, 1959, 6, 3, 1959),
    ComicBookInfo(Titles.WEATHER_WATCHERS_THE, True, Issues.FC, 1010, 7, 1959, 6, 3, 1959),
    ComicBookInfo(Titles.SHEEPISH_COWBOYS_THE, True, Issues.FC, 1010, 7, 1959, 6, 3, 1959),
    ComicBookInfo(Titles.GAB_MUFFER_THE, True, Issues.FC, 1047, 11, 1959, 18, 3, 1959),
    ComicBookInfo(Titles.BIRD_CAMERA_THE, True, Issues.FC, 1047, 11, 1959, 18, 3, 1959),
    ComicBookInfo(Titles.ODD_ORDER_THE, True, Issues.FC, 1047, 11, 1959, 18, 3, 1959),
    ComicBookInfo(Titles.STUBBORN_STORK_THE, True, Issues.FC, 1047, 11, 1959, 14, 4, 1959),
    ComicBookInfo(Titles.MILKTIME_MELODIES, True, Issues.FC, 1047, 11, 1959, 14, 4, 1959),
    ComicBookInfo(Titles.LOST_RABBIT_FOOT_THE, True, Issues.FC, 1047, 11, 1959, 14, 4, 1959),
    ComicBookInfo(Titles.OODLES_OF_OOMPH, True, Issues.US, 29, 3, 1960, 20, 4, 1959),
    ComicBookInfo(Titles.DAISYS_DAZED_DAYS, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.LIBRARIAN_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.DOUBLE_DATE_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.TV_BABYSITTER_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.BEAUTY_QUEEN_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.TIGHT_SHOES, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.FRAMED_MIRROR_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.NEW_GIRL_THE, True, Issues.FC, 1055, 11, 1959, 14, 5, 1959),
    ComicBookInfo(Titles.MASTER_GLASSER_THE, True, Issues.DD, 68, 11, 1959, 20, 5, 1959),
    ComicBookInfo(Titles.MONEY_HAT_THE, False, Issues.US, 28, 12, 1959, 20, 5, 1959),
    ComicBookInfo(Titles.CHRISTMAS_CHA_CHA_THE, True, Issues.CP, 26, 12, 1959, 26, 5, 1959),
    ComicBookInfo(Titles.DONALDS_PARTY, True, Issues.FC, 1055, 11, 1959, 29, 5, 1959),
    ComicBookInfo(Titles.ISLAND_IN_THE_SKY, True, Issues.US, 29, 3, 1960, 15, 6, 1959),
    ComicBookInfo(Titles.UNDER_THE_POLAR_ICE, True, Issues.CS, 232, 1, 1960, 11, 7, 1959),
    ComicBookInfo(Titles.HOUND_OF_THE_WHISKERVILLES, True, Issues.US, 29, 3, 1960, 11, 7, 1959),
    ComicBookInfo(Titles.TOUCHE_TOUPEE, True, Issues.FC, 1073, 1, 1960, 15, 7, 1959),
    ComicBookInfo(Titles.FREE_SKI_SPREE, True, Issues.FC, 1073, 1, 1960, 15, 7, 1959),
    ComicBookInfo(Titles.MOPPING_UP, True, Issues.FC, 1073, 1, 1960, 28, 7, 1959),
    ComicBookInfo(Titles.SNOW_CHASER_THE, True, Issues.FC, 1073, 1, 1960, 28, 7, 1959),
    ComicBookInfo(Titles.RIDING_THE_PONY_EXPRESS, True, Issues.CS, 234, 3, 1960, 17, 8, 1959),
    ComicBookInfo(Titles.CAVE_OF_THE_WINDS, True, Issues.FC, 1095, 4, 1960, 12, 9, 1959),
    ComicBookInfo(Titles.MADBALL_PITCHER_THE, True, Issues.FC, 1095, 4, 1960, 12, 9, 1959),
    ComicBookInfo(Titles.MIXED_UP_MIXER, True, Issues.FC, 1095, 4, 1960, 16, 9, 1959),
    ComicBookInfo(Titles.WANT_TO_BUY_AN_ISLAND, True, Issues.CS, 235, 4, 1960, 28, 9, 1959),
    ComicBookInfo(Titles.FROGGY_FARMER, True, Issues.CS, 236, 5, 1960, 14, 10, 1959),
    ComicBookInfo(Titles.CALL_OF_THE_WILD_THE, True, Issues.FC, 1095, 4, 1960, 19, 10, 1959),
    ComicBookInfo(Titles.TALE_OF_THE_TAPE, False, Issues.FC, 1095, 4, 1960, 19, 10, 1959),
    ComicBookInfo(Titles.HIS_SHINING_HOUR, False, Issues.FC, 1095, 4, 1960, 19, 10, 1959),
    ComicBookInfo(Titles.BEAR_TAMER_THE, True, Issues.FC, 1095, 4, 1960, 29, 10, 1959),
    ComicBookInfo(Titles.PIPELINE_TO_DANGER, True, Issues.US, 30, 6, 1960, 13, 11, 1959),
    ComicBookInfo(Titles.YOICKS_THE_FOX, True, Issues.US, 30, 6, 1960, 9, 12, 1959),
    ComicBookInfo(Titles.WAR_PAINT, True, Issues.US, 30, 6, 1960, 9, 12, 1959),
    ComicBookInfo(Titles.DOG_SITTER_THE, True, Issues.CS, 238, 7, 1960, 7, 1, 1960),
    ComicBookInfo(Titles.MYSTERY_OF_THE_LOCH, True, Issues.CS, 237, 6, 1960, 15, 1, 1960),
    ComicBookInfo(Titles.VILLAGE_BLACKSMITH_THE, True, Issues.CS, 239, 8, 1960, 15, 1, 1960),
    ComicBookInfo(Titles.FRAIDY_FALCON_THE, True, Issues.CS, 240, 9, 1960, 15, 1, 1960),
    ComicBookInfo(Titles.ALL_AT_SEA, True, Issues.US, 31, 9, 1960, 12, 2, 1960),
    ComicBookInfo(Titles.FISHY_WARDEN, True, Issues.US, 31, 9, 1960, 16, 2, 1960),
    ComicBookInfo(Titles.TWO_WAY_LUCK, True, Issues.US, 31, 9, 1960, 26, 2, 1960),
    ComicBookInfo(Titles.BALLOONATICS, True, Issues.CS, 242, 11, 1960, 11, 3, 1960),
    ComicBookInfo(Titles.TURKEY_TROUBLE, True, Issues.CS, 243, 12, 1960, 11, 4, 1960),
    ComicBookInfo(Titles.MISSILE_FIZZLE, True, Issues.CS, 244, 1, 1961, 11, 4, 1960),
    ComicBookInfo(Titles.ROCKS_TO_RICHES, True, Issues.CS, 241, 10, 1960, 18, 4, 1960),
    ComicBookInfo(Titles.SITTING_HIGH, True, Issues.CS, 245, 2, 1961, 18, 4, 1960),
    ComicBookInfo(Titles.THATS_NO_FABLE, True, Issues.US, 32, 12, 1960, 12, 5, 1960),
    ComicBookInfo(Titles.CLOTHES_MAKE_THE_DUCK, True, Issues.US, 32, 12, 1960, 17, 5, 1960),
    ComicBookInfo(Titles.THAT_SMALL_FEELING, True, Issues.US, 32, 12, 1960, 13, 6, 1960),
    ComicBookInfo(Titles.MADCAP_MARINER_THE, False, Issues.CS, 247, 4, 1961, 11, 7, 1960),
    ComicBookInfo(Titles.TERRIBLE_TOURIST, False, Issues.CS, 248, 5, 1961, 11, 7, 1960),
    ComicBookInfo(Titles.THRIFT_GIFT_A, True, Issues.US, 32, 12, 1960, 18, 7, 1960),
    ComicBookInfo(Titles.LOST_FRONTIER, False, Issues.CS, 246, 3, 1961, 18, 7, 1960),
    ComicBookInfo(Titles.WHOLE_HERD_OF_HELP_THE, True, Issues.FC, 1161, 1, 1961, 8, 8, 1960),
    ComicBookInfo(Titles.DAY_THE_FARM_STOOD_STILL_THE, True, Issues.FC, 1161, 1, 1961, 8, 8, 1960),
    ComicBookInfo(Titles.TRAINING_FARM_FUSS_THE, True, Issues.FC, 1161, 1, 1961, 8, 8, 1960),
    ComicBookInfo(Titles.REVERSED_RESCUE_THE, True, Issues.FC, 1161, 1, 1961, 8, 8, 1960),
    ComicBookInfo(Titles.YOU_CANT_WIN, True, Issues.US, 33, 3, 1961, 15, 8, 1960),
    ComicBookInfo(Titles.BILLIONS_IN_THE_HOLE, True, Issues.US, 33, 3, 1961, 3, 9, 1960),
    ComicBookInfo(Titles.BONGO_ON_THE_CONGO, True, Issues.US, 33, 3, 1961, 12, 9, 1960),
    ComicBookInfo(Titles.STRANGER_THAN_FICTION, False, Issues.CS, 249, 6, 1961, 31, 10, 1960),
    ComicBookInfo(Titles.BOXED_IN, False, Issues.CS, 250, 7, 1961, 12, 11, 1960),
    ComicBookInfo(Titles.CHUGWAGON_DERBY, True, Issues.US, 34, 6, 1961, 16, 11, 1960),
    ComicBookInfo(Titles.MYTHTIC_MYSTERY, True, Issues.US, 34, 6, 1961, 10, 12, 1960),
    ComicBookInfo(Titles.WILY_RIVAL, True, Issues.US, 34, 6, 1961, 10, 12, 1960),
    ComicBookInfo(Titles.DUCK_LUCK, False, Issues.CS, 251, 8, 1961, 28, 12, 1960),
    ComicBookInfo(Titles.MR_PRIVATE_EYE, False, Issues.CS, 252, 9, 1961, 10, 1, 1961),
    ComicBookInfo(Titles.HOUND_HOUNDER, False, Issues.CS, 253, 10, 1961, 16, 1, 1961),
    ComicBookInfo(Titles.GOLDEN_NUGGET_BOAT_THE, True, Issues.US, 35, 9, 1961, 16, 2, 1961),
    ComicBookInfo(Titles.FAST_AWAY_CASTAWAY, True, Issues.US, 35, 9, 1961, 24, 2, 1961),
    ComicBookInfo(Titles.GIFT_LION, True, Issues.US, 35, 9, 1961, 24, 2, 1961),
    ComicBookInfo(Titles.JET_WITCH, False, Issues.CS, 254, 11, 1961, 13, 3, 1961),
    ComicBookInfo(Titles.BOAT_BUSTER, False, Issues.CS, 255, 12, 1961, 20, 3, 1961),
    ComicBookInfo(Titles.MIDAS_TOUCH_THE, True, Issues.US, 36, 12, 1961, 17, 4, 1961),
    ComicBookInfo(Titles.MONEY_BAG_GOAT, True, Issues.US, 36, 12, 1961, 3, 5, 1961),
    ComicBookInfo(Titles.DUCKBURGS_DAY_OF_PERIL, True, Issues.US, 36, 12, 1961, 3, 5, 1961),
    ComicBookInfo(Titles.NORTHEASTER_ON_CAPE_QUACK, False, Issues.CS, 256, 1, 1962, 17, 5, 1961),
    ComicBookInfo(Titles.MOVIE_MAD, False, Issues.CS, 257, 2, 1962, 5, 6, 1961),
    ComicBookInfo(Titles.TEN_CENT_VALENTINE, False, Issues.CS, 258, 3, 1962, 14, 6, 1961),
    ComicBookInfo(Titles.CAVE_OF_ALI_BABA, False, Issues.US, 37, 3, 1962, 7, 7, 1961),
    ComicBookInfo(Titles.DEEP_DOWN_DOINGS, False, Issues.US, 37, 3, 1962, 13, 7, 1961),
    ComicBookInfo(Titles.GREAT_POP_UP_THE, False, Issues.US, 37, 3, 1962, 22, 8, 1961),
    ComicBookInfo(Titles.JUNGLE_BUNGLE, False, Issues.CS, 259, 4, 1962, 14, 9, 1961),
    ComicBookInfo(Titles.MERRY_FERRY, False, Issues.CS, 260, 5, 1962, 19, 9, 1961),
    ComicBookInfo(Titles.UNSAFE_SAFE_THE, False, Issues.US, 38, 6, 1962, 11, 10, 1961),
    ComicBookInfo(Titles.MUCH_LUCK_MCDUCK, False, Issues.US, 38, 6, 1962, 16, 10, 1961),
    ComicBookInfo(Titles.UNCLE_SCROOGE___MONKEY_BUSINESS, False, Issues.US, 38, 6, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.COLLECTION_DAY, False, Issues.US, 38, 6, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.SEEING_IS_BELIEVING, False, Issues.US, 38, 6, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.PLAYMATES, False, Issues.US, 38, 6, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.RAGS_TO_RICHES, False, Issues.CS, 262, 7, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.ART_APPRECIATION, False, Issues.US, 39, 9, 1962, 1, 11, 1961),
    ComicBookInfo(Titles.FLOWERS_ARE_FLOWERS, False, Issues.US, 54, 12, 1964, 1, 11, 1961),
    ComicBookInfo(Titles.MADCAP_INVENTORS, False, Issues.US, 38, 6, 1962, 3, 11, 1961),
    ComicBookInfo(Titles.MEDALING_AROUND, False, Issues.CS, 261, 6, 1962, 16, 11, 1961),
    ComicBookInfo(Titles.WAY_OUT_YONDER, False, Issues.CS, 262, 7, 1962, 5, 12, 1961),
    ComicBookInfo(Titles.CANDY_KID_THE, False, Issues.CS, 263, 8, 1962, 13, 12, 1961),
    ComicBookInfo(Titles.SPICY_TALE_A, False, Issues.US, 39, 9, 1962, 15, 1, 1962),
    ComicBookInfo(Titles.FINNY_FUN, False, Issues.US, 39, 9, 1962, 15, 1, 1962),
    ComicBookInfo(Titles.GETTING_THE_BIRD, False, Issues.US, 39, 9, 1962, 15, 1, 1962),
    ComicBookInfo(Titles.NEST_EGG_COLLECTOR, False, Issues.US, 39, 9, 1962, 15, 1, 1962),
    ComicBookInfo(Titles.MILLION_DOLLAR_SHOWER, False, Issues.CS, 297, 6, 1965, 15, 1, 1962),
    ComicBookInfo(Titles.TRICKY_EXPERIMENT, False, Issues.US, 39, 9, 1962, 5, 2, 1962),
    ComicBookInfo(Titles.MASTER_WRECKER, False, Issues.CS, 264, 9, 1962, 9, 2, 1962),
    ComicBookInfo(Titles.RAVEN_MAD, False, Issues.CS, 265, 10, 1962, 17, 2, 1962),
    ComicBookInfo(Titles.STALWART_RANGER, False, Issues.CS, 266, 11, 1962, 5, 3, 1962),
    ComicBookInfo(Titles.LOG_JOCKEY, False, Issues.CS, 267, 12, 1962, 15, 3, 1962),
    ComicBookInfo(Titles.SNOW_DUSTER, False, Issues.US, 41, 3, 1963, 19, 3, 1962),
    ComicBookInfo(Titles.ODDBALL_ODYSSEY, False, Issues.US, 40, 1, 1963, 12, 4, 1962),
    ComicBookInfo(Titles.POSTHASTY_POSTMAN, False, Issues.US, 40, 1, 1963, 18, 4, 1962),
    ComicBookInfo(Titles.STATUS_SEEKER_THE, False, Issues.US, 41, 3, 1963, 16, 5, 1962),
    ComicBookInfo(Titles.MATTER_OF_FACTORY_A, False, Issues.CS, 269, 2, 1963, -1, 6, 1962),
    ComicBookInfo(Titles.CHRISTMAS_CHEERS, False, Issues.CS, 268, 1, 1963, 4, 6, 1962),
    ComicBookInfo(Titles.JINXED_JALOPY_RACE_THE, False, Issues.CS, 270, 3, 1963, 25, 6, 1962),
    ComicBookInfo(Titles.FOR_OLD_DIMES_SAKE, False, Issues.US, 43, 7, 1963, 16, 7, 1962),
    ComicBookInfo(Titles.STONES_THROW_FROM_GHOST_TOWN_A, False, Issues.CS, 271, 4, 1963, 11, 8, 1962),
    ComicBookInfo(Titles.SPARE_THAT_HAIR, False, Issues.CS, 272, 5, 1963, 15, 8, 1962),
    ComicBookInfo(Titles.DUCKS_EYE_VIEW_OF_EUROPE_A, False, Issues.CS, 273, 6, 1963, 27, 8, 1962),
    ComicBookInfo(Titles.CASE_OF_THE_STICKY_MONEY_THE, False, Issues.US, 42, 5, 1963, 17, 9, 1962),
    ComicBookInfo(Titles.DUELING_TYCOONS, False, Issues.US, 42, 5, 1963, 24, 9, 1962),
    ComicBookInfo(Titles.WISHFUL_EXCESS, False, Issues.US, 42, 5, 1963, 24, 9, 1962),
    ComicBookInfo(Titles.SIDEWALK_OF_THE_MIND, False, Issues.US, 42, 5, 1963, 24, 9, 1962),
    ComicBookInfo(Titles.NO_BARGAIN, False, Issues.US, 47, 2, 1964, 24, 9, 1962),
    ComicBookInfo(Titles.UP_AND_AT_IT, False, Issues.US, 47, 2, 1964, 24, 9, 1962),
    ComicBookInfo(Titles.GALL_OF_THE_WILD, False, Issues.CS, 274, 7, 1963, 10, 10, 1962),
    ComicBookInfo(Titles.ZERO_HERO, False, Issues.CS, 275, 8, 1963, 29, 10, 1962),
    ComicBookInfo(Titles.BEACH_BOY, False, Issues.CS, 276, 9, 1963, 13, 11, 1962),
    ComicBookInfo(Titles.CROWN_OF_THE_MAYAS, False, Issues.US, 44, 8, 1963, 10, 12, 1962),
    ComicBookInfo(Titles.INVISIBLE_INTRUDER_THE, False, Issues.US, 44, 8, 1963, 26, 12, 1962),
    ComicBookInfo(Titles.ISLE_OF_GOLDEN_GEESE, False, Issues.US, 45, 10, 1963, 28, 1, 1963),
    ComicBookInfo(Titles.TRAVEL_TIGHTWAD_THE, False, Issues.US, 45, 10, 1963, 7, 2, 1963),
    ComicBookInfo(Titles.DUCKBURG_PET_PARADE_THE, False, Issues.CS, 277, 10, 1963, 7, 3, 1963),
    ComicBookInfo(Titles.HELPERS_HELPING_HAND_A, False, Issues.US, 46, 12, 1963, 19, 3, 1963),
    ComicBookInfo(Titles.HAVE_GUN_WILL_DANCE, False, Issues.CS, 278, 11, 1963, 11, 4, 1963),
    ComicBookInfo(Titles.LOST_BENEATH_THE_SEA, False, Issues.US, 46, 12, 1963, 27, 5, 1963),
    ComicBookInfo(Titles.LEMONADE_FLING_THE, False, Issues.US, 46, 12, 1963, 4, 6, 1963),
    ComicBookInfo(Titles.FIREMAN_SCROOGE, False, Issues.US, 46, 12, 1963, 7, 6, 1963),
    ComicBookInfo(Titles.SAVED_BY_THE_BAG, False, Issues.US, 54, 12, 1964, 7, 6, 1963),
    ComicBookInfo(Titles.ONCE_UPON_A_CARNIVAL, False, Issues.CS, 279, 12, 1963, 1, 7, 1963),
    ComicBookInfo(Titles.DOUBLE_MASQUERADE, False, Issues.CS, 280, 1, 1964, 15, 7, 1963),
    ComicBookInfo(Titles.MAN_VERSUS_MACHINE, False, Issues.US, 47, 2, 1964, 22, 7, 1963),
    ComicBookInfo(Titles.TICKING_DETECTOR, False, Issues.US, 55, 2, 1965, 3, 8, 1963),
    ComicBookInfo(Titles.IT_HAPPENED_ONE_WINTER, False, Issues.US, 61, 1, 1966, 3, 8, 1963),
    ComicBookInfo(Titles.THRIFTY_SPENDTHRIFT_THE, False, Issues.US, 47, 2, 1964, 14, 8, 1963),
    ComicBookInfo(Titles.FEUD_AND_FAR_BETWEEN, False, Issues.CS, 281, 2, 1964, 26, 8, 1963),
    ComicBookInfo(Titles.BUBBLEWEIGHT_CHAMP, False, Issues.CS, 282, 3, 1964, 9, 9, 1963),
    ComicBookInfo(Titles.JONAH_GYRO, False, Issues.US, 48, 3, 1964, 16, 9, 1963),
    ComicBookInfo(Titles.MANY_FACES_OF_MAGICA_DE_SPELL_THE, False, Issues.US, 48, 3, 1964, 5, 10, 1963),
    ComicBookInfo(Titles.CAPN_BLIGHTS_MYSTERY_SHIP, False, Issues.CS, 283, 4, 1964, 29, 10, 1963),
    ComicBookInfo(Titles.LOONY_LUNAR_GOLD_RUSH_THE, False, Issues.US, 49, 5, 1964, 12, 11, 1963),
    ComicBookInfo(Titles.OLYMPIAN_TORCH_BEARER_THE, False, Issues.CS, 286, 7, 1964, 3, 12, 1963),
    ComicBookInfo(Titles.RUG_RIDERS_IN_THE_SKY, False, Issues.US, 50, 7, 1964, 26, 12, 1963),
    ComicBookInfo(Titles.HOW_GREEN_WAS_MY_LETTUCE, False, Issues.US, 51, 8, 1964, 18, 1, 1964),
    ComicBookInfo(Titles.GREAT_WIG_MYSTERY_THE, False, Issues.US, 52, 9, 1964, 19, 2, 1964),
    ComicBookInfo(Titles.HERO_OF_THE_DIKE, False, Issues.CS, 288, 9, 1964, 6, 3, 1964),
    ComicBookInfo(Titles.INTERPLANETARY_POSTMAN, False, Issues.US, 53, 10, 1964, 27, 3, 1964),
    ComicBookInfo(Titles.UNFRIENDLY_ENEMIES, False, Issues.CS, 289, 10, 1964, 6, 4, 1964),
    ComicBookInfo(Titles.BILLION_DOLLAR_SAFARI_THE, False, Issues.US, 54, 12, 1964, 11, 5, 1964),
    ComicBookInfo(Titles.DELIVERY_DILEMMA, False, Issues.CS, 291, 12, 1964, 25, 5, 1964),
    ComicBookInfo(Titles.INSTANT_HERCULES, False, Issues.CS, 292, 1, 1965, 11, 6, 1964),
    ComicBookInfo(Titles.MCDUCK_OF_ARABIA, False, Issues.US, 55, 2, 1965, 13, 7, 1964),
    ComicBookInfo(Titles.MYSTERY_OF_THE_GHOST_TOWN_RAILROAD, False, Issues.US, 56, 3, 1965, 31, 8, 1964),
    ComicBookInfo(Titles.DUCK_OUT_OF_LUCK, False, Issues.CS, 294, 3, 1965, 17, 9, 1964),
    ComicBookInfo(Titles.LOCK_OUT_THE, False, Issues.US, 57, 5, 1965, 19, 9, 1964),
    ComicBookInfo(Titles.BIGGER_THE_BEGGAR_THE, False, Issues.US, 57, 5, 1965, 28, 9, 1964),
    ComicBookInfo(Titles.PLUMMETING_WITH_PRECISION, False, Issues.US, 57, 5, 1965, 28, 9, 1964),
    ComicBookInfo(Titles.SNAKE_TAKE, False, Issues.US, 57, 5, 1965, 28, 9, 1964),
    ComicBookInfo(Titles.SWAMP_OF_NO_RETURN_THE, False, Issues.US, 57, 5, 1965, 30, 10, 1964),
    ComicBookInfo(Titles.MONKEY_BUSINESS, False, Issues.CS, 297, 6, 1965, 16, 11, 1964),
    ComicBookInfo(Titles.GIANT_ROBOT_ROBBERS_THE, False, Issues.US, 58, 7, 1965, 13, 12, 1964),
    ComicBookInfo(Titles.LAUNDRY_FOR_LESS, False, Issues.US, 58, 7, 1965, 21, 12, 1964),
    ComicBookInfo(Titles.LONG_DISTANCE_COLLISION, False, Issues.US, 58, 7, 1965, 21, 12, 1964),
    ComicBookInfo(Titles.TOP_WAGES, False, Issues.US, 61, 1, 1966, 21, 12, 1964),
    ComicBookInfo(Titles.NORTH_OF_THE_YUKON, False, Issues.US, 59, 9, 1965, 25, 1, 1965),
    ComicBookInfo(Titles.DOWN_FOR_THE_COUNT, False, Issues.US, 61, 1, 1966, 1, 2, 1965),
    ComicBookInfo(Titles.WASTED_WORDS, False, Issues.US, 61, 1, 1966, 8, 2, 1965),
    ComicBookInfo(Titles.PHANTOM_OF_NOTRE_DUCK_THE, False, Issues.US, 60, 11, 1965, 4, 3, 1965),
    ComicBookInfo(Titles.SO_FAR_AND_NO_SAFARI, False, Issues.US, 61, 1, 1966, 1, 4, 1965),
    ComicBookInfo(Titles.QUEEN_OF_THE_WILD_DOG_PACK_THE, False, Issues.US, 62, 3, 1966, 12, 5, 1965),
    ComicBookInfo(Titles.HOUSE_OF_HAUNTS, False, Issues.US, 63, 5, 1966, 3, 8, 1965),
    ComicBookInfo(Titles.TREASURE_OF_MARCO_POLO, False, Issues.US, 64, 7, 1966, 13, 10, 1965),
    ComicBookInfo(Titles.BEAUTY_BUSINESS_THE, False, Issues.CS, 308, 5, 1966, 16, 11, 1965),
    ComicBookInfo(Titles.MICRO_DUCKS_FROM_OUTER_SPACE, False, Issues.US, 65, 9, 1966, 7, 12, 1965),
    ComicBookInfo(Titles.NOT_SO_ANCIENT_MARINER_THE, False, Issues.CS, 312, 9, 1966, 5, 1, 1966),
    ComicBookInfo(Titles.HEEDLESS_HORSEMAN_THE, False, Issues.US, 66, 11, 1966, 15, 2, 1966),
    ComicBookInfo(Titles.HALL_OF_THE_MERMAID_QUEEN, False, Issues.US, 68, 3, 1967, 13, 4, 1966),
    ComicBookInfo(Titles.DOOM_DIAMOND_THE, False, Issues.US, 70, 7, 1967, 19, 5, 1966),
    ComicBookInfo(Titles.CATTLE_KING_THE, False, Issues.US, 69, 5, 1967, 27, 5, 1966),
    ComicBookInfo(Titles.KING_SCROOGE_THE_FIRST, False, Issues.US, 71, 10, 1967, 22, 6, 1966),
    ComicBookInfo(Titles.PERIL_OF_THE_BLACK_FOREST, True, Issues.HDL, 6, 7, 1970, 3, 10, 1969),
    ComicBookInfo(Titles.LIFE_SAVERS, True, Issues.HDL, 6, 7, 1970, 3, 10, 1969),
    ComicBookInfo(Titles.WHALE_OF_A_GOOD_DEED, True, Issues.HDL, 7, 10, 1970, 1, 1, 1970),
    ComicBookInfo(Titles.BAD_DAY_FOR_TROOP_A, True, Issues.HDL, 8, 1, 1971, 1, 1, 1970),
    ComicBookInfo(Titles.LET_SLEEPING_BONES_LIE, True, Issues.HDL, 8, 1, 1971, 16, 3, 1970),
    # Not comics below!
    ComicBookInfo(Titles.RICH_TOMASSO___ON_COLORING_BARKS, False, Issues.EXTRAS, 1, 1, 2011, 1, 1, 2011),
    ComicBookInfo(Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION, False, Issues.EXTRAS, 1, 1, 2011, 1, 1, 2011),
    ComicBookInfo(Titles.DON_AULT___LIFE_AMONG_THE_DUCKS, False, Issues.EXTRAS, 1, 1, 2014, 1, 1, 2014),
    ComicBookInfo(Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD, False, Issues.EXTRAS, 1, 1, 2025, 1, 1, 2025),
    ComicBookInfo(Titles.GEORGE_LUCAS___AN_APPRECIATION, False, Issues.EXTRAS, 1, 1, 1983, 1, 1, 1983),
    ComicBookInfo(Titles.CENSORSHIP_FIXES_AND_OTHER_CHANGES, False, Issues.EXTRAS, 6, 8, 2025, 6, 8, 2025),
]
# fmt: on

assert len(BARKS_TITLE_INFO) == NUM_TITLES, f"{len(BARKS_TITLE_INFO)} != {NUM_TITLES}"

USEFUL_TITLES = {
    Titles.HORSERADISH_STORY_THE: "Uncle Scrooge #3",
    Titles.ROUND_MONEY_BIN_THE: "Uncle Scrooge #3",
    Titles.ROSCOE_THE_ROBOT: "Gyro Gearloose",
    Titles.TRAPPED_LIGHTNING: "Gyro Gearloose",
    Titles.CAT_BOX_THE: "Gyro Gearloose",
    Titles.FISHING_MYSTERY: "Gyro Gearloose",
    Titles.FORECASTING_FOLLIES: "Gyro Gearloose",
    Titles.GETTING_THOR: "Gyro Gearloose",
    Titles.GYRO_BUILDS_A_BETTER_HOUSE: "Gyro Gearloose",
    Titles.GYRO_GOES_FOR_A_DIP: "Gyro Gearloose",
    Titles.HOUSE_ON_CYCLONE_HILL_THE: "Gyro Gearloose",
    Titles.FORBIDIUM_MONEY_BIN_THE: "Uncle Scrooge and Gyro",
    Titles.WISHING_WELL_THE: "Gyro Gearloose",
    Titles.KNOW_IT_ALL_MACHINE_THE: "Gyro Gearloose",
    Titles.SURE_FIRE_GOLD_FINDER_THE: "Gyro Gearloose",
}

BARKS_TITLE_DICT: dict[str, Titles] = {
    info.get_title_str(): info.title for info in BARKS_TITLE_INFO
}

NON_COMIC_TITLES = [
    Titles.RICH_TOMASSO___ON_COLORING_BARKS,
    Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION,
    Titles.DON_AULT___LIFE_AMONG_THE_DUCKS,
    Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD,
    Titles.GEORGE_LUCAS___AN_APPRECIATION,
    Titles.CENSORSHIP_FIXES_AND_OTHER_CHANGES,
]

ONE_PAGERS = [
    Titles.IF_THE_HAT_FITS,
    Titles.FASHION_IN_FLIGHT,
    Titles.TURN_FOR_THE_WORSE,
    Titles.MACHINE_MIX_UP,
    Titles.BIRD_WATCHING,
    Titles.HORSESHOE_LUCK,
    Titles.BEAN_TAKEN,
    Titles.SORRY_TO_BE_SAFE,
    Titles.BEST_LAID_PLANS,
    Titles.GENUINE_ARTICLE_THE,
    Titles.JUMPING_TO_CONCLUSIONS,
    Titles.TRUE_TEST_THE,
    Titles.ORNAMENTS_ON_THE_WAY,
    Titles.TOO_FIT_TO_FIT,
    Titles.TUNNEL_VISION,
    Titles.SLEEPY_SITTERS,
    Titles.SLIPPERY_SHINE,
    Titles.FRACTIOUS_FUN,
    Titles.KING_SIZE_CONE,
    Titles.NO_NOISE_IS_GOOD_NOISE,
    Titles.TOASTY_TOYS,
    Titles.NO_PLACE_TO_HIDE,
    Titles.TIED_DOWN_TOOLS,
    Titles.NOISE_NULLIFIER,
    Titles.MATINEE_MADNESS,
    Titles.FETCHING_PRICE_A,
    Titles.TALKING_PARROT,
    Titles.TREEING_OFF,
    Titles.CHRISTMAS_KISS,
    Titles.PROJECTING_DESIRES,
    Titles.OSOGOOD_SILVER_POLISH,
    Titles.COFFEE_FOR_TWO,
    Titles.SOUPLINE_EIGHT,
    Titles.FULL_SERVICE_WINDOWS,
    Titles.RIGGED_UP_ROLLER,
    Titles.AWASH_IN_SUCCESS,
    Titles.STABLE_PRICES,
    Titles.ARMORED_RESCUE,
    Titles.CRAFTY_CORNER,
    Titles.PRANK_ABOVE_A,
    Titles.FRIGHTFUL_FACE,
    Titles.FARE_DELAY,
    Titles.MONEY_LADDER_THE,
    Titles.CHECKER_GAME_THE,
    Titles.TEMPER_TAMPERING,
    Titles.DINER_DILEMMA,
    Titles.BARBER_COLLEGE,
    Titles.FOLLOW_THE_RAINBOW,
    Titles.ITCHING_TO_SHARE,
    Titles.BALLET_EVASIONS,
    Titles.CHEAPEST_WEIGH_THE,
    Titles.BUM_STEER,
    Titles.HOSPITALITY_WEEK,
    Titles.MCDUCK_TAKES_A_DIVE,
    Titles.SLIPPERY_SIPPER,
    Titles.OIL_THE_NEWS,
    Titles.DIG_IT,
    Titles.MENTAL_FEE,
    Titles.WRONG_NUMBER,
    Titles.CASH_ON_THE_BRAIN,
    Titles.CLASSY_TAXI,
    Titles.BLANKET_INVESTMENT,
    Titles.EASY_MOWING,
    Titles.SKI_LIFT_LETDOWN,
    Titles.CAST_OF_THOUSANDS,
    Titles.COURTSIDE_HEATING,
    Titles.POWER_PLOWING,
    Titles.REMEMBER_THIS,
    Titles.DEEP_DECISION,
    Titles.SMASH_SUCCESS,
    Titles.COME_AS_YOU_ARE,
    Titles.ROUNDABOUT_HANDOUT,
    Titles.WATT_AN_OCCASION,
    Titles.DOUGHNUT_DARE,
    Titles.SWEAT_DEAL_A,
    Titles.ART_OF_SECURITY_THE,
    Titles.FASHION_FORECAST,
    Titles.MUSH,
    Titles.LUNCHEON_LAMENT,
    Titles.GOLD_RUSH,
    Titles.FIREFLIES_ARE_FREE,
    Titles.EARLY_TO_BUILD,
    Titles.CHINA_SHOP_SHAKEUP,
    Titles.BUFFO_OR_BUST,
    Titles.POUND_FOR_SOUND,
    Titles.FERTILE_ASSETS,
    Titles.BACKYARD_BONANZA,
    Titles.ALL_SEASON_HAT,
    Titles.EYES_HAVE_IT_THE,
    Titles.RELATIVE_REACTION,
    Titles.SECRET_BOOK_THE,
    Titles.TREE_TRICK,
    Titles.NET_WORTH,
    Titles.HISTORY_TOSSED,
    Titles.DOGGED_DETERMINATION,
    Titles.FORGOTTEN_PRECAUTION,
    Titles.BIG_BOBBER_THE,
    Titles.WINDFALL_OF_THE_MIND,
    Titles.RESCUE_ENHANCEMENT,
    Titles.GOING_TO_PIECES,
    Titles.HIGH_RIDER,
    Titles.THAT_SINKING_FEELING,
    Titles.BALMY_SWAMI_THE,
    Titles.WINDY_STORY_THE,
    Titles.MOOLA_ON_THE_MOVE,
    Titles.THUMBS_UP,
    Titles.BILL_WIND,
    Titles.SLEEPIES_THE,
    Titles.LIGHTS_OUT,
    Titles.IMMOVABLE_MISER,
    Titles.KITTY_GO_ROUND,
    Titles.POOR_LOSER,
    Titles.CRAWLS_FOR_CASH,
    Titles.ALL_CHOKED_UP,
    Titles.BIRD_CAMERA_THE,
    Titles.ODD_ORDER_THE,
    Titles.MONEY_HAT_THE,
    Titles.CALL_OF_THE_WILD_THE,
    Titles.TALE_OF_THE_TAPE,
    Titles.HIS_SHINING_HOUR,
    Titles.THRIFT_GIFT_A,
    Titles.UNCLE_SCROOGE___MONKEY_BUSINESS,
    Titles.COLLECTION_DAY,
    Titles.SEEING_IS_BELIEVING,
    Titles.PLAYMATES,
    Titles.RAGS_TO_RICHES,
    Titles.ART_APPRECIATION,
    Titles.FLOWERS_ARE_FLOWERS,
    Titles.GETTING_THE_BIRD,
    Titles.NEST_EGG_COLLECTOR,
    Titles.MILLION_DOLLAR_SHOWER,
    Titles.DUELING_TYCOONS,
    Titles.WISHFUL_EXCESS,
    Titles.SIDEWALK_OF_THE_MIND,
    Titles.NO_BARGAIN,
    Titles.UP_AND_AT_IT,
    Titles.FIREMAN_SCROOGE,
    Titles.SAVED_BY_THE_BAG,
    Titles.TICKING_DETECTOR,
    Titles.IT_HAPPENED_ONE_WINTER,
    Titles.LOCK_OUT_THE,
    Titles.BIGGER_THE_BEGGAR_THE,
    Titles.PLUMMETING_WITH_PRECISION,
    Titles.SNAKE_TAKE,
    Titles.LAUNDRY_FOR_LESS,
    Titles.LONG_DISTANCE_COLLISION,
    Titles.TOP_WAGES,
    Titles.DOWN_FOR_THE_COUNT,
    Titles.WASTED_WORDS,
]


def get_shortest_issue_name(issue_name: Issues) -> str:
    return "CS" if issue_name == Issues.CS else SHORT_ISSUE_NAME[issue_name]


BARKS_ISSUE_DICT: dict[str, list[Titles]] = {
    f"{get_shortest_issue_name(info.issue_name)} {info.issue_number}": sorted(
        inf.title
        for inf in BARKS_TITLE_INFO
        if (inf.issue_name == info.issue_name)
        and (inf.issue_number == info.issue_number)
        and (inf.title not in ONE_PAGERS)
    )
    for info in BARKS_TITLE_INFO
}
# Add Uncle Scrooge special cases:
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 1"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_1_FC_ISSUE_NUM}"
]
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 2"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_2_FC_ISSUE_NUM}"
]
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 3"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_3_FC_ISSUE_NUM}"
]


def check_story_submitted_order(title_list: list[ComicBookInfo]) -> None:
    prev_chronological_number = 0
    prev_title = ""
    prev_submitted_date = date(1940, 1, 1)
    for title in title_list:
        if not JAN <= title.submitted_month <= DEC:
            msg = f'"{title}": Invalid submission month: {title.submitted_month}.'
            raise RuntimeError(msg)
        submitted_day = 1 if title.submitted_day == -1 else title.submitted_day
        submitted_date = date(
            title.submitted_year,
            title.submitted_month,
            submitted_day,
        )
        if prev_submitted_date > submitted_date:
            msg = (
                f'"{title}": Out of order submitted date {submitted_date}.'
                f' Previous entry: "{prev_title}" - {prev_submitted_date}.'
            )
            raise RuntimeError(msg)
        chronological_number = title.chronological_number
        if prev_chronological_number >= chronological_number:
            msg = (
                f'"{title}": Out of order chronological number {chronological_number}.'
                f' Previous title: "{prev_title}"'
                f" with chronological number {prev_chronological_number}."
            )
            raise RuntimeError(msg)
        prev_title = title
        prev_submitted_date = submitted_date
        prev_chronological_number = chronological_number


def get_safe_title(title: str) -> str:
    safe_title = title.replace("\n", " ")
    safe_title = safe_title.replace("- ", "-")
    safe_title = safe_title.replace('"', "")
    return safe_title  # noqa: RET504


def is_non_comic_title(title_str: str) -> bool:
    return BARKS_TITLE_DICT[title_str] in NON_COMIC_TITLES


TITLE_TO_FILENAME_SPECIAL_CASE_MAP: dict[str, str] = {
    FUN_WHATS_THAT: "Fun What's That",
    WANT_TO_BUY_AN_ISLAND: "Want to Buy an Island",
}
FILENAME_TO_TITLE_SPECIAL_CASE_MAP: dict[str, str] = {
    "Fun What's That": FUN_WHATS_THAT,
    "Want to Buy an Island": WANT_TO_BUY_AN_ISLAND,
}


def get_filename_from_title(title: Titles, ext: str) -> str:
    return get_filename_from_title_str(BARKS_TITLES[title], ext)


def get_filename_from_title_str(title_str: str, ext: str) -> str:
    return TITLE_TO_FILENAME_SPECIAL_CASE_MAP.get(title_str, title_str) + ext


def get_title_str_from_filename(filename: str | PanelPath) -> str:
    if isinstance(filename, str):
        filename = Path(filename)

    # Can't use 'stem' on directories because a title may contain a '.'
    name = filename.name if filename.is_dir() else filename.stem

    return FILENAME_TO_TITLE_SPECIAL_CASE_MAP.get(name, name)
