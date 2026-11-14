import sys
from collections.abc import Callable
from configparser import ConfigParser
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from barks_reader.core import data_pack
from barks_reader.core.config_info import ConfigInfo, get_app_exe_dir
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, DataPackInfo, UpdateStatus
from barks_reader.core.reader_consts_and_types import FANTAGRAPHICS_BARKS_LIBRARY
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.installer_support import (
    ZIP_CONFIGS_SUBDIR,
    ZIP_READER_FILES_SUBDIR,
    InstallerDataError,
    extract_subdir,
    install_reader_files,
    read_member,
    require_subdir,
    subdir_bytes,
)
from barks_reader.ui.error_handling import handle_app_fail, handle_app_fail_with_traceback

_APP_TYPE = "Installer"
_APP_NAME = "Barks Reader Installation"

_EXPECTED_FANTA_VOLUMES_DIR_NAME = FANTAGRAPHICS_BARKS_LIBRARY

_REPORT_NOT_SHOWN = "The install is complete, but its report could not be shown:"

# The window the installer works behind, and then reports in.
_WINDOW_SIZE = (800, 950)
_PROGRESS_TITLE = "Installing the Barks Reader"
_PROGRESS_MESSAGE = (
    "[b]Setting up the Barks Reader.[/b]\n\n"
    "Its pictures and other files are being unpacked beside the app. This happens"
    " once, and takes a minute or so."
)

_CONFIG_UNREADABLE_DETAILS = (
    "The config file was just extracted from the installer data pack, so it should be"
    " readable. Download the data packs again, then run the Barks Reader again: it"
    " starts the install afresh."
)
# What the app's config waits as until the data is in place (`_install_app_config`).
_PENDING_SUFFIX = ".new"

# Directory of the running standalone executable, beside which the installer data
# zips are shipped and into which config/data are installed.
_barks_reader_exe_dir = get_app_exe_dir()
_log_file = (
    _barks_reader_exe_dir
    / f"barks-reader-installer-{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
)


def _handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
    handle_app_fail_with_traceback(
        _APP_TYPE, _APP_NAME, exc_type, exc_value, exc_traceback, str(_log_file)
    )


sys.excepthook = _handle_uncaught_exception


def main() -> None:
    """Install the configs and the data packs beside the executable, and report.

    The app's own config (the file `ConfigInfo.is_app_installed` looks for) is written
    last, once the data is in place: a failed or interrupted install leaves the app not
    installed, and the next launch runs this again. Any failure before that sets the
    failed flag, shows the installer's error popup and exits the process; nothing after
    it does, since the install is then complete.
    """
    from barks_reader.core.config_info import (  # noqa: PLC0415
        ConfigInfo,
        remove_barks_reader_installer_failed_flag,
    )
    from barks_reader.core.platform_info import PLATFORM  # noqa: PLC0415

    remove_barks_reader_installer_failed_flag()

    # noinspection PyBroadException
    try:
        logger.add(_log_file)

        logger.info(
            f"Installer running: platform = '{PLATFORM.value}',"
            f' sys.executable = "{sys.executable}",'
            f' sys.argv[0] = "{sys.argv[0]}",'
            f' exe dir = "{_barks_reader_exe_dir}",'
            f' Log file = "{_log_file}".'
        )

        config_info = ConfigInfo()

        logger.info("Checking that the compiled panel module is correctly installed.")
        _check_panel_module_is_correct()

        # The installer expects the data zips to sit in the app anchor directory
        # (``_barks_reader_exe_dir``: beside the executable, or beside the .app bundle on
        # macOS). Confirm we are running from the expected executable before looking there.
        logger.info("Checking that we are running from the correct executable.")
        _check_barks_reader_exe_location(config_info)

        logger.info(f'Checking for an existing app config path "{config_info.app_config_path}".')
        if config_info.is_app_installed():
            logger.info("Found app config path. Exiting installer - assume app already installed.")
            return

        logger.info("Checking that the installer zips are OK.")
        pack = _check_installer_zips()

        fanta_volumes_dir, success_shown = _run_installer(config_info, pack)

    except InstallerDataError as e:
        logger.error(f"An installer data error occurred: {e.message} {e.details}")
        _handle_installer_data_error(e)
    except Exception:  # noqa: BLE001
        logger.exception("An installer error occurred:")
        _handle_installer_exception(*sys.exc_info())
    else:
        if not success_shown:
            # The install is complete: a report that cannot be drawn must not fail it.
            try:
                _show_success_message(config_info, fanta_volumes_dir)
            except Exception:  # noqa: BLE001
                logger.exception(_REPORT_NOT_SHOWN)


