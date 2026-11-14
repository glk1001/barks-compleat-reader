"""The data pack installer: newer packs beside the executable replace the installed data.

The reader spawns this (``main.py``, `INSTALL_DATA_PACK_ARG`) after the user accepts
its offer to install the packs, and closes: its open panels zip and index files must
be closed before the Reader Files folder can move. This process extracts both packs
into "Reader Files.new", checks what came out against the version the packs claimed,
swaps the folders, removes the old one, says so, and starts the reader again.

It never touches the config, so the user's settings survive, and never sets the
first-run installer's failed flag: a failed update leaves the installed data as it
was, and the reader is started again on it once the error popup has closed.

The reader is started again by `main`, not by a popup's button: whatever closes the
window (its OK, the desktop's own close, a popup that could not be drawn), the user is
not left with no reader running. The one exception is an installed folder that a
failed swap could not put back: a reader started without it would only fail. Nor is
one started when this module was run by hand: there was no reader to start again.

To look at the success popup without installing anything (`preview_success_message`):
``uv run --env-file .env.runtime python -m barks_reader.data_pack_installer --preview``.
"""

from __future__ import annotations

import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from barks_reader.core import data_pack
from barks_reader.core.config_info import IS_COMPILED, ConfigInfo, get_app_exe_dir
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, DataPackInfo, UpdateStatus
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.installer_support import (
    ZIP_READER_FILES_SUBDIR,
    InstallerDataError,
    install_reader_files,
    subdir_bytes,
)
from barks_reader.ui.error_handling import handle_app_fail, handle_app_fail_with_traceback

if TYPE_CHECKING:
    from collections.abc import Callable

_APP_TYPE = "Installer"
_APP_NAME = "Barks Reader Data Pack Update"
# The whole window is the popup (no OS frame): its title bar is the popup's own. The
# content below the 56 px title bar keeps the success art's 1184 x 864 shape, so the art
# fills it with no bands at the sides.
_POPUP_SIZE = (900, 720)
_PROGRESS_TITLE = "Updating the Barks Reader's Data"
_PROGRESS_MESSAGE = (
    "[b]Installing the new data pack.[/b]\n\n"
    "It is being unpacked in place of the old one. This takes a minute or so, and then"
    " the Barks Reader starts again."
)
PREVIEW_ARG = "--preview"


_REPORT_NOT_SHOWN = "The data pack is installed, but the popup saying so could not be shown:"


def main() -> int:
    """Install the packs beside the executable over the installed data; then restart.

    Returns:
        0 when the reader has been started again on the new data. A failure shows the
        installer error popup and starts the reader again on the data it had, and the
        popup exits the process.

    """
    exe_dir = get_app_exe_dir()
    log_file = (
        exe_dir / f"barks-reader-data-pack-update-{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
    )
    config_info: ConfigInfo | None = None
    try:
        _add_log_file(log_file)
        logger.info(
            f'Data pack installer running: sys.argv[0] = "{sys.argv[0]}", exe dir = "{exe_dir}".'
        )
        config_info = ConfigInfo()
        installed, success_shown = _install_behind_a_window(config_info, exe_dir)
    except InstallerDataError as e:
        logger.error(f"The data pack update stopped: {e.message} {e.details}")
        try:
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
        finally:
            _restart_reader_on_the_installed_data(config_info)
    except Exception:  # noqa: BLE001
        logger.exception("The data pack update failed:")
        try:
            handle_app_fail_with_traceback(
                _APP_TYPE,
                _APP_NAME,
                *sys.exc_info(),
                str(log_file),
                log_the_error=False,
                background_image_file=None,
            )
        finally:
            _restart_reader_on_the_installed_data(config_info)
    else:
        if not success_shown:
            # The data is installed: a popup that cannot be drawn must not stop the restart.
            try:
                _show_success_message(config_info, installed)
            except Exception:  # noqa: BLE001
                logger.exception(_REPORT_NOT_SHOWN)
        _restart_reader()
    return 0


def _add_log_file(log_file: Path) -> None:
    """Log to `log_file` too; an update can still run where the file cannot be made."""
    try:
        logger.add(log_file)
    except OSError as exc:
        logger.warning(f'Could not log the data pack update to "{log_file}": {exc}')


def _restart_reader_on_the_installed_data(config_info: ConfigInfo | None) -> None:
    """Start the reader again after a failed update, if it has data to run on.

    Called as the error popup's exit passes: a failed update leaves the installed data
    as it was, except when a failed swap could not put the folder back (it is then at
    its ``.old`` name, and the next update restores it).
    """
    if config_info is None:
        logger.warning("Not starting the Barks Reader again: its config could not be set up.")
        return
    reader_files = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
    if not reader_files.is_dir():
        logger.warning(f'Not starting the Barks Reader again: "{reader_files}" is missing.')
        return
    try:
        _restart_reader()
    except Exception:  # noqa: BLE001
        logger.exception("Could not start the Barks Reader again:")


