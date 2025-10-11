# ruff: noqa: T201

"""A utility script to check the correctness of contents of the PNG Barks Panels source."""

import sys
from pathlib import Path

from barks_fantagraphics.barks_titles import (
    BARKS_TITLE_DICT,
    FILENAME_TO_TITLE_SPECIAL_CASE_MAP,
)
from barks_reader.reader_consts_and_types import NO_OVERRIDES_SUFFIX
from barks_reader.reader_file_paths import EDITED_SUBDIR, PanelDirNames, ReaderFilePaths
from barks_reader.reader_utils import get_paths_from_directory
from loguru import logger


def check_file_paths_are_titles(path_set: set[str]) -> None:
    print("\n" + "=" * 50)
    print("PANEL TITLE CHECK REPORT")
    print("=" * 50)

    num_errors = 0
    for path_str in path_set:
        path = Path(path_str)

        if (path.parts[-2] == EDITED_SUBDIR) or (path.parts[0] == PanelDirNames.NONTITLES.value):
            continue

        title = (
            path.parts[-1]
            if path.parts[0] in [PanelDirNames.COVERS.value, PanelDirNames.INSETS.value]
            else path.parts[-2]
        )

        title = title.removesuffix(NO_OVERRIDES_SUFFIX)
        if title in FILENAME_TO_TITLE_SPECIAL_CASE_MAP:
            title = FILENAME_TO_TITLE_SPECIAL_CASE_MAP[title]

        if title not in BARKS_TITLE_DICT:
            print(f'"{path}" is not a title.')
            num_errors += 1

    if num_errors == 0:
        print("\nNo errors found.")
    else:
        print(f"\nThere were {num_errors} title errors.")

    print("\n" + "=" * 50)


def main() -> None:
    """Run the check."""
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    file_paths = ReaderFilePaths()

    png_source_path = file_paths.get_default_png_barks_panels_source()
    if not png_source_path.is_dir():
        logger.error(f"PNG source directory not found: {png_source_path}.")
        return

    logger.info(f"Scanning PNG directory source: {png_source_path}...")
    png_paths = get_paths_from_directory(png_source_path)
    assert png_paths
    logger.success(f"Found {len(png_paths)} file paths in PNG directory.")

    logger.info("Checking PNG file set...")
    check_file_paths_are_titles(png_paths)


if __name__ == "__main__":
    main()