def _show_success_message(
    config_info: ConfigInfo,
    fanta_volumes_dir: Path | None,
    on_dismiss: Callable[[], None] | None = None,
    in_running_loop: bool = False,
) -> None:
    from barks_reader.core.minimal_config_info import get_minimal_config_options  # noqa: PLC0415
    from barks_reader.first_run_installer_show_message import (  # noqa: PLC0415
        show_installer_message,
    )

    minimal_config_options = get_minimal_config_options(config_info)
    data_zips = [Path(p) for p in DATA_PACK_FILE_NAMES]

    logger.debug("Preparing to show installation success message.")

    show_installer_message(
        "Installation Complete",
        fanta_volumes_dir,
        data_zips,
        config_info.app_config_dir,
        config_info.app_log_path,
        size=_WINDOW_SIZE,
        background_image_file=minimal_config_options.success_background_path,
        on_dismiss=on_dismiss,
        in_running_loop=in_running_loop,
    )


def _check_panel_module_is_correct() -> None:
    from barks_reader.core.reader_utils import safe_import_check  # noqa: PLC0415

    if not safe_import_check("comic_utils.get_panel_bytes"):
        _handle_panel_module_sanity_check_failed()


def _check_barks_reader_exe_location(config_info: ConfigInfo) -> None:
    # The binary itself may live inside a macOS .app bundle, so validate the running
    # executable's name rather than reconstructing a path under the anchor directory.
    expected_exe_name = config_info.get_executable_name()
    running_exe = Path(sys.argv[0]).resolve()
    logger.info(f'Checking the running executable "{running_exe}" is named "{expected_exe_name}".')

    if running_exe.name != expected_exe_name:
        _handle_wrong_exe_error(running_exe, expected_exe_name)


def _check_installer_zips() -> DataPackInfo:
    """Check the two data packs beside the executable, as an update checks its packs.

    Returns:
        The version both packs carry.

    Raises:
        InstallerDataError: A pack cannot be read, was re-zipped, carries no version,
            or the two are from different releases.

    """
    # The data packs' names (and why they are not ".zip"): core/data_pack.py.
    logger.info(f'Checking the installer zips in "{_barks_reader_exe_dir}".')
    # No installed version: a first install takes whatever version the packs are.
    check = data_pack.find_update(_barks_reader_exe_dir, None)

    if check.status is UpdateStatus.PACKS_MISSING:
        _handle_could_not_find_data_zip_error(_barks_reader_exe_dir / check.missing[0])
    if check.status is UpdateStatus.PACKS_NOT_VERSIONED:
        # A re-zipped pack has no version file where it is looked for either: say that.
        for pack_name in check.missing:
            require_subdir(_barks_reader_exe_dir / pack_name, ZIP_READER_FILES_SUBDIR)
    if check.available is None:
        msg = "The Barks Reader data packs cannot be installed."
        raise InstallerDataError(msg, check.no_update_message())

    logger.info(f'Found {check.available.display()} in "{_barks_reader_exe_dir}".')
    return check.available


