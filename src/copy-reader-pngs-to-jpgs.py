import logging
import os
import shutil
from pathlib import Path
from typing import Callable

from barks_fantagraphics.comics_consts import PNG_FILE_EXT, JPG_FILE_EXT
from barks_fantagraphics.pil_image_utils import open_pil_image_for_reading, SAVE_JPG_COMPRESS_LEVEL

# Setup basic logging to see the output and any potential errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def process_file(file_path: str, dest_dir: str) -> None:
    try:
        if file_path.endswith(PNG_FILE_EXT):
            dest_file = os.path.join(dest_dir, Path(file_path).stem + JPG_FILE_EXT)
            logging.info(f'Converting png file "{file_path}" to "{dest_file}"...')
            copy_file_to_jpg(file_path, dest_file)
        else:
            dest_file = os.path.join(dest_dir, os.path.basename(file_path))
            logging.info(f'Copying file "{file_path}" to "{dest_file}"...')
            shutil.copy(file_path, dest_file)

    except FileNotFoundError:
        logging.error(f'File not found during processing: "{file_path}".')
    except Exception as e:
        logging.error(f'An error occurred while processing "{file_path}": {e}')


def copy_file_to_jpg(srce_file: str, dest_file: str) -> None:
    image = open_pil_image_for_reading(srce_file).convert("RGB")

    image.save(
        dest_file,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=92,
    )


def traverse_and_process(
    root_directory: str, dest_dir: str, file_processor_func: Callable[[str, str], None]
) -> None:
    """
    Traverses a directory tree and runs a processor function on each file.

    Args:
        root_directory (str): The path to the top-level directory to start from.
        dest_dir (str): The path to the destination directory.
        file_processor_func (callable): The function to call for each file.
                                        It should accept one argument: the full file path.
    """
    if not os.path.isdir(root_directory):
        logging.error(f"The specified root directory does not exist: {root_directory}")
        return

    logging.info(f'Starting traversal of directory: "{root_directory}".')
    file_count = 0
    for dirpath, _, filenames in os.walk(root_directory):
        logging.info(f'Processing directory "{dirpath}"...')
        dest_subdir = dirpath.replace(root_directory, dest_dir)
        logging.info(f'Creating dest subdir "{dest_subdir}"...')
        os.makedirs(dest_subdir, exist_ok=True)

        for filename in filenames:
            # Construct the full file path
            full_path = os.path.join(dirpath, filename)
            # Run the provided function on the file
            file_processor_func(full_path, dest_subdir)
            file_count += 1

    logging.info(f"Traversal complete. Processed {file_count} files.")


if __name__ == "__main__":
    png_dir = os.path.expanduser("~/Books/Carl Barks/Barks Panels Pngs")
    jpg_dir = os.path.expanduser("~/Books/Carl Barks/Compleat Barks Disney Reader/Barks Panels")

    traverse_and_process(png_dir, jpg_dir, file_processor_func=process_file)
