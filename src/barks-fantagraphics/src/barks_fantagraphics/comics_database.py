# ruff: noqa: ERA001

import configparser
import difflib
from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path

from comic_utils.comic_consts import JPG_FILE_EXT, PNG_FILE_EXT
from loguru import logger

from .barks_titles import get_filename_from_title_str, get_title_str_from_filename
from .comic_book import (
    INTRO_AUTHOR_DEFAULT_FONT_SIZE,
    INTRO_TITLE_DEFAULT_FONT_SIZE,
    ComicBook,
    ComicBookDirs,
    _get_pages_in_order,
    get_main_publication_info,
)
from .comics_consts import (
    BARKS_ROOT_DIR,
    FANTA_VOLUME_OVERRIDES_ROOT,
    IMAGES_SUBDIR,
    INTERNAL_DATA_DIR,
    INTRO_TITLE_DEFAULT_FONT_FILE,
    PNG_INSET_DIR,
    STORY_TITLES_DIR,
    PageType,
)
from .comics_utils import (
    get_formatted_first_published_str,
    get_formatted_submitted_date,
    get_relpath,
)
from .fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    FANTA_SOURCE_COMICS,
    FANTAGRAPHICS_DIRNAME,
    FANTAGRAPHICS_FIXES_DIRNAME,
    FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME,
    FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME,
    FANTAGRAPHICS_RESTORED_DIRNAME,
    FANTAGRAPHICS_RESTORED_OCR_DIRNAME,
    FANTAGRAPHICS_RESTORED_SVG_DIRNAME,
    FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaBook,
    FantaComicBookInfo,
    get_fanta_volume_from_str,
    get_fanta_volume_str,
)
from .page_classes import OriginalPage


