import sys
from configparser import ConfigParser
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

from loguru import logger

from barks_reader.core.config_info import ConfigInfo, get_app_exe_dir
from barks_reader.core.reader_consts_and_types import FANTAGRAPHICS_BARKS_LIBRARY
from barks_reader.core.reader_utils import quote_and_join_with_and
from barks_reader.ui.error_handling import handle_app_fail, handle_app_fail_with_traceback

_APP_TYPE = "Installer"
_APP_NAME = "Barks Reader Installation"

_ZIP_CONFIGS_SUBDIR = "Configs/"
_ZIP_READER_FILES_SUBDIR = "Reader Files/"
_ZIP_DATA_INSTALLER_FILES = ["barks-reader-data-1.zip", "barks-reader-data-2.zip"]

_EXPECTED_FANTA_VOLUMES_DIR_NAME = FANTAGRAPHICS_BARKS_LIBRARY

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
        _check_cython_compiled_module_is_correct()

        # The installer runs from the standalone executable and expects the data zips to sit
        # in the same directory as the executable (``_barks_reader_exe_dir``). Confirm the
        # executable is where we think it is before looking for those zips.
        logger.info("Checking that we are running from the correct executable.")
        _check_barks_reader_exe_location(config_info)

        logger.info(f'Checking for an existing app config path "{config_info.app_config_path}".')
        if config_info.app_config_path.is_file():
            logger.info("Found app config path. Exiting installer - assume app already installed.")
            return

        logger.info("Checking that the installer zips are OK.")
        installer_zip_paths = _check_installer_zips()

        fanta_volumes_dir = _run_installer(config_info, installer_zip_paths)
        logger.info("Finished installing config and data files.")

    except Exception:  # noqa: BLE001
        logger.exception("An installer error occurred:")
        _handle_installer_exception(*sys.exc_info())
    else:
        _show_success_message(config_info, fanta_volumes_dir)


def _show_success_message(config_info: ConfigInfo, fanta_volumes_dir: Path | None) -> None:
    from barks_reader.core.minimal_config_info import get_minimal_config_options  # noqa: PLC0415
    from barks_reader.first_run_installer_show_message import (  # noqa: PLC0415
        show_installer_message,
    )

    minimal_config_options = get_minimal_config_options(config_info)
    data_zips = [Path(p) for p in _ZIP_DATA_INSTALLER_FILES]

    logger.debug("Preparing to show installation success message.")

    show_installer_message(
        "Installation Complete",
        fanta_volumes_dir,
        data_zips,
        config_info.app_config_dir,
        config_info.app_log_path,
        size=(800, 950),
        background_image_file=minimal_config_options.success_background_path,
    )


def _check_cython_compiled_module_is_correct() -> None:
    from barks_reader.core.reader_utils import safe_import_check  # noqa: PLC0415

    if not safe_import_check("comic_utils.get_panel_bytes"):
        _handle_cython_compiled_module_sanity_check_failed()


def _check_barks_reader_exe_location(config_info: ConfigInfo) -> None:
    barks_reader_exe = _barks_reader_exe_dir / config_info.get_executable_name()
    logger.info(f'Checking for the correct executable path: "{barks_reader_exe}".')

    if not barks_reader_exe.is_file():
        _handle_could_not_find_exe_error(barks_reader_exe)
        sys.exit(1)


def _check_installer_zips() -> list[Path]:
    installer_zip_paths = []
    for zip_file in _ZIP_DATA_INSTALLER_FILES:
        installer_zip = _barks_reader_exe_dir / zip_file

        logger.info(f'Checking existence of installer zip: "{installer_zip}".')

        if not installer_zip.is_file():
            _handle_could_not_find_data_zip_error(installer_zip)

        installer_zip_paths.append(installer_zip)

    return installer_zip_paths


def _run_installer(config_info: ConfigInfo, installer_zip_paths: list[Path]) -> Path | None:
    assert len(installer_zip_paths) == 2  # noqa: PLR2004

    logger.info(
        f'Found installer zips "{quote_and_join_with_and(installer_zip_paths)}".'
        f" Continuing with installer script."
    )

    logger.info(
        f'Installing Barks Reader and Kivy configs to directory "{config_info.app_config_dir}".'
    )
    _extract_subdir(installer_zip_paths[0], _ZIP_CONFIGS_SUBDIR, config_info.app_config_dir)

    reader_files_dir = config_info.app_data_dir / _ZIP_READER_FILES_SUBDIR
    logger.info(f'Installing Barks Reader support files to directory "{reader_files_dir}".')
    _extract_subdir(installer_zip_paths[0], _ZIP_READER_FILES_SUBDIR, reader_files_dir)
    _extract_subdir(installer_zip_paths[1], _ZIP_READER_FILES_SUBDIR, reader_files_dir)

    return _configure_fanta_volumes_for_platform(config_info)


def _configure_fanta_volumes_for_platform(config_info: ConfigInfo) -> Path | None:
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

    barks_config = ConfigParser()
    barks_config.read(config_info.app_config_path)

    barks_config.set(BARKS_READER_SECTION, FANTA_DIR, str(fanta_volumes_dir))
    with config_info.app_config_path.open("w") as configfile:
        barks_config.write(configfile)
    logger.info(f'Rewrote fanta volumes setting as "{fanta_volumes_dir}".')

    return fanta_volumes_dir


def _extract_subdir(installer_zip: Path, subdir: str, extract_to_dir: Path) -> None:
    with ZipFile(installer_zip, "r") as installer_files:
        for member in installer_files.infolist():
            # TODO: Does this work with Windows????
            if member.is_dir() or not member.filename.startswith(subdir):
                continue

            # Create the new path by stripping the subdir prefix.
            relative_path = member.filename.removeprefix(subdir)
            target_path = extract_to_dir / relative_path

            # Ensure the parent directory exists.
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract the file by reading from the zip and writing to the new path.
            with installer_files.open(member) as source, target_path.open("wb") as target:
                target.write(source.read())


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


def _handle_cython_compiled_module_sanity_check_failed() -> None:
    message = "The Cython-protected module failed to load."
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


def _handle_could_not_find_exe_error(barks_reader_exe: Path) -> None:
    message = f'Could not find the Barks Reader executable:\n\n[b]"{barks_reader_exe}".[/b]'
    details = (
        f"The Barks Reader executable is expected to be found in the same directory"
        f' the installer is running from:\n\n[b]"{_barks_reader_exe_dir}".[/b]'
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
    message = f'Could not find the Barks Reader installer zip:\n\n[b]"{installer_zip}".[/b]'
    details = (
        f"The Barks Reader installer zip should be in the same"
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
