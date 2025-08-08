import logging  # noqa: INP001
import shutil
from collections.abc import Callable
from pathlib import Path

from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PNG_FILE_EXT
from barks_fantagraphics.pil_image_utils import SAVE_JPG_COMPRESS_LEVEL, open_pil_image_for_reading

# Setup basic logging to see the output and any potential errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def copy_or_convert_file(file_path: Path, dest_dir: Path) -> None:
    # noinspection PyBroadException
    try:
        if file_path.suffix == PNG_FILE_EXT:
            dest_file = dest_dir / (file_path.stem + JPG_FILE_EXT)
            logging.info(f'Converting png file "{file_path}" to "{dest_file}"...')
            copy_file_to_jpg(file_path, dest_file)
        else:
            dest_file = dest_dir / file_path.name
            logging.info(f'Copying file "{file_path}" to "{dest_file}"...')
            shutil.copy(file_path, dest_file)

    except FileNotFoundError:
        logging.exception(f'File not found during processing: "{file_path}": ')
    except Exception:
        logging.exception(f'An error occurred while processing "{file_path}": ')


def copy_file_to_jpg(srce_file: Path, dest_file: Path) -> None:
    image = open_pil_image_for_reading(str(srce_file)).convert("RGB")

    image.save(
        dest_file,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=92,
    )


def traverse_and_process(
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
        logging.error(f"The specified root directory does not exist: {root_directory}")
        return

    logging.info(f'Starting traversal of directory: "{root_directory}".')
    file_count = 0
    for dirpath, _, filenames in root_directory.walk():
        logging.info(f'Processing directory "{dirpath}"...')
        dest_subdir = Path(str(dirpath).replace(str(root_directory), str(dest_dir)))
        logging.info(f'Creating dest subdir "{dest_subdir}"...')
        dest_subdir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            # Construct the full file path
            full_path = dirpath / filename
            # Run the provided function on the file
            file_processor_func(full_path, dest_subdir)
            file_count += 1

    logging.info(f"Traversal complete. Processed {file_count} files.")


if __name__ == "__main__":
    png_dir = Path("~/Books/Carl Barks/Barks Panels Pngs").expanduser()
    jpg_dir = Path("~/Books/Carl Barks/Compleat Barks Disney Reader/Barks Panels").expanduser()

    traverse_and_process(png_dir, jpg_dir, file_processor_func=copy_or_convert_file)
