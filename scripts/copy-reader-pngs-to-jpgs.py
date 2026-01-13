import io
import os
import zipfile
from collections.abc import Callable
from configparser import ConfigParser
from pathlib import Path

import typer
from barks_fantagraphics.comics_consts import PNG_FILE_EXT
from barks_fantagraphics.comics_utils import get_abbrev_path, get_timestamp_str
from barks_reader.config_info import ConfigInfo  # make sure this is before any kivy imports
from barks_reader.reader_settings import ReaderSettings
from comic_utils.comic_consts import JPG_FILE_EXT
from comic_utils.common_typer_options import LogLevelArg
from comic_utils.pil_image_utils import get_pil_image_as_jpg_bytes, load_pil_image_for_reading
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from loguru import logger
from loguru_config import LoguruConfig

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

APP_LOGGING_NAME = "zip"

PANEL_KEY = os.environ["BARKS_ZIPS_KEY"]
FERNET = Fernet(PANEL_KEY)


def get_backup_filename(file: Path) -> Path:
    return Path(str(file) + "_" + get_timestamp_str(file))


def convert_and_zip_file(file_path: Path, archive: zipfile.ZipFile, dest_subdir: Path) -> None:
    if not file_path.is_file():
        msg = f'Could not find source file "{file_path}".'
        raise FileNotFoundError(msg)

    # noinspection PyBroadException
    try:
        if file_path.suffix == PNG_FILE_EXT:
            dest_file = dest_subdir / (file_path.stem + JPG_FILE_EXT)
            logger.debug(
                f'Converting png file "{get_abbrev_path(file_path)}"'
                f' to "{get_abbrev_path(dest_file)}"...'
            )
            zip_file_as_jpg(file_path, archive, dest_file)
        else:
            dest_file = dest_subdir / file_path.name
            logger.debug(
                f'Writing file "{get_abbrev_path(file_path)}"'
                f' to zip: "{get_abbrev_path(dest_file)}"...'
            )
            with file_path.open("rb") as f:
                original = f.read()
            buffer = io.BytesIO(FERNET.encrypt(original))
            buffer.seek(0)
            archive.writestr(str(dest_file), buffer.read())

    except FileNotFoundError:
        msg = f'File not found during processing: "{file_path}"'
        raise FileNotFoundError(msg) from None
    except Exception as e:
        msg = f'An error occurred while processing "{file_path}": '
        raise Exception(msg) from e  # noqa: TRY002


def zip_file_as_jpg(srce_file: Path, archive: zipfile.ZipFile, dest_file: Path) -> None:
    image = load_pil_image_for_reading(srce_file).convert("RGB")

    buffer = get_pil_image_as_jpg_bytes(image)
    buffer = io.BytesIO(FERNET.encrypt(buffer.getvalue()))
    buffer.seek(0)

    archive.writestr(str(dest_file), buffer.read())


def traverse_and_process_dirs(
    root_directory: Path,
    dest_zip: Path,
    file_processor_func: Callable[[Path, zipfile.ZipFile, Path], None],
) -> None:
    if not root_directory.is_dir():
        raise FileNotFoundError(root_directory)

    logger.info(f'Copying all barks panel pngs to zip: "{dest_zip}"...')
    logger.info(f'Starting traversal of directory: "{root_directory}"...')

    with zipfile.ZipFile(
        dest_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=2
    ) as dest_zip_archive:
        file_count = 0
        for dirpath, _, filenames in root_directory.walk():
            logger.info(f'Processing directory "{dirpath}"...')
            dest_subdir = str(dirpath)[len(str(root_directory)) + 1 :]
            logger.info(f'Adding files to dest zip under subdir "{dest_subdir}"...')
            dest_subdir = Path(dest_subdir)

            for filename in filenames:
                full_path = dirpath / filename
                file_processor_func(full_path, dest_zip_archive, dest_subdir)
                file_count += 1

    logger.success(f'Traversal complete. Added {file_count} files to "{dest_zip}".')


app = typer.Typer()
log_level = ""


@app.command(help="Copy Barks png panels to jpg directory")
def main(log_level_str: LogLevelArg = "DEBUG") -> None:
    # Global variable accessed by loguru-config.
    global log_level  # noqa: PLW0603
    log_level = log_level_str
    LoguruConfig.load(Path(__file__).parent / "log-config.yaml")

    # noinspection PyBroadException
    try:
        config_info = ConfigInfo()
        config = ConfigParser()
        logger.info(f'Using config file "{config_info.app_config_path}".')
        config.read(config_info.app_config_path)
        reader_settings = ReaderSettings()
        # noinspection PyTypeChecker,LongLine
        reader_settings.set_config(config, config_info.app_config_path, config_info.app_data_dir)  # ty: ignore[invalid-argument-type]
        reader_settings.force_barks_panels_dir(use_png_images=True)

        png_dir = reader_settings.file_paths.get_default_png_barks_panels_source()
        zip_file = reader_settings.file_paths.get_default_jpg_barks_panels_source()

        if not zip_file.is_file():
            zip_backup = ""
        else:
            zip_backup = get_backup_filename(zip_file)
            zip_file.rename(zip_backup)

        traverse_and_process_dirs(png_dir, zip_file, file_processor_func=convert_and_zip_file)

        if zip_backup:
            logger.success(f'NOTE: Backed up old zip to "{zip_backup}".')

    except Exception:  # noqa: BLE001
        logger.exception("Program error: ")


if __name__ == "__main__":
    main()
