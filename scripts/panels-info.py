# ruff: noqa: T201, INP001

import logging
import sys
from configparser import ConfigParser
from pathlib import Path

from barks_fantagraphics.comics_cmd_args import CmdArgNames, CmdArgs
from barks_fantagraphics.comics_logging import setup_logging

from barks_reader.config_info import ConfigInfo  # make sure this is before any kivy imports
from barks_reader.image_file_getter import FileTypes, TitleImageFileGetter
from barks_reader.reader_settings import ReaderSettings

SHORT_FILE_TYPE_NAMES = {
    FileTypes.BLACK_AND_WHITE: "bw",
    FileTypes.CENSORSHIP: "ce",
    FileTypes.COVER: "co",
    FileTypes.FAVOURITE: "fa",
    FileTypes.INSET: "in",
    FileTypes.NONTITLE: "nt",
    FileTypes.ORIGINAL_ART: "oa",
    FileTypes.SILHOUETTE: "si",
    FileTypes.SPLASH: "sp",
}
RELEVANT_FILE_TYPES = [ft for ft in FileTypes if ft != FileTypes.NONTITLE]


# TODO(glk): Some issue with type checking inspection?
# noinspection PyTypeChecker
cmd_args = CmdArgs("Fantagraphics source files", CmdArgNames.TITLE | CmdArgNames.VOLUME)
args_ok, error_msg = cmd_args.args_are_valid()
if not args_ok:
    logging.error(error_msg)
    sys.exit(1)

# noinspection PyBroadException
try:
    config_info = ConfigInfo()
    print(f'Getting config from "{config_info.app_config_path}".')
    config = ConfigParser()
    config.read(config_info.app_config_path)
    reader_settings = ReaderSettings()
    reader_settings.set_config(config, config_info.app_config_path)
    reader_settings.set_barks_panels_dir()

    setup_logging(cmd_args.get_log_level())

    titles = cmd_args.get_titles()

    image_getter = TitleImageFileGetter(reader_settings)
    image_dict: dict[str, dict[FileTypes, set[tuple[Path, bool]]]] = {}
    max_title_len = 0
    for title in titles:
        max_title_len = max(max_title_len, len(title))
        image_dict[title] = image_getter.get_all_title_image_files(title)

    print()

    for title, file_dict in image_dict.items():
        title_str = title + ":"

        nums = [
            f"{SHORT_FILE_TYPE_NAMES[ft]}: {len(file_dict.get(ft, [])):2d}"
            for ft in RELEVANT_FILE_TYPES
        ]

        print(f"{title_str:<{max_title_len + 1}} {', '.join(nums)}")

except Exception:
    logging.exception("Program error: ")
