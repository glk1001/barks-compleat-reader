"""Integration tests for :mod:`barks_reader.core.image_pipeline`.

These tests exercise the pipeline with real PNG/JPG bytes and real ZIP
files on disk, so composition across stages is actually covered.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from barks_reader.core import image_pipeline
from barks_reader.core.image_pipeline import (
    convert_mode,
    decode_pil,
    encode_png_stream,
    load_pil,
    read_raw_bytes,
    resize_contain,
)
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path


def _make_png_bytes(
    size: tuple[int, int] = (20, 10),
    color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpg_bytes(size: tuple[int, int] = (20, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 0, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def _write_zip(zip_path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


class TestReadRawBytes:
    def test_read_from_filesystem_path(self, tmp_path: Path) -> None:
        data = _make_png_bytes()
        target = tmp_path / "img.png"
        target.write_bytes(data)

        assert read_raw_bytes(target) == data

    def test_read_from_zip_path_unencrypted(self, tmp_path: Path) -> None:
        data = _make_png_bytes()
        zip_path = tmp_path / "archive.zip"
        _write_zip(zip_path, {"images/p1.png": data})

        with zipfile.ZipFile(zip_path, "r") as zf:
            result = read_raw_bytes(zipfile.Path(zf, at="images/p1.png"))

        assert result == data

    def test_unsupported_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="Unsupported PanelPath type"):
            read_raw_bytes("not a path")  # ty:ignore[invalid-argument-type]


class TestDecodePil:
    def test_decode_autodetect(self) -> None:
        pil = decode_pil(_make_png_bytes((30, 15)))

        assert pil.size == (30, 15)

    def test_decode_with_ext_hint(self) -> None:
        pil = decode_pil(_make_png_bytes((8, 4)), ext=".png")

        assert pil.size == (8, 4)

    def test_decode_jpg_with_ext_hint(self) -> None:
        pil = decode_pil(_make_jpg_bytes((12, 6)), ext=".jpg")

        assert pil.size == (12, 6)

    def test_invalid_bytes_raises(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, PT011
            decode_pil(b"not an image")


class TestLoadPil:
    def test_load_pil_from_filesystem_path(self, tmp_path: Path) -> None:
        target = tmp_path / "pic.png"
        target.write_bytes(_make_png_bytes((40, 20)))

        pil = load_pil(target)

        assert pil.size == (40, 20)

    def test_load_pil_from_unencrypted_zip(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "a.zip"
        _write_zip(zip_path, {"dir/x.png": _make_png_bytes((16, 8))})

        with zipfile.ZipFile(zip_path, "r") as zf:
            pil = load_pil(
                zipfile.Path(zf, at="dir/x.png"),
                encrypted_zip=False,
                use_ext_hint=True,
            )

        assert pil.size == (16, 8)

    def test_load_pil_encrypted_zip_delegates_to_allow_listed_loader(self, tmp_path: Path) -> None:
        """Encrypted reads must go through comic_utils' allow-listed loader.

        The compiled panel-key module rejects decryption requested from this
        module, so ``load_pil`` must delegate the encrypted-zip case to
        ``load_pil_image_from_zip`` rather than decrypting here.
        """
        zip_path = tmp_path / "enc.zip"
        _write_zip(zip_path, {"p.png": b"cipher"})
        sentinel = Image.new("RGB", (5, 5))

        with (
            zipfile.ZipFile(zip_path, "r") as zf,
            patch.object(
                image_pipeline, "load_pil_image_from_zip", return_value=sentinel
            ) as mock_loader,
        ):
            zip_member = zipfile.Path(zf, at="p.png")
            result = load_pil(zip_member, encrypted_zip=True, use_ext_hint=True)

        mock_loader.assert_called_once_with(zip_member, encrypted=True)
        assert result is sentinel


class TestTransformStages:
    def test_convert_mode_to_rgba(self) -> None:
        pil = Image.new("RGB", (4, 4))

        result = convert_mode(pil, "RGBA")

        assert result.mode == "RGBA"

    def test_resize_contain_shrinks_to_fit(self) -> None:
        pil = Image.new("RGB", (400, 200))

        result = resize_contain(pil, 100, 100)

        # Aspect ratio 2:1, max 100x100 → contained to 100x50.
        assert result.size == (100, 50)

    def test_encode_png_stream_round_trip(self) -> None:
        pil = Image.new("RGB", (10, 5), (123, 45, 67))

        stream = encode_png_stream(pil, compress_level=0)

        assert stream.tell() == 0
        decoded = Image.open(stream)
        decoded.load()
        assert decoded.size == (10, 5)


class TestEndToEndPipeline:
    """Integration test: ZIP archive → ready-to-display PNG bytes."""

    def test_full_pipeline_from_real_zip(self, tmp_path: Path) -> None:
        source_bytes = _make_png_bytes((1000, 500), color=(10, 20, 30))
        zip_path = tmp_path / "book.cbz"
        _write_zip(zip_path, {"images/p01.png": source_bytes})

        with zipfile.ZipFile(zip_path, "r") as zf:
            pil = load_pil(
                zipfile.Path(zf, at="images/p01.png"),
                encrypted_zip=False,
                use_ext_hint=True,
            )
            pil = convert_mode(pil, "RGBA")
            pil = resize_contain(pil, 200, 200)
            stream = encode_png_stream(pil, compress_level=0)

        decoded = Image.open(stream)
        decoded.load()
        assert decoded.size == (200, 100)  # aspect 2:1 preserved
        assert decoded.mode == "RGBA"
