"""The comic and panel sources the two data settings switch between.

``use_prebuilt_comics`` decides where a story's pages come from: on, one prebuilt
``.cbz`` per story; off, the Fantagraphics volume archives, with the override and
extra pages applied at read time and the title view's overrides row live.
``use_png_images`` decides where the view images come from: the PNG panels
directory, or the JPG panels zip in Reader Files.

The rest of the suite runs on whatever the live profile (or ``run_gui_tests.sh
--prebuilt``/``--png-images``) says. Each test here pins its own value, so every
source whose data is on this machine is read once per run; a source whose data is
missing skips rather than fails, so a machine without the volumes stays green.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from gui_driver import Pick

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

READ = Pick(pages=2, dwell=0.0)
VOLUMES_LOAD_TIMEOUT = 60
JPG_PANELS_ZIP = Path("Reader Files") / "Barks Panels.zip"


def _ini_dir(app_boot: AppBoot, key: str) -> Path:
    """Return a directory setting from the scratch ini, ``${HOME}`` expanded as the app does."""
    return Path(
        os.path.expandvars(harness.read_ini_value(app_boot.scratch / "barks-reader.ini", key))
    )


def _require_dir(path: Path, what: str) -> None:
    if not path.is_dir():
        pytest.skip(f"{what} not on this machine: {path}")


def test_a_story_reads_from_the_fantagraphics_volumes(boot: AppBoot) -> None:
    """With prebuilt comics off, the volumes load at boot and a story reads from them."""
    _require_dir(_ini_dir(boot, "fanta_dir"), "the Fantagraphics volumes")
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES, ini={"use_prebuilt_comics": "0"})
    d.wait_for(pattern(markers.VOLUMES_LOADED), VOLUMES_LOAD_TIMEOUT)
    assert d.match_count(markers.USING_VOLUME_ARCHIVES) == 1
    assert d.match_count(markers.USING_PREBUILT_ARCHIVES) == 0

    d.open_story(Pick(nodes.GHOST_OF_THE_GROTTO_TITLE, pages=READ.pages, dwell=READ.dwell))
    assert d.current_page() >= 1, "a page must have turned before the reader closed"


def test_a_story_reads_from_the_volumes_with_its_override_off(boot: AppBoot) -> None:
    """The overrides row only exists on this source; not ticked, the story still opens and reads."""
    _require_dir(_ini_dir(boot, "fanta_dir"), "the Fantagraphics volumes")
    d = boot(nodes.THE_FIREBUG, cues=nodes.NO_CUES, ini={"use_prebuilt_comics": "0"})
    d.wait_for(pattern(markers.VOLUMES_LOADED), VOLUMES_LOAD_TIMEOUT)
    d.focus_portal()
    d.move_focus("Up")  # the overrides row sits right above the portal (no cue, no goto row)
    d.key_then_wait(pattern(markers.USE_OVERRIDES_CHANGED, value=False), "Return")
    d.move_focus("Down")
    d.key_then_wait(pattern(markers.ALL_IMAGES_LOADED), "Return", timeout=30)
    d.wait_for(pattern(markers.SHOWED_PAGE))
    d.read_pages(READ)
    assert d.current_page() >= 1
    d.close_reader()


def test_a_story_reads_from_the_prebuilt_archives(boot: AppBoot) -> None:
    """With prebuilt comics on, nothing loads at boot and a story reads from its cbz."""
    _require_dir(_ini_dir(boot, "prebuilt_dir"), "the prebuilt comics")
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES, ini={"use_prebuilt_comics": "1"})
    assert d.match_count(markers.USING_PREBUILT_ARCHIVES) == 1
    assert d.match_count(markers.USING_VOLUME_ARCHIVES) == 0

    d.open_story(Pick(nodes.GHOST_OF_THE_GROTTO_TITLE, pages=READ.pages, dwell=READ.dwell))
    assert d.current_page() >= 1


def test_view_images_come_from_the_jpg_panels(boot: AppBoot) -> None:
    """With PNG images off, the fun view's images are the JPGs from the panels zip."""
    data_dir = harness.app_data_dir()
    if data_dir is None or not (data_dir / JPG_PANELS_ZIP).is_file():
        pytest.skip(f"the JPG panels zip not on this machine: {data_dir}/{JPG_PANELS_ZIP}")
    d = boot(nodes.THE_STORIES, ini={"use_png_images": "0"})
    a_jpg = pattern(markers.FUN_IMAGE_LOADED, filename=re.compile(r'[^"]+\.jpg'))
    with d.expect(a_jpg):
        d.main_menu_button("change_pics")
    assert d.match_count(pattern(markers.FUN_IMAGE_LOADED, filename=re.compile(r'[^"]+\.png'))) == 0