def _run_installer(config_info: ConfigInfo, pack: DataPackInfo) -> tuple[Path | None, bool]:
    """Install the configs, then the data behind a window showing its progress.

    Returns:
        The Fantagraphics volumes folder, if one was found, and whether the success
        message has been dealt with already (in the progress window).

    """
    from barks_reader.installer_progress import (  # noqa: PLC0415
        ByteProgress,
        run_showing_progress,
    )

    installer_zip_paths = [_barks_reader_exe_dir / name for name in DATA_PACK_FILE_NAMES]

    logger.info(
        f'Installing Barks Reader and Kivy configs to directory "{config_info.app_config_dir}".'
    )
    # The configs first, and before the window: they are small, and Kivy's own are
    # among them, so the window opens as the packs set it up. All but the app's own:
    # it is what says the app is installed, so it waits until the data is in place.
    extract_subdir(
        installer_zip_paths[0],
        ZIP_CONFIGS_SUBDIR,
        config_info.app_config_dir,
        skip=(config_info.app_config_path.name,),
    )

    reader_files_dir = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
    progress = ByteProgress(
        sum(subdir_bytes(zip_path, ZIP_READER_FILES_SUBDIR) for zip_path in installer_zip_paths)
    )
    installed: list[Path | None] = []

    def install_data() -> Path | None:
        logger.info(f'Installing Barks Reader support files to directory "{reader_files_dir}".')
        install_reader_files(pack, _barks_reader_exe_dir, reader_files_dir, progress.add)
        fanta_volumes_dir = _install_app_config(config_info, installer_zip_paths[0])
        logger.info("Finished installing config and data files.")
        installed.append(fanta_volumes_dir)
        return fanta_volumes_dir

    def show_success(fanta_volumes_dir: Path | None, end_loop: Callable[[], None]) -> None:
        _show_success_message(
            config_info, fanta_volumes_dir, on_dismiss=end_loop, in_running_loop=True
        )

    try:
        return run_showing_progress(
            install_data,
            progress,
            title=_PROGRESS_TITLE,
            message=_PROGRESS_MESSAGE,
            window_size=_WINDOW_SIZE,
            show_next=show_success,
        )
    except Exception:
        if not installed:
            raise
        # The work is done, and the report that followed it in the window failed. The
        # app is installed, so this is not a failed install; nor is the report tried
        # again outside a window loop that has just died.
        logger.exception(_REPORT_NOT_SHOWN)
        return installed[0], True


def _install_app_config(config_info: ConfigInfo, installer_zip: Path) -> Path | None:
    """Write the app's config, the install's last step: with it, the app is installed.

    The pack's copy is written under a pending name, pointed at the Fantagraphics
    volumes, and only then renamed into place, so the config is never there half-made.

    Returns:
        The Fantagraphics volumes folder, if one was found.

    """
    config_path = config_info.app_config_path
    pending_path = config_path.with_name(config_path.name + _PENDING_SUFFIX)
    pending_path.write_bytes(read_member(installer_zip, ZIP_CONFIGS_SUBDIR + config_path.name))
    try:
        fanta_volumes_dir = _configure_fanta_volumes_for_platform(config_info, pending_path)
        pending_path.replace(config_path)
    finally:
        pending_path.unlink(missing_ok=True)
    logger.info(f'Installed the Barks Reader config "{config_path}".')
    return fanta_volumes_dir


