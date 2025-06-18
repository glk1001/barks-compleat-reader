import logging
import os
import subprocess
import threading

from kivy.clock import Clock


class ComicReader:
    def __init__(
        self,
        mcomix_python_bin_path: str,
        mcomix_path: str,
        mcomix_barks_reader_config_path: str,
        the_comic_zips_dir: str,
    ):
        self.reader_is_running = False

        self.mcomix_python_bin_path = mcomix_python_bin_path
        self.mcomix_path = mcomix_path
        self.mcomix_barks_reader_config_path = mcomix_barks_reader_config_path
        self.the_comic_zips_dir = the_comic_zips_dir

        self.comic_file_stem: str = ""
        self.comic_path: str = ""

    def on_app_request_close(self):
        if self.reader_is_running:
            logging.debug(f"ComicReader: on_request_close event triggered but reader is running.")
            return True

        return False  # Returning False allows the app to close now

    def show_comic(self, comic_file_stem: str):
        self.comic_file_stem = comic_file_stem

        Clock.schedule_once(lambda dt: self.run_reader(), 0.1)

    def run_reader(self):
        self.comic_path = os.path.join(self.the_comic_zips_dir, self.comic_file_stem + ".cbz")

        threading.Thread(target=self.run_comic_reader, daemon=True).start()

    def run_comic_reader(self) -> None:
        ui_desc_path = self.mcomix_barks_reader_config_path

        run_args = [
            self.mcomix_python_bin_path,
            self.mcomix_path,
            "--ui-desc-file",
            ui_desc_path,
            self.comic_path,
        ]
        logging.info(f"Running mcomix: {' '.join(run_args)}.")

        process = subprocess.Popen(run_args, text=True)
        self.reader_is_running = True
        result = process.wait()
        logging.info(f"mcomix return code = {result}.")

        self.reader_is_running = False