def _install_behind_a_window(config_info: ConfigInfo, exe_dir: Path) -> tuple[DataPackInfo, bool]:
    """Find the newer packs, then install them behind a window showing its progress.

    Returns:
        The pack installed, and whether the success message has been dealt with already
        (in the progress window).

    """
    from barks_reader.installer_progress import (  # noqa: PLC0415
        ByteProgress,
        run_showing_progress,
    )

    available, pack_dir, reader_files = _find_update(config_info, exe_dir)
    progress = ByteProgress(
        sum(
            subdir_bytes(pack_dir / pack_name, ZIP_READER_FILES_SUBDIR)
            for pack_name in DATA_PACK_FILE_NAMES
        )
    )
    done: list[DataPackInfo] = []

    def install() -> DataPackInfo:
        install_reader_files(available, pack_dir, reader_files, progress.add)
        logger.info(f"Installed {available.display()}.")
        done.append(available)
        return available

    def show_success(installed: DataPackInfo, end_loop: Callable[[], None]) -> None:
        _show_success_message(config_info, installed, on_dismiss=end_loop, in_running_loop=True)

    try:
        return run_showing_progress(
            install,
            progress,
            title=_PROGRESS_TITLE,
            message=_PROGRESS_MESSAGE,
            window_size=_POPUP_SIZE,
            show_next=show_success,
            borderless=True,
        )
    except Exception:
        if not done:
            raise
        # The data is installed, and the popup that followed in the window failed: not
        # a failed update, and not tried again outside a window loop that has just died.
        logger.exception(_REPORT_NOT_SHOWN)
        return done[0], True


def _find_update(config_info: ConfigInfo, exe_dir: Path) -> tuple[DataPackInfo, Path, Path]:
    """Return the newer pack beside the executable, its folder and the installed data's."""
    reader_files = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
    check = data_pack.look_for_update(
        exe_dir, reader_files, is_compiled=IS_COMPILED, env=os.environ
    )
    if check.status is not UpdateStatus.UPDATE_AVAILABLE or check.available is None:
        msg = "There is no newer data pack to install."
        raise InstallerDataError(msg, check.no_update_message())
    available = check.available
    pack_dir = check.pack_dir
    assert pack_dir is not None
    logger.info(f'Installing {available.display()} from "{pack_dir}" over "{reader_files}".')
    return available, pack_dir, reader_files


def preview_success_message() -> None:
    """Show the success popup for a made-up pack, to look at it; nothing is installed.

    Run with the reader's folders in the environment (``.env.runtime``), so the popup
    finds its background art. Closing it does not start the reader: `main` does that.
    """
    info = DataPackInfo(6, "data-v6", datetime.now(UTC), platform.node() or "preview", {})
    _show_success_message(ConfigInfo(), info)


def _show_success_message(
    config_info: ConfigInfo,
    installed: DataPackInfo,
    *,
    on_dismiss: Callable[[], None] | None = None,
    in_running_loop: bool = False,
) -> None:
    # Kivy only now: config_info must be constructed before any kivy import (its guard).
    from barks_reader.core.minimal_config_info import get_minimal_config_options  # noqa: PLC0415
    from barks_reader.core.popup_frame import FrameButton  # noqa: PLC0415
    from barks_reader.installer_progress import place_window  # noqa: PLC0415
    from barks_reader.ui.kivy_standalone_show_message import show_standalone_popup  # noqa: PLC0415

    # Set the window pos and size now to avoid moving window flicker. No OS frame: the
    # popup's own title bar is the window's top.
    place_window(_POPUP_SIZE, borderless=True)

    content = _success_content(success_text(installed))

    # The new Reader Files' art; the popup matters more than its background.
    try:
        background = get_minimal_config_options(config_info).success_background_path
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"No background for the success popup: {exc}")
        background = None

    show_standalone_popup(
        "Data Pack Updated",
        content,
        fill_window=True,
        buttons=(FrameButton("OK", lambda: None),),  # once it has closed, main restarts
        background_image_file=background,
        on_dismiss=on_dismiss,
        in_running_loop=in_running_loop,
    )


def _success_content(text: str) -> Any:  # noqa: ANN401
    """Return the popup's body: the message, over the art.

    The popup's OK button is the frame's; Return and Escape press it too, for the remote.
    """
    from kivy.metrics import dp, sp  # noqa: PLC0415
    from kivy.uix.label import Label  # noqa: PLC0415

    from barks_reader.core.reader_palette import theme  # noqa: PLC0415

    # The app's hero-title gold, outlined dark so it stands out over the art.
    label = Label(
        text=text,
        markup=True,
        font_size=sp(27),
        color=list(theme().text_display),
        outline_width=2,
        outline_color=[0.1, 0.09, 0.08, 1],
        halign="center",
        valign="middle",
        padding=(dp(24), dp(24)),
    )
    label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
    return label


def success_text(installed: DataPackInfo) -> str:
    """Return what the success popup says."""
    return (
        f"[b]{installed.display()}[/b] is installed.\n\n"
        f"The Barks Reader will now start.\n\n"
        f"You can delete the two [i].barkspack[/i] files beside it."
    )


def _run_by_hand() -> bool:
    """Return whether this module was run itself (``python -m``), not by the reader."""
    return not IS_COMPILED and Path(sys.argv[0]).resolve() == Path(__file__).resolve()


def _restart_reader() -> None:
    if _run_by_hand():
        # ``sys.argv[0]`` is then this module, not the reader: the command made from it
        # would run the installer again, and a failed one again after that.
        logger.warning("Not starting the Barks Reader: the reader did not start this update.")
        return
    command = data_pack.self_command(
        is_compiled=IS_COMPILED, argv0=sys.argv[0], executable=sys.executable
    )
    logger.info(f"Starting the Barks Reader again: {command}.")
    data_pack.spawn_detached(command)


if __name__ == "__main__":
    if sys.argv[1:] == [PREVIEW_ARG]:
        preview_success_message()
        sys.exit(0)
    sys.exit(main())
