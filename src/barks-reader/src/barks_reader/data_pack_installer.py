"""The data pack installer: newer packs beside the executable replace the installed data.

The reader spawns this (``main.py``, `INSTALL_DATA_PACK_ARG`) after the user accepts
its offer to install the packs, and closes: its open panels zip and index files must
be closed before the Reader Files folder can move. This process extracts both packs
into "Reader Files.new", checks what came out against the version the packs claimed,
swaps the folders, removes the old one, says so, and starts the reader again.

It never touches the config, so the user's settings survive, and never sets the
first-run installer's failed flag: a failed update leaves the installed data as it
was, and the reader runs on it.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from barks_reader.core import data_pack
from barks_reader.core.config_info import IS_COMPILED, ConfigInfo, get_app_exe_dir
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, DataPackInfo, UpdateStatus
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_utils import get_centred_position_on_primary_monitor
from barks_reader.installer_support import (
    ZIP_READER_FILES_SUBDIR,
    InstallerDataError,
    extract_subdir,
)
from barks_reader.ui.error_handling import handle_app_fail, handle_app_fail_with_traceback

if TYPE_CHECKING:
    from pathlib import Path

_APP_TYPE = "Installer"
_APP_NAME = "Barks Reader Data Pack Update"
_POPUP_SIZE = (720, 420)


def main() -> int:
    """Install the packs beside the executable over the installed data; then restart.

    Returns:
        0 when the reader has been started again on the new data. A failure shows the
        installer error popup, which exits the process.

    """
    exe_dir = get_app_exe_dir()
    log_file = (
        exe_dir / f"barks-reader-data-pack-update-{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
    )
    logger.add(log_file)
    logger.info(
        f'Data pack installer running: sys.argv[0] = "{sys.argv[0]}", exe dir = "{exe_dir}".'
    )

    config_info = ConfigInfo()
    try:
        installed = _install(config_info, exe_dir)
    except InstallerDataError as e:
        logger.error(f"The data pack update stopped: {e.message} {e.details}")
        handle_app_fail(
            _APP_TYPE,
            _APP_NAME,
            e.message,
            e.details,
            str(log_file),
            log_the_error=False,
            background_image_file=None,
            show_details=True,
        )
    except Exception:  # noqa: BLE001
        logger.exception("The data pack update failed:")
        handle_app_fail_with_traceback(
            _APP_TYPE,
            _APP_NAME,
            *sys.exc_info(),
            str(log_file),
            log_the_error=False,
            background_image_file=None,
        )
    else:
        logger.info(f"Installed {installed.display()}.")
        _show_success_message(config_info, installed)
    return 0


def _install(config_info: ConfigInfo, exe_dir: Path) -> DataPackInfo:
    reader_files = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
    pack_dir = data_pack.pack_dir_for_update(exe_dir, is_compiled=IS_COMPILED, env=os.environ)
    check = data_pack.find_update(pack_dir, data_pack.read_installed(reader_files))
    if check.status is not UpdateStatus.UPDATE_AVAILABLE or check.available is None:
        msg = "There is no newer data pack to install."
        raise InstallerDataError(msg, check.no_update_message())
    available = check.available
    assert pack_dir is not None
    logger.info(f'Installing {available.display()} from "{pack_dir}" over "{reader_files}".')

    data_pack.clear_leftovers(reader_files)
    new_dir = data_pack.new_dir_for(reader_files)
    for pack_name in DATA_PACK_FILE_NAMES:
        extract_subdir(pack_dir / pack_name, ZIP_READER_FILES_SUBDIR, new_dir)

    problems = data_pack.verify_extracted(new_dir, available)
    if problems:
        shutil.rmtree(new_dir, ignore_errors=True)
        msg = f"The extracted {available.short()} is not what its packs promised."
        details = (
            "\n".join(problems)
            + "\n\nThe installed data was left as it was. Download both packs again and"
            " check them against the release's SHA256SUMS.txt."
        )
        raise InstallerDataError(msg, details)

    try:
        old_dir = data_pack.swap_reader_files(reader_files)
    except PermissionError as exc:
        shutil.rmtree(new_dir, ignore_errors=True)
        msg = (
            f'The folder [b]"{reader_files}"[/b] is in use, so the new data could not be moved in.'
        )
        details = (
            f"{exc}\n\nClose the Barks Reader, and any window showing that folder, and"
            " try the update again. The installed data was left as it was."
        )
        raise InstallerDataError(msg, details) from exc

    if old_dir is not None:
        shutil.rmtree(old_dir, ignore_errors=True)
        if old_dir.exists():
            logger.warning(f'Could not remove "{old_dir}"; the next update will.')
    return available


def _show_success_message(config_info: ConfigInfo, installed: DataPackInfo) -> None:
    # Kivy only now: config_info must be constructed before any kivy import (its guard).
    from kivy import Config  # noqa: PLC0415
    from kivy.uix.label import Label  # noqa: PLC0415

    from barks_reader.core.minimal_config_info import get_minimal_config_options  # noqa: PLC0415
    from barks_reader.ui.kivy_standalone_show_message import show_standalone_popup  # noqa: PLC0415

    # Set the window pos and size now to avoid moving window flicker.
    x, y = get_centred_position_on_primary_monitor(*_POPUP_SIZE)
    Config.set("graphics", "left", x)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "top", y)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "width", _POPUP_SIZE[0])  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "height", _POPUP_SIZE[1])  # ty:ignore[unresolved-attribute]

    content = Label(
        text=success_text(installed),
        markup=True,
        halign="center",
        valign="middle",
        padding=(24, 24),
    )
    content.bind(size=lambda widget, size: setattr(widget, "text_size", size))

    # The new Reader Files' art; the popup matters more than its background.
    try:
        background = get_minimal_config_options(config_info).success_background_path
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"No background for the success popup: {exc}")
        background = None

    show_standalone_popup(
        "Data Pack Updated",
        content,
        size_hint=(0.92, 0.85),
        add_close_button=True,
        background_image_file=background,
        on_dismiss=_restart_reader,
    )


def success_text(installed: DataPackInfo) -> str:
    """Return what the success popup says."""
    return (
        f"[b]{installed.display()}[/b] is installed.\n\n"
        f"The Barks Reader will now start.\n\n"
        f"You can delete the two [i].barkspack[/i] files beside it."
    )


def _restart_reader() -> None:
    command = data_pack.self_command(
        is_compiled=IS_COMPILED, argv0=sys.argv[0], executable=sys.executable
    )
    logger.info(f"Starting the Barks Reader again: {command}.")
    data_pack.spawn_detached(command)


if __name__ == "__main__":
    sys.exit(main())