class ComicsDatabase:
    def __init__(self, for_building_comics: bool = True) -> None:
        self._database_dir = INTERNAL_DATA_DIR
        self._for_building_comics = for_building_comics
        self._story_titles_dir = _get_story_titles_dir(self._database_dir)
        self._all_comic_book_info = ALL_FANTA_COMIC_BOOK_INFO
        self._ini_files = [p.name for p in self._story_titles_dir.glob("*.ini")]
        self._story_titles = {get_title_str_from_filename(f) for f in self._ini_files}
        self._issue_titles = self._get_all_issue_titles()
        self._inset_dir = PNG_INSET_DIR
        self._inset_ext = PNG_FILE_EXT

    def set_inset_info(self, inset_dir: Path, inset_ext: str) -> None:
        self._inset_dir = inset_dir
        self._inset_ext = inset_ext
        assert self._inset_dir.is_dir()
        assert self._inset_ext in [JPG_FILE_EXT, PNG_FILE_EXT]

    def _get_all_issue_titles(self) -> dict[str, list[str]]:
        all_issues = {}
        for title in self._all_comic_book_info:
            issue_title = self._all_comic_book_info[title].get_short_issue_title()
            if issue_title not in all_issues:
                all_issues[issue_title] = [title]
            else:
                all_issues[issue_title].append(title)

        return all_issues

    def get_comics_database_dir(self) -> Path:
        return self._database_dir

    def get_story_titles_dir(self) -> Path:
        return self._story_titles_dir

    def get_ini_file(self, story_title: str) -> Path:
        return self._story_titles_dir / get_filename_from_title_str(story_title, ".ini")

    def get_fanta_volume(self, story_title: str) -> str:
        return self._all_comic_book_info[story_title].fantagraphics_volume

    def get_fanta_volume_int(self, story_title: str) -> int:
        return get_fanta_volume_from_str(self.get_fanta_volume(story_title))

    def is_story_title(self, title: str) -> tuple[bool, str]:
        if title in self._story_titles:
            return True, ""

        close = difflib.get_close_matches(title, self._story_titles, 1, 0.3)
        close_str = close[0] if close else ""
        return False, close_str

    def get_story_title_from_issue(self, issue_title: str) -> tuple[bool, list[str], str]:
        issue_title = issue_title.upper()
        if issue_title in self._issue_titles:
            return True, self._issue_titles[issue_title], ""

        close = difflib.get_close_matches(issue_title, self._issue_titles, 1, 0.7)
        close_str = close[0] if close else ""
        return False, [], close_str

    def get_all_story_titles(self) -> list[str]:
        return sorted(self._story_titles)

    def get_all_titles_in_fantagraphics_volumes(
        self,
        volume_nums: list[int],
    ) -> list[tuple[str, FantaComicBookInfo]]:
        story_titles = []
        for volume_num in volume_nums:
            fanta_key = get_fanta_volume_str(volume_num)
            for title, comic_info in self._all_comic_book_info.items():
                if comic_info.fantagraphics_volume == fanta_key:
                    story_titles.append((title, comic_info))

        return sorted(story_titles)

    def get_configured_titles_in_fantagraphics_volumes(
        self,
        volume_nums: list[int],
    ) -> list[tuple[str, FantaComicBookInfo]]:
        story_titles = []

        for volume in volume_nums:
            story_titles.extend(self.get_configured_titles_in_fantagraphics_volume(volume))

        return sorted(story_titles)

    def get_configured_titles_in_fantagraphics_volume(
        self,
        volume: int,
    ) -> list[tuple[str, FantaComicBookInfo]]:
        config = ConfigParser(interpolation=ExtendedInterpolation())

        story_titles = []
        fanta_key = f"FANTA_{volume:02}"
        for file in self._ini_files:
            ini_file = self._story_titles_dir / file
            config.read(ini_file)
            if config["info"]["source_comic"] == fanta_key:
                story_title = get_title_str_from_filename(file)
                comic_info = self._all_comic_book_info[story_title]
                story_titles.append((story_title, comic_info))

        return sorted(story_titles)

    # "$HOME/Books/Carl Barks/Fantagraphics/Carl Barks Vol. 2 - Donald Duck - Frozen Gold"
    #     root_dir      = "$HOME/Books/Carl Barks/Fantagraphics"
    #     fanta dirname = "Fantagraphics"
    #     title         = "Carl Barks Vol. 2 - Donald Duck - Frozen Gold"
    @staticmethod
    def get_fantagraphics_volume_title(volume_num: int) -> str:
        fanta_key = f"FANTA_{volume_num:02}"
        fanta_book = FANTA_SOURCE_COMICS[fanta_key]
        return fanta_book.title

    @staticmethod
    def get_num_pages_in_fantagraphics_volume(volume_num: int) -> int:
        fanta_key = f"FANTA_{volume_num:02}"
        fanta_book = FANTA_SOURCE_COMICS[fanta_key]
        return fanta_book.num_pages

    def _get_comic_book_dirs(self, fanta_book: FantaBook) -> ComicBookDirs:
        return ComicBookDirs(
            srce_dir=self.get_fantagraphics_volume_dir(fanta_book.volume),
            srce_upscayled_dir=self.get_fantagraphics_upscayled_volume_dir(fanta_book.volume),
            srce_restored_dir=self.get_fantagraphics_restored_volume_dir(fanta_book.volume),
            srce_restored_upscayled_dir=self.get_fantagraphics_restored_upscayled_volume_dir(
                fanta_book.volume,
            ),
            srce_restored_svg_dir=self.get_fantagraphics_restored_svg_volume_dir(fanta_book.volume),
            srce_restored_raw_ocr_dir=self.get_fantagraphics_restored_raw_ocr_volume_dir(
                fanta_book.volume
            ),
            srce_fixes_dir=self.get_fantagraphics_fixes_volume_dir(fanta_book.volume),
            srce_upscayled_fixes_dir=self.get_fantagraphics_upscayled_fixes_volume_dir(
                fanta_book.volume,
            ),
            panel_segments_dir=self.get_fantagraphics_panel_segments_volume_dir(fanta_book.volume),
        )

    @staticmethod
    def get_root_dir(fanta_subdir: str) -> Path:
        return BARKS_ROOT_DIR / fanta_subdir

    def get_fantagraphics_original_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_dirname())

    @staticmethod
    def get_fantagraphics_dirname() -> str:
        return FANTAGRAPHICS_DIRNAME

    def get_fantagraphics_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_original_root_dir() / title

    def get_fantagraphics_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_upscayled_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_upscayled_dirname())

    @staticmethod
    def get_fantagraphics_upscayled_dirname() -> str:
        return FANTAGRAPHICS_UPSCAYLED_DIRNAME

    def get_fantagraphics_upscayled_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_upscayled_root_dir() / title

    def get_fantagraphics_upscayled_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_upscayled_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_restored_dirname())

    @staticmethod
    def get_fantagraphics_restored_dirname() -> str:
        return FANTAGRAPHICS_RESTORED_DIRNAME

    def get_fantagraphics_restored_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_restored_root_dir() / title

    def get_fantagraphics_restored_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_restored_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_upscayled_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_restored_upscayled_dirname())

    @staticmethod
    def get_fantagraphics_restored_upscayled_dirname() -> str:
        return FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME

    def get_fantagraphics_restored_upscayled_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_restored_upscayled_root_dir() / title

    def get_fantagraphics_restored_upscayled_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_restored_upscayled_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_svg_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_restored_svg_dirname())

    @staticmethod
    def get_fantagraphics_restored_svg_dirname() -> str:
        return FANTAGRAPHICS_RESTORED_SVG_DIRNAME

    def get_fantagraphics_restored_svg_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_restored_svg_root_dir() / title

    def get_fantagraphics_restored_svg_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_restored_svg_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_ocr_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_restored_ocr_dirname())

    def get_fantagraphics_restored_raw_ocr_root_dir(self) -> Path:
        return self.get_fantagraphics_restored_ocr_root_dir() / "Raw"

    @staticmethod
    def get_fantagraphics_restored_ocr_dirname() -> str:
        return FANTAGRAPHICS_RESTORED_OCR_DIRNAME

    def get_fantagraphics_restored_raw_ocr_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_restored_raw_ocr_root_dir() / title

    def get_fantagraphics_panel_segments_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_panel_segments_dirname())

    @staticmethod
    def get_fantagraphics_panel_segments_dirname() -> str:
        return FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME

    def get_fantagraphics_panel_segments_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_panel_segments_root_dir() / title

    def get_fantagraphics_fixes_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_fixes_dirname())

    @staticmethod
    def get_fantagraphics_fixes_dirname() -> str:
        return FANTAGRAPHICS_FIXES_DIRNAME

    def get_fantagraphics_fixes_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_fixes_root_dir() / title

    def get_fantagraphics_fixes_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_fixes_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_upscayled_fixes_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_upscayled_fixes_dirname())

    @staticmethod
    def get_fantagraphics_upscayled_fixes_dirname() -> str:
        return FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME

    def get_fantagraphics_upscayled_fixes_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_upscayled_fixes_root_dir() / title

    def get_fantagraphics_upscayled_fixes_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_upscayled_fixes_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_fixes_scraps_root_dir(self) -> Path:
        return self.get_root_dir(self.get_fantagraphics_fixes_scraps_dirname())

    @staticmethod
    def get_fantagraphics_fixes_scraps_dirname() -> str:
        return FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME

    def get_fantagraphics_fixes_scraps_volume_dir(self, volume_num: int) -> Path:
        title = self.get_fantagraphics_volume_title(volume_num)
        return self.get_fantagraphics_fixes_scraps_root_dir() / title

    def get_fantagraphics_fixes_scraps_volume_image_dir(self, volume_num: int) -> Path:
        return self.get_fantagraphics_fixes_scraps_volume_dir(volume_num) / IMAGES_SUBDIR

    def make_all_fantagraphics_directories(self) -> None:
        FANTA_VOLUME_OVERRIDES_ROOT.mkdir(parents=True, exist_ok=True)

        for volume in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1):
            # Create these directories if they're already not there.
            self._make_vol_dirs(self.get_fantagraphics_upscayled_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_restored_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_restored_upscayled_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_restored_svg_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_restored_raw_ocr_volume_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_fixes_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_upscayled_fixes_volume_image_dir(volume))
            self._make_vol_dirs(self.get_fantagraphics_panel_segments_volume_dir(volume))

            scraps_image_dir = self.get_fantagraphics_fixes_scraps_volume_image_dir(volume)
            self._make_vol_dirs(scraps_image_dir / "standard")
            self._make_vol_dirs(scraps_image_dir / "upscayled")
            self._make_vol_dirs(scraps_image_dir / "restored")

        # Symlinks - just make sure these exist.
        self._check_symlink_exists(self.get_fantagraphics_upscayled_root_dir())
        self._check_symlink_exists(self.get_fantagraphics_restored_upscayled_root_dir())
        self._check_symlink_exists(self.get_fantagraphics_restored_svg_root_dir())

    @staticmethod
    def _make_vol_dirs(vol_dirname: Path) -> None:
        if vol_dirname.is_dir():
            logger.debug(f'Dir already exists - nothing to do: "{vol_dirname}".')
        else:
            vol_dirname.mkdir(parents=True, exist_ok=True)
            logger.info(f'Created dir "{vol_dirname}".')

    @staticmethod
    def _check_symlink_exists(symlink: Path) -> None:
        if not symlink.is_symlink():
            logger.error(f'Symlink not found: "{symlink}".')
        else:
            logger.debug(f'Symlink exists - all good: "{symlink}".')

    def get_fanta_comic_book_info(self, title: str) -> FantaComicBookInfo:
        found, titles, close = self.get_story_title_from_issue(title)
        if found:
            if len(titles) > 1:
                titles_str = ", ".join([f'"{t}"' for t in titles])
                msg = f"You cannot use an issue title that has multiple titles: {titles_str}."
                raise RuntimeError(msg)
            title = titles[0]
        elif close:
            msg = f'Could not find issue title "{title}". Did you mean "{close}"?'
            raise RuntimeError(msg)

        return self._all_comic_book_info[title]

    def get_comic_book(self, title: str) -> ComicBook:
        story_title = ""

        found, titles, close = self.get_story_title_from_issue(title)
        if found:
            if len(titles) > 1:
                titles_str = ", ".join([f'"{t}"' for t in titles])
                msg = f"You cannot use an issue title that has multiple titles: {titles_str}."
                raise RuntimeError(msg)
            story_title = titles[0]
        elif close:
            msg = f'Could not find issue title "{title}". Did you mean "{close}"?'
            raise RuntimeError(msg)

        if not story_title:
            found, close = self.is_story_title(title)
            if found:
                story_title = title
            else:
                if close:
                    msg = f'Could not find title "{title}". Did you mean "{close}"?'
                    raise RuntimeError(msg)
                msg = f'Could not find title "{title}".'
                raise RuntimeError(msg)

        ini_file = self._story_titles_dir / get_filename_from_title_str(story_title, ".ini")
        logger.debug(f'Getting comic book info from config file "{get_relpath(ini_file)}".')

        config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        config.read(ini_file)

        issue_title = config["info"].get("issue_title", "")
        intro_inset_file = self._get_inset_file(ini_file)

        fanta_info: FantaComicBookInfo = self.get_fanta_comic_book_info(story_title)
        fanta_book = FANTA_SOURCE_COMICS[config["info"]["source_comic"]]

        title = config["info"]["title"]
        if not title and fanta_info.comic_book_info.is_barks_title:
            msg = f'"{story_title}" is a barks title and should be set in the ini file.'
            raise RuntimeError(msg)
        if title and not fanta_info.comic_book_info.is_barks_title:
            msg = f'"{story_title}" is a not barks title and should not be set in the ini file.'
            raise RuntimeError(msg)

        srce_dir_num_page_files = fanta_book.num_pages
        comic_book_dirs = self._get_comic_book_dirs(fanta_book)

        publication_date = get_formatted_first_published_str(fanta_info.comic_book_info)
        submitted_date = get_formatted_submitted_date(fanta_info.comic_book_info)

        publication_text = get_main_publication_info(story_title, fanta_info, fanta_book)
        if "extra_pub_info" in config["info"]:
            publication_text += "\n" + config["info"]["extra_pub_info"]

        # noinspection PyTypeChecker
        config_page_images = [
            OriginalPage(key, PageType[config["pages"][key]]) for key in config["pages"]
        ]

        comic = ComicBook(
            ini_file=ini_file,
            title=title,
            title_font_file=INTRO_TITLE_DEFAULT_FONT_FILE,
            title_font_size=config["info"].getint("title_font_size", INTRO_TITLE_DEFAULT_FONT_SIZE),
            issue_title=issue_title,
            author_font_size=config["info"].getint(
                "author_font_size",
                INTRO_AUTHOR_DEFAULT_FONT_SIZE,
            ),
            srce_dir_num_page_files=srce_dir_num_page_files,
            dirs=comic_book_dirs,
            intro_inset_file=intro_inset_file,
            config_page_images=config_page_images,
            page_images_in_order=_get_pages_in_order(config_page_images),
            publication_date=publication_date,
            submitted_date=submitted_date,
            publication_text=publication_text,
            fanta_book=fanta_book,
            fanta_info=fanta_info,
        )

        if self._for_building_comics:
            self.check_comic_ok_for_building(comic)

        return comic

    @staticmethod
    def check_comic_ok_for_building(comic: ComicBook) -> None:
        if not comic.dirs.srce_dir.is_dir():
            msg = f'Could not find srce directory "{comic.dirs.srce_dir}".'
            raise FileNotFoundError(msg)
        if not comic.get_srce_image_dir().is_dir():
            msg = f'Could not find srce image directory "{comic.get_srce_image_dir()}".'
            raise FileNotFoundError(msg)
        if not comic.dirs.srce_upscayled_dir.is_dir():
            msg = f'Could not find srce upscayled directory "{comic.dirs.srce_upscayled_dir}".'
            raise FileNotFoundError(msg)
        if not comic.get_srce_upscayled_image_dir().is_dir():
            msg = (
                f"Could not find srce upscayled image directory"
                f' "{comic.get_srce_upscayled_image_dir()}".'
            )
            raise FileNotFoundError(msg)
        if not comic.dirs.srce_restored_dir.is_dir():
            msg = f'Could not find srce restored directory "{comic.dirs.srce_restored_dir}".'
            raise FileNotFoundError(msg)
        if not comic.get_srce_restored_image_dir().is_dir():
            msg = (
                f"Could not find srce restored image directory"
                f' "{comic.get_srce_restored_image_dir()}".'
            )
            raise FileNotFoundError(msg)
        if not comic.dirs.srce_fixes_dir.is_dir():
            msg = f'Could not find srce fixes directory "{comic.dirs.srce_fixes_dir}".'
            raise FileNotFoundError(msg)
        if not comic.get_srce_original_fixes_image_dir().is_dir():
            msg = (
                f"Could not find srce fixes image directory "
                f'"{comic.get_srce_original_fixes_image_dir()}".'
            )
            raise FileNotFoundError(msg)

    # TODO: Make type PanelPath
    def _get_inset_file(self, ini_file: Path) -> Path:
        assert self._inset_dir
        assert self._inset_ext

        title = ini_file.stem
        inset_filename = title + self._inset_ext

        return self._inset_dir / inset_filename


def _get_story_titles_dir(db_dir: Path) -> Path:
    story_titles_dir = db_dir / STORY_TITLES_DIR

    if not story_titles_dir.is_dir():
        msg = f'Could not find story titles directory "{story_titles_dir}".'
        raise FileNotFoundError(msg)

    return story_titles_dir