def _configure_fanta_volumes_for_platform(
    config_info: ConfigInfo, config_path: Path
) -> Path | None:
    """Point the config at ``config_path`` at the Fantagraphics volumes folder, if found."""
    from barks_reader.core.config_info import find_fanta_volumes_dirpath  # noqa: PLC0415
    from barks_reader.core.reader_settings import BARKS_READER_SECTION, FANTA_DIR  # noqa: PLC0415

    fanta_volumes_dir = find_fanta_volumes_dirpath(config_info, _EXPECTED_FANTA_VOLUMES_DIR_NAME)
    if not fanta_volumes_dir:
        logger.warning(
            f"Could not find a Fantagraphics volumes directory"
            f' with the name "{_EXPECTED_FANTA_VOLUMES_DIR_NAME}".'
        )
        return None
    logger.info(f'Found Fantagraphics volumes directory at "{fanta_volumes_dir}".')

    # The file is read and written as Kivy reads and writes it (kivy.config's
    # ConfigParser): UTF-8, whatever the machine's own encoding - Windows' is not - and
    # with "%" doubled, since both parsers take a single one for an interpolation.
    # ConfigParser.read silently skips a file it cannot open, so check its result.
    barks_config = ConfigParser()
    files_read = barks_config.read(config_path, encoding="utf-8-sig")
    if not files_read:
        msg = f'Could not read the newly installed Barks Reader config:\n\n[b]"{config_path}".[/b]'
        raise InstallerDataError(msg, _CONFIG_UNREADABLE_DETAILS)
    if not barks_config.has_section(BARKS_READER_SECTION):
        msg = (
            f'The newly installed Barks Reader config has no "[{BARKS_READER_SECTION}]"'
            f' section:\n\n[b]"{config_path}".[/b]'
        )
        raise InstallerDataError(msg, _CONFIG_UNREADABLE_DETAILS)

    barks_config.set(BARKS_READER_SECTION, FANTA_DIR, str(fanta_volumes_dir).replace("%", "%%"))
    with config_path.open("w", encoding="utf-8") as configfile:
        barks_config.write(configfile)
    logger.info(f'Rewrote fanta volumes setting as "{fanta_volumes_dir}".')

    return fanta_volumes_dir


def _set_installer_failed_flag() -> None:
    from barks_reader.core.config_info import (  # noqa: PLC0415
        get_barks_reader_installer_failed_flag_file,
        set_barks_reader_installer_failed_flag,
    )

    set_barks_reader_installer_failed_flag()
    logger.warning(
        f"Set Barks Reader installer FAILED flag file:"
        f' "{get_barks_reader_installer_failed_flag_file()}".'
    )


def _handle_installer_data_error(error: InstallerDataError) -> None:
    _set_installer_failed_flag()

    handle_app_fail(
        _APP_TYPE,
        _APP_NAME,
        error.message,
        error.details,
        str(_log_file),
        log_the_error=False,
        background_image_file=None,
        show_details=True,
    )


def _handle_panel_module_sanity_check_failed() -> None:
    _set_installer_failed_flag()

    message = "The compiled panel module failed to load."
    details = (
        "A critical part of The Barks Reader has not been configured properly. This is an"
        " unexpected error and you'll need to contact The Barks Reader developer for a fix."
    )

    handle_app_fail(
        _APP_TYPE,
        _APP_NAME,
        message,
        details,
        str(_log_file),
        log_the_error=True,
        background_image_file=None,
        show_details=True,
    )


def _handle_wrong_exe_error(running_exe: Path, expected_exe_name: str) -> None:
    _set_installer_failed_flag()

    message = f'Unexpected Barks Reader executable:\n\n[b]"{running_exe}".[/b]'
    details = (
        f"The Barks Reader executable is expected to be named"
        f' [b]"{expected_exe_name}"[/b] - it looks like the executable was renamed'
        f" or the wrong platform's executable is being run."
    )

    handle_app_fail(
        _APP_TYPE,
        _APP_NAME,
        message,
        details,
        str(_log_file),
        log_the_error=True,
        background_image_file=None,
        show_details=True,
    )


def _handle_could_not_find_data_zip_error(installer_zip: Path) -> None:
    _set_installer_failed_flag()

    message = f'Could not find the Barks Reader data pack:\n\n[b]"{installer_zip}".[/b]'
    details = (
        f"The Barks Reader data pack should be in the same"
        f' directory as the Barks Reader executable:\n\n[b]"{_barks_reader_exe_dir}".[/b]'
    )
    handle_app_fail(
        _APP_TYPE,
        _APP_NAME,
        message,
        details,
        str(_log_file),
        log_the_error=True,
        background_image_file=None,
        show_details=True,
    )


def _handle_installer_exception(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
    _set_installer_failed_flag()

    handle_app_fail_with_traceback(
        _APP_TYPE,
        _APP_NAME,
        exc_type,
        exc_value,
        exc_traceback,
        str(_log_file),
        log_the_error=False,
        background_image_file=None,
    )


if __name__ == "__main__":
    main()
