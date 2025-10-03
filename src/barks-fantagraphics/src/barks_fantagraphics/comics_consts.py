import os
from enum import Enum, auto
from pathlib import Path

from comic_utils.comic_consts import (
    IS_PYINSTALLER_BUNDLE,
    PNG_FILE_EXT,
    PYINSTALLER_BUNDLED_MAIN_DIR,
)

# TODO: Should this dest stuff be here?
DEST_TARGET_WIDTH = 2120
DEST_TARGET_HEIGHT = 3200
DEST_TARGET_X_MARGIN = 100
DEST_TARGET_ASPECT_RATIO = float(DEST_TARGET_HEIGHT) / float(DEST_TARGET_WIDTH)
PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN = 100

PAGE_NUM_X_OFFSET_FROM_CENTRE = 150
PAGE_NUM_X_BLANK_PIXEL_OFFSET = 250
PAGE_NUM_HEIGHT = 40
PAGE_NUM_FONT_SIZE = 30
PAGE_NUM_COLOR = (10, 10, 10)

BARKS = "Carl Barks"
BARKS_ROOT_DIR = os.path.join(str(Path.home()), "Books", BARKS)
THE_COMICS_SUBDIR = "The Comics"
THE_COMICS_DIR = os.path.join(BARKS_ROOT_DIR, THE_COMICS_SUBDIR)
THE_CHRONOLOGICAL_DIRS_SUBDIR = "aaa-Chronological-dirs"
THE_CHRONOLOGICAL_SUBDIR = "Chronological"
THE_CHRONOLOGICAL_DIRS_DIR = os.path.join(THE_COMICS_DIR, THE_CHRONOLOGICAL_DIRS_SUBDIR)
THE_CHRONOLOGICAL_DIR = os.path.join(THE_COMICS_DIR, THE_CHRONOLOGICAL_SUBDIR)
THE_YEARS_SUBDIR = "Chronological Years"
THE_YEARS_COMICS_DIR = os.path.join(THE_COMICS_DIR, THE_YEARS_SUBDIR)
STORY_TITLES_DIR = "story-titles"
IMAGES_SUBDIR = "images"
BOUNDED_SUBDIR = "bounded"

PNG_INSET_DIR = os.path.join(BARKS_ROOT_DIR, "Barks Panels Pngs", "Insets")
PNG_INSET_EXT = PNG_FILE_EXT

INTERNAL_DATA_DIR = (
    PYINSTALLER_BUNDLED_MAIN_DIR / __package__.replace("_", "-") / "data"
    if IS_PYINSTALLER_BUNDLE
    else Path(__file__).parent.parent.parent / "data"
)
assert INTERNAL_DATA_DIR.is_dir(), f'INTERNAL_DATA_DIR "{INTERNAL_DATA_DIR}" does not exist.'

FONT_DIR = INTERNAL_DATA_DIR / "fonts"
CARL_BARKS_FONT = str(FONT_DIR / "Carl Barks Script.ttf")
INTRO_TITLE_DEFAULT_FONT_FILE = CARL_BARKS_FONT
INTRO_TEXT_FONT_FILE = str(FONT_DIR / "Verdana Italic.ttf")
PAGE_NUM_FONT_FILE = str(FONT_DIR / "verdana.ttf")


class PageType(Enum):
    FRONT = auto()
    TITLE = auto()
    COVER = auto()
    SPLASH = auto()
    PAINTING = auto()
    PAINTING_NO_BORDER = auto()
    FRONT_MATTER = auto()
    BODY = auto()
    BACK_MATTER = auto()
    BACK_NO_PANELS = auto()
    BACK_NO_PANELS_DOUBLE = auto()
    BACK_PAINTING = auto()
    BACK_PAINTING_NO_BORDER = auto()
    BLANK_PAGE = auto()


RESTORABLE_PAGE_TYPES = [
    PageType.BODY,
    PageType.FRONT_MATTER,
    PageType.BACK_MATTER,
]

STORY_PAGE_TYPES = [
    PageType.COVER,
    PageType.BODY,
    PageType.FRONT_MATTER,
    PageType.BACK_MATTER,
]
STORY_PAGE_TYPES_STR_LIST = [e.name for e in STORY_PAGE_TYPES]

FRONT_PAGES = [
    PageType.FRONT,
    PageType.TITLE,
    PageType.COVER,
    PageType.SPLASH,
    PageType.PAINTING,
    PageType.PAINTING_NO_BORDER,
]
FRONT_MATTER_PAGES = [*FRONT_PAGES, PageType.FRONT_MATTER]
BACK_MATTER_PAGES = [
    PageType.BACK_MATTER,
    PageType.BACK_NO_PANELS,
    PageType.BACK_NO_PANELS_DOUBLE,
    PageType.BACK_PAINTING,
    PageType.BACK_PAINTING_NO_BORDER,
    PageType.BLANK_PAGE,
]
BACK_MATTER_SINGLE_PAGES = [p for p in BACK_MATTER_PAGES if p != PageType.BLANK_PAGE]
BACK_NO_PANELS_PAGES = [PageType.BACK_NO_PANELS, PageType.BACK_NO_PANELS_DOUBLE]
PAINTING_PAGES = [
    PageType.PAINTING,
    PageType.PAINTING_NO_BORDER,
    PageType.BACK_PAINTING,
    PageType.BACK_PAINTING_NO_BORDER,
]
PAGES_WITHOUT_PANELS = set(
    FRONT_PAGES + PAINTING_PAGES + BACK_NO_PANELS_PAGES + [PageType.BLANK_PAGE]
)
