# ruff: noqa: T201

"""A utility script to compare the contents of the PNG and JPG Barks Panels sources."""

import sys

from barks_reader.core.reader_file_paths import ReaderFilePaths
from barks_reader.core.reader_utils import get_paths_from_directory, get_paths_from_zip
from loguru import logger


def main() -> None:
    """Run the comparison."""
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    file_paths = ReaderFilePaths()

    png_source_path = file_paths.get_default_png_barks_panels_source()
    if not png_source_path.is_dir():
        logger.error(f"PNG source directory not found: {png_source_path}.")
        return

    jpg_source_path = file_paths.get_default_jpg_barks_panels_source()
    if not jpg_source_path.is_file():
        logger.error(f"JPG source zip file not found: {jpg_source_path}.")
        return

    logger.info(f"Scanning PNG directory source: {png_source_path}...")
    png_paths = get_paths_from_directory(png_source_path)
    assert png_paths
    logger.success(f"Found {len(png_paths)} file paths in PNG directory.")

    logger.info(f"Scanning JPG zip source: {jpg_source_path}...")
    jpg_paths = get_paths_from_zip(jpg_source_path)
    assert jpg_paths
    logger.success(f"Found {len(jpg_paths)} file paths in JPG zip archive.")

    logger.info("Comparing file sets...")

    only_in_png = sorted(png_paths - jpg_paths)
    only_in_jpg = sorted(jpg_paths - png_paths)

    print("\n" + "=" * 50)
    print("PANEL SOURCES COMPARISON REPORT")
    print("=" * 50)

    if not only_in_png and not only_in_jpg:
        print("\nSources are in sync! No discrepancies found.")
    else:
        if not only_in_png:
            print("\n>>> No items found only in the PNG Directory Source.")
        else:
            print(f"\n>>> Found {len(only_in_png)} items ONLY in PNG Directory Source:")
            for item in only_in_png:
                print(f"  - {item}")

        if not only_in_jpg:
            print("\n>>> No items found only in the JPG Zip Source.")
        else:
            print(f"\n>>> Found {len(only_in_jpg)} items ONLY in JPG Zip Source:")
            for item in only_in_jpg:
                print(f"  - {item}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
