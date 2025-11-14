#!/usr/bin/env python3
"""
Test loading images from a ZIP into Kivy textures using:
  - Sequential decode
  - Threaded decode

Decode (ZIP read + PIL) happens in worker threads.
Texture creation happens only in the Kivy main thread.

Outputs:
  - Per-image decode time
  - Texture upload time
  - Total + average times
  - Peak Python memory
"""

from __future__ import annotations

import io
import os
import sys
import time
import zipfile
import statistics
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List

from PIL import Image as PILImage

# ---- Kivy setup (window hidden) ---------------------------------------------

from kivy.config import Config

Config.set("kivy", "log_level", "info")

from kivy.core.window import Window

Window.hide()

from kivy.graphics.texture import Texture


# ---- CONFIG: edit these if desired -----------------------------------------

# Default zip path if not given on CLI
ZIP_PATH = "/home/greg/Books/Carl Barks/The Comics/Donald Duck Adventures/016 Lost in the Andes! [FC 223].cbz"

# Default list of files inside the zip if not given on CLI
FILES_TO_TEST: list[str] = [
    "images/2-01.jpg",
    "images/2-02.jpg",
    "images/2-03.jpg",
    "images/2-04.jpg",
    "images/2-05.jpg",
    "images/2-06.jpg",
    "images/2-07.jpg",
    "images/2-08.jpg",
    "images/2-09.jpg",
    "images/2-10.jpg",
]


# ---- Helpers ----------------------------------------------------------------


def normalize_zip_path(name: str) -> str:
    if name.startswith("/"):
        name = name[1:]
    if name.startswith("./"):
        name = name[2:]
    return name


# ---- Worker-thread decode ---------------------------------------------------


def decode_image(
    zip_file: zipfile.ZipFile, filename: str
) -> tuple[str, float, tuple[int, int, bytes]]:
    """
    Worker-thread function:
      - Reads from ZIP
      - Decodes via PIL
    Returns:
      (filename, decode_time, (width, height, rgba_bytes))
    """
    start = time.perf_counter()

    zip_name = normalize_zip_path(filename)
    data = zip_file.read(zip_name)

    pil_img = PILImage.open(io.BytesIO(data)).convert("RGBA")
    w, h = pil_img.size
    rgba = pil_img.tobytes()

    dt = time.perf_counter() - start
    return filename, dt, (w, h, rgba)


# ---- Main-thread texture creation ------------------------------------------


def upload_texture(decoded: tuple[int, int, bytes]) -> float:
    """
    Runs in the main thread:
      - Create Texture
      - Upload pixel buffer

    Returns the texture upload time in seconds.
    """
    w, h, rgba = decoded
    start = time.perf_counter()

    tex = Texture.create(size=(w, h), colorfmt="rgba")
    tex.blit_buffer(rgba, colorfmt="rgba", bufferfmt="ubyte")
    tex.flip_vertical()

    return time.perf_counter() - start


# ---- Sequential test --------------------------------------------------------


def run_sequential_test(zip_file, filenames):
    print("\n=== Sequential (decode + upload in order) ===")

    decode_times = []
    upload_times = []

    tracemalloc.start()
    start_total = time.perf_counter()

    for fn in filenames:
        name, dt_decode, decoded = decode_image(zip_file, fn)
        dt_upload = upload_texture(decoded)

        decode_times.append(dt_decode)
        upload_times.append(dt_upload)
        print(f"{fn}: decode={dt_decode:.4f} s, upload={dt_upload:.4f} s")

    total = time.perf_counter() - start_total
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("\nSequential summary:")
    print(f"  Images: {len(filenames)}")
    print(f"  Avg decode: {statistics.mean(decode_times):.4f} s")
    print(f"  Avg upload: {statistics.mean(upload_times):.4f} s")
    print(f"  Total:      {total:.4f} s")
    print(f"  Peak Python mem: {peak / (1024 * 1024):.2f} MiB")


# ---- Threaded decode test ---------------------------------------------------


def run_threaded_test(zip_file, filenames, max_workers=None):
    print("\n=== Threaded decode (main-thread upload) ===")

    decode_times = []
    upload_times = []

    tracemalloc.start()
    start_total = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(decode_image, zip_file, fn): fn for fn in filenames}

        # As decoded pages come in, upload textures in main thread
        for future in as_completed(future_map):
            fn = future_map[future]

            try:
                name, dt_decode, decoded = future.result()
            except Exception as e:
                print(f"{fn}: ERROR {e!r}")
                continue

            decode_times.append(dt_decode)
            dt_upload = upload_texture(decoded)
            upload_times.append(dt_upload)

            print(f"{fn}: decode={dt_decode:.4f} s, upload={dt_upload:.4f} s")

    total = time.perf_counter() - start_total
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("\nThreaded summary:")
    print(f"  Images: {len(filenames)}")
    print(f"  Avg decode: {statistics.mean(decode_times):.4f} s")
    print(f"  Avg upload: {statistics.mean(upload_times):.4f} s")
    print(f"  Total:      {total:.4f} s")
    print(f"  Peak Python mem: {peak / (1024 * 1024):.2f} MiB")


# ---- Main entry -------------------------------------------------------------


def main(argv):
    if len(argv) >= 2:
        zip_path = argv[1]
        filenames = argv[2:] or FILES_TO_TEST
    else:
        zip_path = ZIP_PATH
        filenames = FILES_TO_TEST

    if not zip_path:
        print("ERROR: No ZIP given.")
        return 1
    if not filenames:
        print("ERROR: No filenames given.")
        return 1

    filenames = [normalize_zip_path(fn) for fn in filenames]

    if not os.path.exists(zip_path):
        print("ZIP not found:", zip_path)
        return 1

    print("ZIP:", zip_path)
    print("Files:", filenames)

    with zipfile.ZipFile(zip_path, "r") as zf:
        run_sequential_test(zf, filenames)
        run_threaded_test(zf, filenames, max_workers=10)

    print("\nAll tests completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
