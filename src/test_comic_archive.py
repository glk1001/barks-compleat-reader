import logging
import os
import sys
from typing import Dict

from intspan import intspan

from barks_fantagraphics.comic_book import get_page_str
from barks_fantagraphics.comics_logging import setup_logging
from fantagraphics_volumes import FantagraphicsArchive, FantagraphicsVolumeArchives

FANTA_VOLUME_ARCHIVES_ROOT = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes"
FANTA_VOLUME_OVERRIDES_ROOT = "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes Overrides"


def print_archive_image_pages_map(archive: FantagraphicsArchive) -> None:
    first_page = get_page_str(1)
    print(f"  '{first_page}': '{archive.archive_images_page_map[first_page]}'")

    print("   ...")

    last_page = get_page_str(archive.get_num_pages())
    print(f"  '{last_page}': '{archive.archive_images_page_map[last_page]}'")


def print_page_map(page_map: Dict[str, str]) -> None:
    for page in sorted(page_map.keys()):
        print(f"  '{page}': '{page_map[page]}'")


if __name__ == "__main__":
    setup_logging(log_level=logging.DEBUG)

    assert len(sys.argv) > 1
    vol_list = list(intspan(sys.argv[1]))

    fanta_volume_archives = FantagraphicsVolumeArchives(
        FANTA_VOLUME_ARCHIVES_ROOT, FANTA_VOLUME_OVERRIDES_ROOT, vol_list
    )
    fanta_volume_archives.load()

    print()
    print(f'Archive Root: "{FANTA_VOLUME_ARCHIVES_ROOT}"')

    for fanta_vol in vol_list:
        fanta_archive = fanta_volume_archives.get_fantagraphics_archive(fanta_vol)

        assert fanta_vol == fanta_archive.fanta_volume
        print(f"Fanta Vol: {fanta_archive.fanta_volume}")
        print(f'Archive: "{os.path.basename(fanta_archive.archive_filename)}"')
        print(f'Override: "{fanta_archive.override_dir}"')
        print(f'Image dir: "{fanta_archive.archive_image_subdir}"')
        print(f'Image ext: "{fanta_archive.image_ext}"')
        print(f"Images: {fanta_archive.first_page}-{fanta_archive.last_page}")

        print("Archive page map: ")
        print_archive_image_pages_map(fanta_archive)

        print(f"Override pages map: ")
        print_page_map(fanta_archive.override_images_page_map)

        print(f"Extra pages map: ")
        print_page_map(fanta_archive.extra_images_page_map)

        print()
