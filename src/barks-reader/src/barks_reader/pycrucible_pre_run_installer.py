import tempfile
from configparser import ConfigParser
from pathlib import Path
from zipfile import ZipFile

from loguru import logger

from barks_reader.config_info import (
    ConfigInfo,
    get_barks_reader_installer_failed_flag_file,
    remove_barks_reader_installer_failed_flag,
    set_barks_reader_installer_failed_flag,
)
from barks_reader.platform_info import PLATFORM
from barks_reader.reader_settings import BARKS_READER_SECTION, FANTA_DIR

ZIP_CONFIGS_SUBDIR = "Configs/"
ZIP_READER_FILES_SUBDIR = "Reader Files/"


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

        logger.info(f'Checking for correct executable directory: "{Path().cwd().parent}".')
        barks_reader_exists, barks_reader_exe = check_barks_reader_exe_location(config_info)
        if not barks_reader_exists:
            set_installer_failed_flag()
            return

        logger.info(f'Checking for existing app config path "{config_info.app_config_path}".')
        if config_info.app_config_path.is_file():
            logger.info("Found app config path. Exiting - nothing to do.")
            return

        installer_zip = barks_reader_exe.parent / "barks-reader-installer.zip"
        logger.info(f'Checking for installer zip: "{installer_zip}".')
        if not installer_zip.is_file():
            logger.critical(f'Could not find the Barks Reader installer zip: "{installer_zip}".')
            logger.info(
                f"It should be in the same directory as the"
                f' Barks Reader executable: "{barks_reader_exe}".'
            )
            set_installer_failed_flag()
            return

        run_installer(config_info, installer_zip)

    except Exception as e:  # noqa: BLE001
        logger.critical(f"An installer error occurred: {e}.")
        set_installer_failed_flag()


def check_barks_reader_exe_location(config_info: ConfigInfo) -> tuple[bool, Path]:
    barks_reader_exe = Path.cwd().parent / config_info.get_executable_name()
    if not barks_reader_exe.is_file():
        logger.critical(f'Could not find the Barks Reader executable: "{barks_reader_exe}".')
        logger.info(
            f"It should be in the parent directory of the directory this installer"
            f' script is running from: "{Path.cwd()}".'
        )
        return False, barks_reader_exe

    return True, barks_reader_exe


def run_installer(config_info: ConfigInfo, installer_zip: Path) -> None:
    logger.info(f'Found installer zip "{installer_zip}". Continuing with installer script.')

    logger.info(
        f'Installing Barks Reader and Kivy configs to directory "{config_info.app_config_dir}".'
    )
    extract_subdir(installer_zip, ZIP_CONFIGS_SUBDIR, config_info.app_config_dir)

    reader_files_dir = config_info.app_data_dir / ZIP_READER_FILES_SUBDIR
    logger.info(f'Installing Barks Reader support files to directory "{reader_files_dir}".')
    extract_subdir(installer_zip, ZIP_READER_FILES_SUBDIR, reader_files_dir)

    configure_for_platform(config_info)


def configure_for_platform(config_info: ConfigInfo) -> None:
    barks_config = ConfigParser()
    barks_config.read(config_info.app_config_path)

    fanta_volumes = barks_config.get(BARKS_READER_SECTION, FANTA_DIR)
    fanta_volumes = config_info.app_data_dir / fanta_volumes
    barks_config.set(BARKS_READER_SECTION, FANTA_DIR, str(fanta_volumes))
    with config_info.app_config_path.open("w") as configfile:
        barks_config.write(configfile)
    logger.info(f'Rewrote fanta volumes setting as "{fanta_volumes}".')


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
