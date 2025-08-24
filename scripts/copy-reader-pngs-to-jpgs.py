# ruff: noqa: INP001

import shutil
import sys
from collections.abc import Callable
from configparser import ConfigParser
from pathlib import Path

from barks_fantagraphics.comics_cmd_args import CmdArgNames, CmdArgs
from barks_fantagraphics.comics_consts import PNG_FILE_EXT
from barks_fantagraphics.comics_utils import get_abbrev_path
from comic_utils.comic_consts import JPG_FILE_EXT
from comic_utils.comics_logging import setup_logging
from comic_utils.pil_image_utils import SAVE_JPG_COMPRESS_LEVEL, open_pil_image_for_reading
from loguru import logger

from barks_reader.config_info import ConfigInfo  # make sure this is before any kivy imports
from barks_reader.reader_settings import ReaderSettings


def copy_or_convert_file(file_path: Path, dest_dir: Path) -> None:
    if not file_path.is_file():
        msg = f'Could not find source file "{file_path}".'
        raise FileNotFoundError(msg)

    # noinspection PyBroadException
    try:
        if file_path.suffix == PNG_FILE_EXT:
            dest_file = dest_dir / (file_path.stem + JPG_FILE_EXT)
            logger.info(
                f'Converting png file "{get_abbrev_path(file_path)}"'
                f' to "{get_abbrev_path(dest_file)}"...'
            )
            copy_file_to_jpg(file_path, dest_file)
        else:
            dest_file = dest_dir / file_path.name
            logger.info(
                f'Copying file "{get_abbrev_path(file_path)}" to "{get_abbrev_path(dest_file)}"...'
            )
            shutil.copy(file_path, dest_file)

    except FileNotFoundError:
        logger.exception(f'File not found during processing: "{file_path}": ')
    except Exception:
        logger.exception(f'An error occurred while processing "{file_path}": ')


def copy_file_to_jpg(srce_file: Path, dest_file: Path) -> None:
    image = open_pil_image_for_reading(str(srce_file)).convert("RGB")

    image.save(
        dest_file,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=92,
    )


def traverse_and_process_dirs(
    root_directory: Path, dest_dir: Path, file_processor_func: Callable[[Path, Path], None]
) -> None:
    """Traverses a directory tree and runs a processor function on each file.

    Args:
        root_directory (Path): The path to the top-level directory to start from.
        dest_dir (Path): The path to the destination directory.
        file_processor_func (callable): The function to call for each file.
                                        It should accept one argument: the full file path.

    """
    if not root_directory.is_dir():
        logger.error(f"The specified root directory does not exist: {root_directory}")
        return

    logger.info(f'Starting traversal of directory: "{root_directory}".')
    file_count = 0
    for dirpath, _, filenames in root_directory.walk():
        logger.info(f'Processing directory "{dirpath}"...')
        dest_subdir = Path(str(dirpath).replace(str(root_directory), str(dest_dir)))
        logger.info(f'Creating dest subdir "{dest_subdir}"...')
        dest_subdir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            # Construct the full file path
            full_path = dirpath / filename
            # Run the provided function on the file
            file_processor_func(full_path, dest_subdir)
            file_count += 1

    logger.info(f"Traversal complete. Processed {file_count} files.")


if __name__ == "__main__":
    # TODO(glk): Some issue with type checking inspection?
    # noinspection PyTypeChecker
    cmd_args = CmdArgs("Fantagraphics source files", CmdArgNames.TITLE | CmdArgNames.VOLUME)
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        logger.error(error_msg)
        sys.exit(1)

    # noinspection PyBroadException
    try:
        config_info = ConfigInfo()
        config = ConfigParser()
        config.read(config_info.app_config_path)
        reader_settings = ReaderSettings()
        reader_settings.set_config(config, config_info.app_config_path)
        reader_settings.set_barks_panels_dir()

        setup_logging(cmd_args.get_log_level())

        png_dir = reader_settings.file_paths.get_default_png_barks_panels_dir()
        jpg_dir = reader_settings.file_paths.get_default_jpg_barks_panels_dir()

        traverse_and_process_dirs(png_dir, jpg_dir, file_processor_func=copy_or_convert_file)

    except Exception:
        logger.exception("Program error: ")
