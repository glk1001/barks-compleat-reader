# ruff: noqa: ERA001

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo

from .comic_consts import JPG_FILE_EXT, PNG_FILE_EXT

if TYPE_CHECKING:
    from pathlib import Path

    from PIL.Image import Image as PilImage

Image.MAX_IMAGE_PIXELS = None

SAVE_PNG_COMPRESSION = 9
SAVE_JPG_QUALITY = 95
SAVE_JPG_COMPRESS_LEVEL = 9

METADATA_PROPERTY_GROUP = "BARKS"

JPEG_PIL_FORMAT = "JPEG"
PNG_PIL_FORMAT = "PNG"
_EXTENSION_TO_PIL_FORMAT = {
    JPG_FILE_EXT: JPEG_PIL_FORMAT,
    PNG_FILE_EXT: PNG_PIL_FORMAT,
}


def open_pil_image_for_reading(file: Path) -> PilImage:
    current_log_level = logging.getLogger().level
    try:
        logging.getLogger().setLevel(logging.INFO)
        return Image.open(str(file), "r")
    finally:
        logging.getLogger().setLevel(current_log_level)


def open_pil_image_from_bytes(file_bytes: bytes, ext: str) -> PilImage:
    current_log_level = logging.getLogger().level
    try:
        logging.getLogger().setLevel(logging.INFO)
        return Image.open(io.BytesIO(file_bytes), "r", formats=[_get_pil_format_from_ext(ext)])
    finally:
        logging.getLogger().setLevel(current_log_level)


def _get_pil_format_from_ext(ext: str) -> str:
    try:
        return _EXTENSION_TO_PIL_FORMAT[ext.lower()]
    except KeyError as e:
        msg = f"Unsupported image extension for PIL: '{ext}'."
        raise ValueError(msg) from e


def get_image_as_png_bytes(file: Path) -> io.BytesIO:
    pil_image = open_pil_image_for_reading(file)
    return get_pil_image_as_png_bytes(pil_image)


def get_pil_image_as_png_bytes(pil_image: PilImage) -> io.BytesIO:
    data = io.BytesIO()
    pil_image.save(
        data,
        format=PNG_PIL_FORMAT,
        optimize=True,
        compress_level=SAVE_PNG_COMPRESSION,
        quality=SAVE_PNG_COMPRESSION,
    )
    return data


def get_pil_image_as_jpg_bytes(pil_image: PilImage) -> io.BytesIO:
    data = io.BytesIO()
    pil_image.save(
        data,
        format=JPEG_PIL_FORMAT,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=SAVE_JPG_QUALITY,
    )
    return data


def copy_file_to_jpg(srce_file: Path, dest_file: Path) -> None:
    image = open_pil_image_for_reading(srce_file).convert("RGB")

    image.save(
        str(dest_file),
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=SAVE_JPG_QUALITY,
    )


def copy_file_to_png(srce_file: Path, dest_file: Path) -> None:
    image = open_pil_image_for_reading(srce_file)

    image.save(
        str(dest_file),
        optimize=True,
        compress_level=SAVE_PNG_COMPRESSION,
        quality=SAVE_PNG_COMPRESSION,
    )


def downscale_jpg(width: int, height: int, srce_file: Path, dest_file: Path) -> None:
    image_resized = get_downscaled_jpg(width, height, srce_file)

    image_resized.save(
        str(dest_file),
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=SAVE_JPG_QUALITY,
    )


def get_downscaled_jpg(width: int, height: int, srce_file: Path) -> PilImage:
    image = open_pil_image_for_reading(srce_file).convert("RGB")

    return ImageOps.contain(
        image,
        (width, height),
        Image.Resampling.LANCZOS,
    )


def add_jpg_metadata(jpg_file: Path, metadata: dict[str, str]) -> None:
    pil_image = Image.open(str(jpg_file), "r")

    jpg_metadata = PngInfo()
    for key, value in metadata.items():
        jpg_metadata.add_text(f"{METADATA_PROPERTY_GROUP}:{key}", value)

    pil_image.save(
        str(jpg_file),
        jpginfo=jpg_metadata,
        optimize=True,
        compress_level=SAVE_JPG_COMPRESS_LEVEL,
        quality=SAVE_JPG_QUALITY,
    )


def add_png_metadata(png_file: Path, metadata: dict[str, str]) -> None:
    pil_image = Image.open(str(png_file), "r")

    png_metadata = PngInfo()
    for key, value in metadata.items():
        png_metadata.add_text(f"{METADATA_PROPERTY_GROUP}:{key}", value)

    pil_image.save(
        str(png_file),
        pnginfo=png_metadata,
        optimize=True,
        compress_level=SAVE_PNG_COMPRESSION,
    )


# def get_png_metadata(png_file: str) -> Dict[str, str]:
#     pil_image = Image.open(png_file, "r")
#
#     png_metadata = pil_image.info
#
#     prefix = METADATA_PROPERTY_GROUP + ":"
#     metadata = dict()
#     for key in png_metadata:
#         if key.startswith(prefix):
#             metadata[key[len(prefix) :]] = png_metadata[key]
#
#     return metadata
#
#
# def get_jpg_metadata(jpg_file: str) -> Dict[str, str]:
#     pil_image = Image.open(jpg_file, "r")
#
#     jpg_comments = pil_image.app["COM"]
#
#     metadata = dict()
#     metadata["comments"] = jpg_comments
#
#     return metadata
