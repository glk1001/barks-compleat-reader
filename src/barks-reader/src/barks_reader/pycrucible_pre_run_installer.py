import tempfile
from configparser import ConfigParser
from pathlib import Path
from zipfile import ZipFile

from loguru import logger

from barks_reader.config_info import (
    ConfigInfo,
    find_fanta_volumes_dirpath,
    get_barks_reader_installer_failed_flag_file,
    remove_barks_reader_installer_failed_flag,
    set_barks_reader_installer_failed_flag,
)
from barks_reader.message_popup import show_message
from barks_reader.minimal_config_info import get_minimal_config_options
from barks_reader.platform_info import PLATFORM
from barks_reader.reader_settings import BARKS_READER_SECTION, FANTA_DIR

ZIP_CONFIGS_SUBDIR = "Configs/"
ZIP_READER_FILES_SUBDIR = "Reader Files/"
ZIP_DATA_INSTALLER_FILE = "barks-reader-data.zip"

EXPECTED_FANTA_VOLUMES_DIR_NAME = "Fantagraphics Complete Carl Barks Disney Library"


def main() -> None:
    remove_barks_reader_installer_failed_flag()

    try:
        log_file = Path(tempfile.gettempdir()) / "barks-reader-installer.log"
        logger.add(log_file)
        logger.info(
            f"Installer script running: platform = '{PLATFORM.value}', log file = '{log_file}'."
        )

        config_info = ConfigInfo()

        # Make sure we're running in the right directory. Pycrucible has been set with the options:
        #       extract_to_temp = false  # noqa: ERA001
        #       delete_after_run = true  # noqa: ERA001
        # which means the pycrucible_payload directory will be extracted at the same level as
        # the barks-reader executable. (And deleted after use.) Make sure of this.

        barks_reader_exists, barks_reader_exe = check_barks_reader_exe_location(config_info)
        if not barks_reader_exists:
            set_installer_failed_flag()
            return

        logger.info(f'Checking for existing app config path "{config_info.app_config_path}".')
        if config_info.app_config_path.is_file():
            logger.info("Found app config path. Exiting installer - assume app already installed.")
            return

        installer_zip = barks_reader_exe.parent / ZIP_DATA_INSTALLER_FILE
        logger.info(f'Checking for installer zip: "{installer_zip}".')
        if not installer_zip.is_file():
            logger.critical(f'Could not find the Barks Reader installer zip: "{installer_zip}".')
            logger.info(
                f"It should be in the same directory as the"
                f' Barks Reader executable: "{barks_reader_exe}".'
            )
            set_installer_failed_flag()
            return

        fanta_volumes_dir = run_installer(config_info, installer_zip)

    except Exception as e:  # noqa: BLE001
        logger.critical(f"An installer error occurred: {e}.")
        set_installer_failed_flag()
    else:
        show_success_message(config_info, fanta_volumes_dir)


def show_success_message(config_info: ConfigInfo, fanta_volumes_dir: Path | None) -> None:
    minimal_config_options = get_minimal_config_options(config_info)
    data_zips = ["barks-reader-data.zip"]

    fanta_msg = (
        f'The Fantagraphics Carl Barks Library was found at:\n\n"{fanta_volumes_dir}".'
        if fanta_volumes_dir
        else "The Fantagraphics Carl Barks Library was NOT found."
    )

    heading = "The Barks Reader installer successfully completed."
    msg = f"""\n
{fanta_msg}\n
The main Barks Reader app will now start.\n
Once you're happy with the app you can delete the data installer zips:\n
        "{", ".join(data_zips)}".\n
Default config files have been written to\n
        "{config_info.app_config_dir}"\n
and logging will go to\n
        "{config_info.app_log_path}".
"""

    show_message(
        msg,
        heading,
        bgnd_image_file=minimal_config_options.success_background_path,
        window_title="Barks Reader Installer Success",
    )


def check_barks_reader_exe_location(config_info: ConfigInfo) -> tuple[bool, Path]:
    this_script_dir = Path(__file__).parent
    exe_dir = this_script_dir.parent.parent.parent.parent.parent

    barks_reader_exe = exe_dir / config_info.get_executable_name()
    logger.info(f'Checking for correct executable path: "{barks_reader_exe}".')

    if not barks_reader_exe.is_file():
        logger.critical(f'Could not find the Barks Reader executable: "{barks_reader_exe}".')
        logger.info(
            f"It should be in the parent directory of the directory this installer"
            f' script is running from: "{Path.cwd()}".'
        )
        return False, barks_reader_exe

    return True, barks_reader_exe


def run_installer(config_info: ConfigInfo, installer_zip: Path) -> Path | None:
    logger.info(f'Found installer zip "{installer_zip}". Continuing with installer script.')

    logger.info(
        f'Installing Barks Reader and Kivy configs to directory "{config_info.app_config_dir}".'
    )
    extract_subdir(installer_zip, ZIP_CONFIGS_SUBDIR, config_info.app_config_dir)

    reader_files_dir = config_info.app_data_dir / ZIP_READER_FILES_SUBDIR
    logger.info(f'Installing Barks Reader support files to directory "{reader_files_dir}".')
    extract_subdir(installer_zip, ZIP_READER_FILES_SUBDIR, reader_files_dir)

    return configure_fanta_volumes_for_platform(config_info)


def configure_fanta_volumes_for_platform(config_info: ConfigInfo) -> Path | None:
    fanta_volumes_dir = find_fanta_volumes_dirpath(config_info, EXPECTED_FANTA_VOLUMES_DIR_NAME)
    if not fanta_volumes_dir:
        logger.warning(
            f"Could not find a Fantagraphics volumes directory"
            f' with the name "{EXPECTED_FANTA_VOLUMES_DIR_NAME}".'
        )
        return None

    barks_config = ConfigParser()
    barks_config.read(config_info.app_config_path)

    barks_config.set(BARKS_READER_SECTION, FANTA_DIR, str(fanta_volumes_dir))
    with config_info.app_config_path.open("w") as configfile:
        barks_config.write(configfile)
    logger.info(f'Rewrote fanta volumes setting as "{fanta_volumes_dir}".')

    return fanta_volumes_dir


def extract_subdir(installer_zip: Path, subdir: str, extract_to_dir: Path) -> None:
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


def set_installer_failed_flag() -> None:
    set_barks_reader_installer_failed_flag()
    logger.warning(
        f"Set Barks Reader installer FAILED flag file:"
        f' "{get_barks_reader_installer_failed_flag_file()}".'
    )


if __name__ == "__main__":
    main()
