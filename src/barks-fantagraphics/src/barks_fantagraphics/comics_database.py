# ruff: noqa: ERA001

import configparser
import difflib
import functools
from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path

from comic_utils.comic_consts import JPG_FILE_EXT, PNG_FILE_EXT, PanelPath
from loguru import logger

from .barks_covers import get_cover_collection_pages
from .barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from .comic_book import (
    BYLINES,
    INTRO_AUTHOR_DEFAULT_FONT_SIZE,
    INTRO_DEFAULT_BYLINE,
    INTRO_TITLE_DEFAULT_COLOR,
    INTRO_TITLE_DEFAULT_FONT_SIZE,
    TITLE_COLORS,
    ComicBook,
    ComicBookDirs,
    _get_pages_in_order,
    get_main_publication_info,
)
from .comic_book_info import (
    NON_COMIC_TITLES,
    get_filename_from_title_str,
    get_one_pager_collection_pages,
    get_title_str_from_filename,
    is_covers_collection,
    is_one_pager_collection,
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
from .ocr_file_paths import get_ocr_prelim_dir
from .page_classes import OriginalPage


class TitleNotFoundError(Exception):
    """A title that is not a known story; ``title`` holds the title asked for."""

    def __init__(self, msg: str, title: str) -> None:
        super().__init__(msg)
        self.title = title


class ComicsDatabase:
    """The stories that have an ini file, and where each Fantagraphics volume's files are.

    Looks a story up by its title or by an issue holding one story, builds its
    `ComicBook` from its ini file, and names the directories of each kind of file under
    the Barks root: the original scans, the upscayled and restored pages, the fixes, the
    OCR and the panel segments.

    Made with ``for_building_comics`` (the default), each `ComicBook` it builds is also
    checked to be fit for building; a reader of comics already built passes False.
    """

    def __init__(self, for_building_comics: bool = True) -> None:
        self._database_dir = INTERNAL_DATA_DIR
        self._for_building_comics = for_building_comics
        self._story_titles_dir = _get_story_titles_dir(self._database_dir)
        self._all_comic_book_info = ALL_FANTA_COMIC_BOOK_INFO
        self._ini_files = [p.name for p in self._story_titles_dir.glob("*.ini")]
        self._story_titles = {get_title_str_from_filename(f) for f in self._ini_files}
        self._issue_titles = self._get_all_issue_titles()
        self._source_comic_by_ini: dict[str, str] = {}
        self._inset_dir = PNG_INSET_DIR
        self._inset_ext = PNG_FILE_EXT

    def set_inset_info(self, inset_dir: Path, inset_ext: str) -> None:
        """Set where a comic's title-page inset comes from.

        Args:
            inset_dir: The directory holding one inset per story; it must exist.
            inset_ext: The insets' extension, ".jpg" or ".png".

        """
        self._inset_dir = inset_dir
        self._inset_ext = inset_ext
        assert self._inset_dir.is_dir()
        assert self._inset_ext in [JPG_FILE_EXT, PNG_FILE_EXT]

    def _get_all_issue_titles(self) -> dict[str, list[str]]:
        all_issues = {}
        for title, fanta_info in self._all_comic_book_info.items():
            title_str = ENUM_TO_STR_TITLE[title]
            issue_title = fanta_info.get_short_issue_title()
            if issue_title not in all_issues:
                all_issues[issue_title] = [title_str]
            else:
                all_issues[issue_title].append(title_str)

        return all_issues

    def get_comics_database_dir(self) -> Path:
        """Return the directory holding the database's own data files."""
        return self._database_dir

    def get_ini_filenames(self) -> list[str]:
        """Return the name of every story's ini file, in no particular order."""
        return list(self._ini_files)

    def get_story_titles_dir(self) -> Path:
        """Return the directory holding the stories' ini files."""
        return self._story_titles_dir

    def get_ini_file(self, story_title: str) -> Path:
        """Return a story's ini file, whether or not it exists."""
        return self._story_titles_dir / get_filename_from_title_str(story_title, ".ini")

    def get_fanta_volume(self, story_title: str) -> str:
        """Return the key of the Fantagraphics volume a title is in: "FANTA_07"."""
        return self._all_comic_book_info[STR_TITLE_TO_ENUM[story_title]].fantagraphics_volume

    def get_fanta_volume_int(self, story_title: str) -> int:
        """Return the number of the Fantagraphics volume a title is in."""
        return get_fanta_volume_from_str(self.get_fanta_volume(story_title))

    def get_fanta_volume_int_for(self, title: Titles) -> int:
        """Return the Fantagraphics volume number for a title enum.

        Convenience wrapper for callers that already hold a ``Titles`` enum, avoiding a
        redundant enum-to-string conversion at the call site.

        Args:
            title: The title enum member.

        Returns:
            The Fantagraphics volume number containing the title.

        """
        return get_fanta_volume_from_str(self._all_comic_book_info[title].fantagraphics_volume)

    def is_story_title(self, title: str) -> tuple[bool, str]:
        """Return whether a title is a story with an ini file.

        Returns:
            Whether it is, and, if not, the closest story title, or "" if none is close.

        """
        if title in self._story_titles:
            return True, ""

        close = difflib.get_close_matches(title, self._story_titles, 1, 0.3)
        close_str = close[0] if close else ""
        return False, close_str

    def get_story_title_from_issue(self, issue_title: str) -> tuple[bool, list[str], str]:
        """Return the stories that came out in an issue.

        Args:
            issue_title: The issue in short, in any case: "FC 223", "us 4".

        Returns:
            Whether the issue is known; its story titles; and, if it is not known, the
            closest issue, or "" if none is close.

        """
        issue_title = issue_title.upper()
        if issue_title in self._issue_titles:
            return True, self._issue_titles[issue_title], ""

        close = difflib.get_close_matches(issue_title, self._issue_titles, 1, 0.7)
        close_str = close[0] if close else ""
        return False, [], close_str

    def get_all_story_titles(self) -> list[str]:
        """Return the title of every story with an ini file, sorted."""
        return sorted(self._story_titles)

    def get_all_titles_in_fantagraphics_volumes(
        self,
        volume_nums: list[int],
    ) -> list[tuple[str, FantaComicBookInfo]]:
        """Return every title in the given volumes, with or without an ini file.

        Returns:
            ``(title, info)`` pairs, sorted by title.

        """
        story_titles = []
        for volume_num in volume_nums:
            fanta_key = get_fanta_volume_str(volume_num)
            for title, comic_info in self._all_comic_book_info.items():
                if comic_info.fantagraphics_volume == fanta_key:
                    story_titles.append((ENUM_TO_STR_TITLE[title], comic_info))

        return sorted(story_titles)

    def get_configured_titles_in_fantagraphics_volumes(
        self,
        volume_nums: list[int],
        exclude_non_comics: bool = False,
    ) -> list[tuple[str, FantaComicBookInfo]]:
        """Return the titles in the given volumes that have an ini file.

        Args:
            volume_nums: The Fantagraphics volumes.
            exclude_non_comics: Whether to leave the volumes' articles out.

        Returns:
            ``(title, info)`` pairs, sorted by title.

        """
        story_titles = []

        for volume in volume_nums:
            story_titles.extend(
                self.get_configured_titles_in_fantagraphics_volume(volume, exclude_non_comics)
            )

        return sorted(story_titles)

    def get_configured_titles_in_fantagraphics_volume(
        self,
        volume: int,
        exclude_non_comics: bool = False,
    ) -> list[tuple[str, FantaComicBookInfo]]:
        """Return the titles in a volume that have an ini file.

        Args:
            volume: The Fantagraphics volume.
            exclude_non_comics: Whether to leave the volume's articles out.

        Returns:
            ``(title, info)`` pairs, sorted by title.

        """
        story_titles = []
        fanta_key = get_fanta_volume_str(volume)
        for file in self._ini_files:
            if self._get_source_comic(file) == fanta_key:
                story_title = get_title_str_from_filename(file)
                if not exclude_non_comics or STR_TITLE_TO_ENUM[story_title] not in NON_COMIC_TITLES:
                    comic_info = self._all_comic_book_info[STR_TITLE_TO_ENUM[story_title]]
                    story_titles.append((story_title, comic_info))

        return sorted(story_titles)

    def _get_source_comic(self, ini_filename: str) -> str:
        """Return the Fantagraphics volume key a story's ini file names, reading it once.

        Listing every volume would otherwise parse every ini file once per volume.
        """
        source_comic = self._source_comic_by_ini.get(ini_filename)
        if source_comic is None:
            # A parser per file: a shared one keeps the last file's value for a missing key.
            config = ConfigParser(interpolation=ExtendedInterpolation())
            config.read(self._story_titles_dir / ini_filename, encoding="utf-8")
            source_comic = config["info"]["source_comic"]
            self._source_comic_by_ini[ini_filename] = source_comic
        return source_comic

    # "$HOME/Books/Carl Barks/Fantagraphics/Carl Barks Vol. 2 - Donald Duck - Frozen Gold"
    #     root_dir      = "$HOME/Books/Carl Barks/Fantagraphics"
    #     fanta dirname = "Fantagraphics"
    #     title         = "Carl Barks Vol. 2 - Donald Duck - Frozen Gold"
    @staticmethod
    def get_fantagraphics_volume_title(volume_num: int) -> str:
        """Return a volume's title, which is also the name of its directories."""
        return get_fanta_title_for_volume(volume_num)

    @staticmethod
    def get_num_pages_in_fantagraphics_volume(volume_num: int) -> int:
        """Return how many scan pages a volume has."""
        return FANTA_SOURCE_COMICS[get_fanta_volume_str(volume_num)].num_pages

    def _get_comic_book_dirs(self, fanta_book: FantaBook) -> ComicBookDirs:
        return ComicBookDirs(
            srce_dir=self.get_fantagraphics_volume_dir(fanta_book.volume),
            srce_upscayled_dir=self.get_fantagraphics_upscayled_volume_dir(fanta_book.volume),
            srce_restored_dir=self.get_fantagraphics_restored_volume_dir(fanta_book.volume),
            srce_restored_upscayled_dir=self.get_fantagraphics_restored_upscayled_volume_dir(
                fanta_book.volume,
            ),
            srce_restored_svg_dir=self.get_fantagraphics_restored_svg_volume_dir(fanta_book.volume),
            srce_restored_ocr_raw_dir=self.get_fantagraphics_restored_ocr_raw_volume_dir(
                fanta_book.volume
            ),
            srce_restored_ocr_prelim_dir=self.get_fantagraphics_restored_ocr_prelim_volume_dir(
                fanta_book.volume
            ),
            srce_restored_ocr_annotations_dir=self.get_fantagraphics_restored_ocr_annotations_volume_dir(
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
        """Return a directory of the Barks root, by name."""
        return BARKS_ROOT_DIR / fanta_subdir

    def _fanta_volume_dir(self, dirname: str, volume_num: int, subdir: str | None = None) -> Path:
        root = self.get_root_dir(dirname)
        if subdir is not None:
            root /= subdir
        return root / self.get_fantagraphics_volume_title(volume_num)

    def get_fantagraphics_original_root_dir(self) -> Path:
        """Return the directory holding every volume's original scans."""
        return self.get_root_dir(self.get_fantagraphics_dirname())

    @staticmethod
    def get_fantagraphics_dirname() -> str:
        """Return the name of the directory holding every volume's original scans."""
        return FANTAGRAPHICS_DIRNAME

    def get_fantagraphics_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of original scans."""
        return self._fanta_volume_dir(FANTAGRAPHICS_DIRNAME, volume_num)

    def get_fantagraphics_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's original scans."""
        return self.get_fantagraphics_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_upscayled_root_dir(self) -> Path:
        """Return the directory holding every volume's upscayled pages."""
        return self.get_root_dir(self.get_fantagraphics_upscayled_dirname())

    @staticmethod
    def get_fantagraphics_upscayled_dirname() -> str:
        """Return the name of the directory holding every volume's upscayled pages."""
        return FANTAGRAPHICS_UPSCAYLED_DIRNAME

    def get_fantagraphics_upscayled_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of upscayled pages."""
        return self._fanta_volume_dir(FANTAGRAPHICS_UPSCAYLED_DIRNAME, volume_num)

    def get_fantagraphics_upscayled_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's upscayled pages."""
        return self.get_fantagraphics_upscayled_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_root_dir(self) -> Path:
        """Return the directory holding every volume's restored pages."""
        return self.get_root_dir(self.get_fantagraphics_restored_dirname())

    @staticmethod
    def get_fantagraphics_restored_dirname() -> str:
        """Return the name of the directory holding every volume's restored pages."""
        return FANTAGRAPHICS_RESTORED_DIRNAME

    def get_fantagraphics_restored_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of restored pages."""
        return self._fanta_volume_dir(FANTAGRAPHICS_RESTORED_DIRNAME, volume_num)

    def get_fantagraphics_restored_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's restored pages."""
        return self.get_fantagraphics_restored_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_upscayled_root_dir(self) -> Path:
        """Return the directory holding every volume's restored, upscayled pages."""
        return self.get_root_dir(self.get_fantagraphics_restored_upscayled_dirname())

    @staticmethod
    def get_fantagraphics_restored_upscayled_dirname() -> str:
        """Return the name of the directory holding every volume's restored, upscayled pages."""
        return FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME

    def get_fantagraphics_restored_upscayled_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of restored, upscayled pages."""
        return self._fanta_volume_dir(FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME, volume_num)

    def get_fantagraphics_restored_upscayled_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's restored, upscayled pages."""
        return self.get_fantagraphics_restored_upscayled_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_svg_root_dir(self) -> Path:
        """Return the directory holding every volume's restored pages as SVG."""
        return self.get_root_dir(self.get_fantagraphics_restored_svg_dirname())

    @staticmethod
    def get_fantagraphics_restored_svg_dirname() -> str:
        """Return the name of the directory holding every volume's restored pages as SVG."""
        return FANTAGRAPHICS_RESTORED_SVG_DIRNAME

    def get_fantagraphics_restored_svg_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of restored pages as SVG."""
        return self._fanta_volume_dir(FANTAGRAPHICS_RESTORED_SVG_DIRNAME, volume_num)

    def get_fantagraphics_restored_svg_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's restored pages as SVG."""
        return self.get_fantagraphics_restored_svg_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_restored_ocr_root_dir(self) -> Path:
        """Return the directory holding every volume's OCR."""
        return self.get_root_dir(self.get_fantagraphics_restored_ocr_dirname())

    @staticmethod
    def get_fantagraphics_restored_ocr_dirname() -> str:
        """Return the name of the directory holding every volume's OCR."""
        return FANTAGRAPHICS_RESTORED_OCR_DIRNAME

    def get_fantagraphics_restored_ocr_raw_root_dir(self) -> Path:
        """Return the directory holding every volume's raw OCR."""
        return self.get_fantagraphics_restored_ocr_root_dir() / "Raw"

    def get_fantagraphics_restored_ocr_raw_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of raw OCR."""
        return self._fanta_volume_dir(FANTAGRAPHICS_RESTORED_OCR_DIRNAME, volume_num, "Raw")

    def get_fantagraphics_restored_ocr_prelim_root_dir(self) -> Path:
        """Return the directory holding every volume's preliminary OCR.

        The ``BARKS_OCR_PRELIM_DIR`` environment variable, when set, names it instead.
        """
        return get_fanta_restored_ocr_prelim_root_dir(
            self.get_fantagraphics_restored_ocr_root_dir()
        )

    def get_fantagraphics_restored_ocr_prelim_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of preliminary OCR."""
        return get_fanta_restored_ocr_prelim_volume_dir(
            self.get_fantagraphics_restored_ocr_root_dir(), volume_num
        )

    def get_fantagraphics_restored_ocr_annotations_root_dir(self) -> Path:
        """Return the directory holding every volume's annotated OCR images."""
        return self.get_fantagraphics_restored_ocr_root_dir() / "Annotations"

    def get_fantagraphics_restored_ocr_annotations_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of annotated OCR images."""
        return self._fanta_volume_dir(FANTAGRAPHICS_RESTORED_OCR_DIRNAME, volume_num, "Annotations")

    def get_fantagraphics_panel_segments_root_dir(self) -> Path:
        """Return the directory holding every volume's panel segments."""
        return self.get_root_dir(self.get_fantagraphics_panel_segments_dirname())

    @staticmethod
    def get_fantagraphics_panel_segments_dirname() -> str:
        """Return the name of the directory holding every volume's panel segments."""
        return FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME

    def get_fantagraphics_panel_segments_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of panel segments."""
        return self._fanta_volume_dir(FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME, volume_num)

    def get_fantagraphics_fixes_root_dir(self) -> Path:
        """Return the directory holding every volume's fixes to its original scans."""
        return self.get_root_dir(self.get_fantagraphics_fixes_dirname())

    @staticmethod
    def get_fantagraphics_fixes_dirname() -> str:
        """Return the name of the directory holding every volume's fixes to its original scans."""
        return FANTAGRAPHICS_FIXES_DIRNAME

    def get_fantagraphics_fixes_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of fixes to its original scans."""
        return self._fanta_volume_dir(FANTAGRAPHICS_FIXES_DIRNAME, volume_num)

    def get_fantagraphics_fixes_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's fixes to its original scans."""
        return self.get_fantagraphics_fixes_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_upscayled_fixes_root_dir(self) -> Path:
        """Return the directory holding every volume's fixes to its upscayled pages."""
        return self.get_root_dir(self.get_fantagraphics_upscayled_fixes_dirname())

    @staticmethod
    def get_fantagraphics_upscayled_fixes_dirname() -> str:
        """Return the name of the directory holding every volume's fixes to its upscayled pages."""
        return FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME

    def get_fantagraphics_upscayled_fixes_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of fixes to its upscayled pages."""
        return self._fanta_volume_dir(FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME, volume_num)

    def get_fantagraphics_upscayled_fixes_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's fixes to its upscayled pages."""
        return self.get_fantagraphics_upscayled_fixes_volume_dir(volume_num) / IMAGES_SUBDIR

    def get_fantagraphics_fixes_scraps_root_dir(self) -> Path:
        """Return the directory holding every volume's fixes scraps."""
        return self.get_root_dir(self.get_fantagraphics_fixes_scraps_dirname())

    @staticmethod
    def get_fantagraphics_fixes_scraps_dirname() -> str:
        """Return the name of the directory holding every volume's fixes scraps."""
        return FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME

    def get_fantagraphics_fixes_scraps_volume_dir(self, volume_num: int) -> Path:
        """Return a volume's directory of fixes scraps."""
        return self._fanta_volume_dir(FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME, volume_num)

    def get_fantagraphics_fixes_scraps_volume_image_dir(self, volume_num: int) -> Path:
        """Return the images directory of a volume's fixes scraps."""
        return self.get_fantagraphics_fixes_scraps_volume_dir(volume_num) / IMAGES_SUBDIR

    def make_all_fantagraphics_directories(self) -> None:
        """Create all required Fantagraphics volume directories and verify symlinks."""
        make_all_fantagraphics_directories(self)

    def get_fanta_comic_book_info(self, title: str) -> FantaComicBookInfo:
        """Return the Fantagraphics info of a title, configured or not.

        Args:
            title: A story title, or an issue holding one story ("FC 9").

        Returns:
            The title's info.

        Raises:
            RuntimeError: If ``title`` is an issue holding several stories, or is close
                to an issue's name without being one.
            TitleNotFoundError: If ``title`` is not a known title.

        """
        # A title as it stands is looked up first: only a miss is worth the issue lookup's
        # search for a near name.
        title_enum = STR_TITLE_TO_ENUM.get(title)
        if title_enum is None:
            title_enum = STR_TITLE_TO_ENUM.get(self._get_story_title_of_issue(title))
        if title_enum is None:
            # Every title, not only the configured ones `is_story_title` knows.
            close_titles = difflib.get_close_matches(title, STR_TITLE_TO_ENUM, 1, 0.3)
            if close_titles:
                msg = f'Could not find title "{title}". Did you mean "{close_titles[0]}"?'
                raise TitleNotFoundError(msg, title)
            msg = f'Could not find title "{title}".'
            raise TitleNotFoundError(msg, title)

        return self._all_comic_book_info[title_enum]

    def _get_story_title_of_issue(self, title: str) -> str:
        """Return the one story of the issue ``title`` names, or "" if it names no issue.

        Raises:
            RuntimeError: If the issue holds several stories, or ``title`` is close to an
                issue's name without being one.

        """
        found, titles, close = self.get_story_title_from_issue(title)
        if found:
            if len(titles) > 1:
                titles_str = ", ".join([f'"{t}"' for t in titles])
                msg = f"You cannot use an issue title that has multiple titles: {titles_str}."
                raise RuntimeError(msg)
            return titles[0]
        if close:
            msg = f'Could not find issue title "{title}". Did you mean "{close}"?'
            raise RuntimeError(msg)
        return ""

    def get_comic_book(self, title: str, intro_inset_file: PanelPath | None = None) -> ComicBook:
        """Return the comic book of a configured story.

        Args:
            title: A story title, or an issue holding one story ("FC 9").
            intro_inset_file: The inset for the title page, if not the story's own.

        Returns:
            The comic book, read from the story's ini file.

        Raises:
            RuntimeError: If ``title`` is an issue holding several stories, or is close
                to an issue's name without being one.
            TitleNotFoundError: If ``title`` is not a configured story.

        """
        story_title = title if title in self._story_titles else ""
        if not story_title:
            story_title = self._get_story_title_of_issue(title)

        if not story_title:
            _found, close = self.is_story_title(title)
            if close:
                msg = f'Could not find title "{title}". Did you mean "{close}"?'
                raise TitleNotFoundError(msg, title)
            msg = f'Could not find title "{title}".'
            raise TitleNotFoundError(msg, title)

        ini_file = self._story_titles_dir / get_filename_from_title_str(story_title, ".ini")

        if not intro_inset_file:
            intro_inset_file = self._get_inset_file(ini_file)
        assert intro_inset_file is not None

        fanta_info: FantaComicBookInfo = self.get_fanta_comic_book_info(story_title)

        fanta_book = FANTA_SOURCE_COMICS[self._get_source_comic(ini_file.name)]
        comic_book_dirs = self._get_comic_book_dirs(fanta_book)

        return _build_comic_book(
            story_title=story_title,
            ini_file=ini_file,
            fanta_info=fanta_info,
            fanta_book=fanta_book,
            intro_inset_file=intro_inset_file,
            comic_book_dirs=comic_book_dirs,
            for_building_comics=self._for_building_comics,
        )

    def get_comic_book_for(
        self, title: Titles, intro_inset_file: PanelPath | None = None
    ) -> ComicBook:
        """Return the comic book for a title enum.

        Convenience wrapper for callers that already hold a ``Titles`` enum, avoiding a
        redundant enum-to-string conversion at the call site.

        Args:
            title: The title enum member.
            intro_inset_file: Optional override for the intro inset image.

        Returns:
            The ``ComicBook`` for the given title.

        """
        return self.get_comic_book(ENUM_TO_STR_TITLE[title], intro_inset_file)

    @staticmethod
    def check_comic_ok_for_building(comic: ComicBook) -> None:
        """Verify that all required source directories for building a comic exist."""
        check_comic_ok_for_building(comic)

    # TODO: Make type PanelPath
    def _get_inset_file(self, ini_file: Path) -> Path:
        assert self._inset_dir
        assert self._inset_ext

        title = ini_file.stem
        inset_filename = title + self._inset_ext

        return self._inset_dir / inset_filename


def _get_title_color(value: str, ini_file: Path) -> tuple[int, int, int]:
    """Return the title colour an ini's ``title_color`` names, such as ``green``.

    Args:
        value: The ``title_color`` value, or "" when the ini has none.
        ini_file: The ini it came from, named if the value is bad.

    Returns:
        The colour, or the default title colour when there is no value.

    Raises:
        ValueError: If the value is not one of the ``TITLE_COLORS`` names.

    """
    if not value:
        return INTRO_TITLE_DEFAULT_COLOR

    color = TITLE_COLORS.get(value.strip().lower())
    if color is None:
        msg = (
            f'Title color "{value}" in "{get_relpath(ini_file)}" is not one of:'
            f" {', '.join(TITLE_COLORS)}."
        )
        raise ValueError(msg)

    return color


def _get_byline(value: str, ini_file: Path) -> str:
    """Return the byline an ini's ``byline`` names, such as ``art by``.

    Args:
        value: The ``byline`` value, or "" when the ini has none.
        ini_file: The ini it came from, named if the value is bad.

    Returns:
        The byline, or the default byline when there is no value.

    Raises:
        ValueError: If the value is not one of the ``BYLINES``.

    """
    if not value:
        return INTRO_DEFAULT_BYLINE

    byline = " ".join(value.lower().split())
    if byline not in BYLINES:
        msg = f'Byline "{value}" in "{get_relpath(ini_file)}" is not one of: {", ".join(BYLINES)}.'
        raise ValueError(msg)

    return byline


def _build_comic_book(
    story_title: str,
    ini_file: Path,
    fanta_info: FantaComicBookInfo,
    fanta_book: FantaBook,
    intro_inset_file: PanelPath,
    comic_book_dirs: ComicBookDirs,
    for_building_comics: bool,
) -> ComicBook:
    logger.debug(f'Getting comic book info from config file "{get_relpath(ini_file)}".')

    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read(ini_file, encoding="utf-8")

    issue_title = config["info"].get("issue_title", "")

    title = config["info"]["title"]
    if not title and fanta_info.comic_book_info.is_barks_title:
        msg = f'"{story_title}" is a barks title and should be set in the ini file.'
        raise RuntimeError(msg)
    if title and not fanta_info.comic_book_info.is_barks_title:
        msg = f'"{story_title}" is a not barks title and should not be set in the ini file.'
        raise RuntimeError(msg)

    srce_dir_num_page_files = fanta_book.num_pages

    publication_date = get_formatted_first_published_str(fanta_info.comic_book_info)
    submitted_date = get_formatted_submitted_date(fanta_info.comic_book_info)

    publication_text = get_main_publication_info(story_title, fanta_info, fanta_book)
    extra_pub_info = config["info"].get("extra_pub_info", "")

    if is_one_pager_collection(fanta_info.comic_book_info.title):
        # The "All One-Pagers" collection's pages are not listed in the ini. They are
        # pre-baked into this (nominal FANTA_01) volume's override + segments offline;
        # ONE_PAGER_LOCATIONS drives the page list (see get_one_pager_collection_pages).
        config_page_images = get_one_pager_collection_pages()
    elif is_covers_collection(fanta_info.comic_book_info.title):
        # Same scheme for the "All Covers" collection, pre-baked into the nominal
        # FANTA_02 volume's override; COVER_LOCATIONS drives the page list.
        config_page_images = get_cover_collection_pages()
    else:
        config_page_images = [
            OriginalPage(key, PageType[config["pages"][key]])
            for key in config["pages"]
            if key != "solo_pages"
        ]

    solo_pages_str = config["pages"].get("solo_pages", "")
    solo_page_keys: frozenset[str] = (
        frozenset(f"{int(k.strip()):03d}" for k in solo_pages_str.split(",") if k.strip())
        if solo_pages_str
        else frozenset()
    )

    comic = ComicBook(
        ini_file=ini_file,
        title=title,
        title_font_file=INTRO_TITLE_DEFAULT_FONT_FILE,
        title_font_size=config["info"].getint("title_font_size", INTRO_TITLE_DEFAULT_FONT_SIZE),
        title_color=_get_title_color(config["info"].get("title_color", ""), ini_file),
        byline=_get_byline(config["info"].get("byline", ""), ini_file),
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
        extra_pub_info=extra_pub_info,
        fanta_book=fanta_book,
        fanta_info=fanta_info,
        solo_page_keys=solo_page_keys,
    )

    if for_building_comics:
        check_comic_ok_for_building(comic)

    return comic


def make_all_fantagraphics_directories(db: "ComicsDatabase") -> None:
    """Create all required Fantagraphics volume directories and verify symlinks.

    Args:
        db: The ComicsDatabase instance providing volume directory paths.

    """
    FANTA_VOLUME_OVERRIDES_ROOT.mkdir(parents=True, exist_ok=True)

    for volume in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1):
        # A volume with no original scans has nothing to derive from, so making its
        # derived dirs anyway would dress a misspelled VOLUME_nn up as a real volume:
        # eleven plausible empty dirs appear, the directory-structure check passes, and
        # every source lookup silently misses because the originals are under the name
        # that was actually meant. Skip the volume and say so instead.
        original_dir = db.get_fantagraphics_volume_dir(volume)
        if not original_dir.is_dir():
            logger.error(
                f"No Fantagraphics original dir for volume {volume} - not making its"
                f' directories: "{original_dir}". Check the volume\'s VOLUME_nn constant'
                f" names its actual directory on disk."
            )
            continue

        # Create these directories if they're already not there.
        _make_vol_dir(db.get_fantagraphics_upscayled_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_restored_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_restored_upscayled_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_restored_svg_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_restored_ocr_raw_volume_dir(volume))
        _make_vol_dir(db.get_fantagraphics_fixes_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_upscayled_fixes_volume_image_dir(volume))
        _make_vol_dir(db.get_fantagraphics_panel_segments_volume_dir(volume))

        scraps_image_dir = db.get_fantagraphics_fixes_scraps_volume_image_dir(volume)
        _make_vol_dir(scraps_image_dir / "standard")
        _make_vol_dir(scraps_image_dir / "upscayled")
        _make_vol_dir(scraps_image_dir / "restored")

    # Symlinks - just make sure these exist.
    _check_symlink_exists(db.get_fantagraphics_upscayled_root_dir())
    _check_symlink_exists(db.get_fantagraphics_restored_upscayled_root_dir())
    _check_symlink_exists(db.get_fantagraphics_restored_svg_root_dir())


def _make_vol_dir(vol_dirname: Path) -> None:
    if vol_dirname.is_dir():
        logger.debug(f'Dir already exists - nothing to do: "{vol_dirname}".')
    else:
        vol_dirname.mkdir(parents=True, exist_ok=True)
        logger.info(f'Created dir "{vol_dirname}".')


def _check_symlink_exists(symlink: Path) -> None:
    if not symlink.is_symlink():
        logger.error(f'Symlink not found: "{symlink}".')
    else:
        logger.debug(f'Symlink exists - all good: "{symlink}".')


def check_comic_ok_for_building(comic: ComicBook) -> None:
    """Verify that all required source directories for building a comic exist.

    Args:
        comic: The ComicBook whose directories are checked.

    Raises:
        FileNotFoundError: If any required directory is missing.

    """
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
            f'Could not find srce restored image directory "{comic.get_srce_restored_image_dir()}".'
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


def _get_story_titles_dir(db_dir: Path) -> Path:
    story_titles_dir = db_dir / STORY_TITLES_DIR

    if not story_titles_dir.is_dir():
        msg = f'Could not find story titles directory "{story_titles_dir}".'
        raise FileNotFoundError(msg)

    return story_titles_dir


def get_fanta_restored_ocr_prelim_volume_dir(
    fanta_restored_ocr_root_dir: Path, volume_num: int
) -> Path:
    """Return a volume's directory of preliminary OCR.

    Args:
        fanta_restored_ocr_root_dir: The directory holding every volume's OCR.
        volume_num: The Fantagraphics volume.

    Returns:
        The volume's directory under the preliminary OCR root.

    """
    title = get_fanta_title_for_volume(volume_num)
    return get_fanta_restored_ocr_prelim_root_dir(fanta_restored_ocr_root_dir) / title


def get_fanta_restored_ocr_prelim_root_dir(fanta_restored_ocr_root_dir: Path) -> Path:
    """Return the directory holding every volume's preliminary OCR.

    Args:
        fanta_restored_ocr_root_dir: The directory holding every volume's OCR.

    Returns:
        The ``BARKS_OCR_PRELIM_DIR`` environment variable's directory when it is set,
        else "Prelim" under ``fanta_restored_ocr_root_dir``.

    Raises:
        NotADirectoryError: If the variable is set but does not name a directory.

    """
    # Defer to the one lookup that knows about the BARKS_OCR_PRELIM_DIR override, so
    # this and ocr_file_paths.OCR_PRELIM_DIR can never name different trees. Not cached,
    # here or in the volume lookup above: the override is read from the environment.
    return get_ocr_prelim_dir(fanta_restored_ocr_root_dir)


@functools.cache
def get_fanta_title_for_volume(volume_num: int) -> str:
    """Return a volume's title, which is also the name of its directories."""
    return FANTA_SOURCE_COMICS[get_fanta_volume_str(volume_num)].title
