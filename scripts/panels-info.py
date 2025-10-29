# ruff: noqa: T201

import sys
from configparser import ConfigParser
from pathlib import Path

from barks_fantagraphics.comic_book import get_abbrev_jpg_page_list
from barks_fantagraphics.comics_cmd_args import CmdArgNames, CmdArgs
from barks_reader.config_info import ConfigInfo  # make sure this is before any kivy imports
from barks_reader.image_file_getter import TitleImageFileGetter
from barks_reader.reader_file_paths import FileTypes
from barks_reader.reader_settings import ReaderSettings
from loguru import logger
from loguru_config import LoguruConfig

APP_LOGGING_NAME = "ipan"

SHORT_FILE_TYPE_NAMES = {
    FileTypes.BLACK_AND_WHITE: "bw",
    FileTypes.AI: "ai",
    FileTypes.CENSORSHIP: "ce",
    FileTypes.CLOSEUP: "cl",
    FileTypes.COVER: "co",
    FileTypes.FAVOURITE: "f",
    FileTypes.INSET: "i",
    FileTypes.NONTITLE: "nt",
    FileTypes.ORIGINAL_ART: "oa",
    FileTypes.SILHOUETTE: "si",
    FileTypes.SPLASH: "sp",
}
RELEVANT_FILE_TYPES = [ft for ft in FileTypes if ft != FileTypes.NONTITLE]


if __name__ == "__main__":
    # TODO(glk): Some issue with type checking inspection?
    # noinspection PyTypeChecker
    cmd_args = CmdArgs("Reader Panels Info", CmdArgNames.TITLE | CmdArgNames.VOLUME)
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        logger.error(error_msg)
        sys.exit(1)

    # Global variable accessed by loguru-config.
    log_level = cmd_args.get_log_level()
    LoguruConfig.load(Path(__file__).parent / "log-config.yaml")

    # noinspection PyBroadException
    try:
        config_info = ConfigInfo()
        print(f'Getting config from "{config_info.app_config_path}".')
        config = ConfigParser()
        config.read(config_info.app_config_path)
        reader_settings = ReaderSettings()
        # noinspection PyTypeChecker
        reader_settings.set_config(config, config_info.app_config_path, config_info.app_data_dir)  # ty: ignore[invalid-argument-type]
        reader_settings.force_barks_panels_dir(use_png_images=True)

        comic_database = cmd_args.get_comics_database(for_building_comics=False)
        titles = cmd_args.get_titles()

        image_getter = TitleImageFileGetter(reader_settings)
        image_dict: dict[str, tuple[dict[FileTypes, set[tuple[Path, bool]]], str]] = {}
        max_title_len = 0
        for title in titles:
            max_title_len = max(max_title_len, len(title))

            comic_book = comic_database.get_comic_book(title)
            page_lst = ", ".join(get_abbrev_jpg_page_list(comic_book)).replace(" - ", "-")

            image_dict[title] = (image_getter.get_all_title_image_files(title), page_lst)

        print()

        for title, (file_dict, page_lst) in image_dict.items():
            title_str = title + ":"

            nums = [
                (
                    f"{SHORT_FILE_TYPE_NAMES[ft]}:"
                    f" {len(file_dict.get(ft, [])):{2 if ft == FileTypes.AI else 1}d}"
                )
                for ft in RELEVANT_FILE_TYPES
            ]
            total = sum(len(file_dict.get(ft, [])) for ft in RELEVANT_FILE_TYPES)

            print(f"{title_str:<{max_title_len + 1}} {total:2d}= {', '.join(nums)}; {page_lst}")

    except Exception:  # noqa: BLE001
        logger.exception("Program error: ")
