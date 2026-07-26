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
        # The offending type is the whole point of the message, so match it too.
        with pytest.raises(TypeError, match=r"Unsupported PanelPath type: <class 'str'>"):
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

    def test_defaults_are_plain_read_and_autodetect(self, tmp_path: Path) -> None:
        """Both keyword defaults are off: no decrypt attempt, no extension hint.

        Called with no keywords at all, so a flipped default would show up here
        and nowhere else - every other caller passes both explicitly.
        """
        data = _make_png_bytes((6, 3))
        zip_path = tmp_path / "plain.zip"
        _write_zip(zip_path, {"q.png": data})
        sentinel = Image.new("RGB", (5, 5))

        with (
            zipfile.ZipFile(zip_path, "r") as zf,
            patch.object(image_pipeline, "load_pil_image_from_zip") as mock_zip_loader,
            patch.object(image_pipeline, "decode_pil", return_value=sentinel) as mock_decode,
        ):
            result = load_pil(zipfile.Path(zf, at="q.png"))

        mock_zip_loader.assert_not_called()
        mock_decode.assert_called_once_with(data, ext=None)
        assert result is sentinel

    def test_ext_hint_passes_the_path_suffix_to_the_decoder(self, tmp_path: Path) -> None:
        data = _make_png_bytes((6, 3))
        target = tmp_path / "pic.png"
        target.write_bytes(data)
        sentinel = Image.new("RGB", (5, 5))

        with patch.object(image_pipeline, "decode_pil", return_value=sentinel) as mock_decode:
            result = load_pil(target, use_ext_hint=True)

        mock_decode.assert_called_once_with(data, ext=".png")
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

    def test_resize_contain_asks_for_lanczos(self) -> None:
        # The resampling filter is invisible in the output size, so the only way
        # to pin it is the call itself. LANCZOS is what keeps downscaled comic
        # line art readable; PIL's own default (BICUBIC) is softer.
        pil = Image.new("RGB", (400, 200))
        resized = Image.new("RGB", (100, 50))

        with patch.object(image_pipeline.ImageOps, "contain", return_value=resized) as mock_contain:
            result = resize_contain(pil, 100, 100)

        mock_contain.assert_called_once_with(pil, (100, 100), Image.Resampling.LANCZOS)
        assert result is resized

    def test_encode_png_stream_defaults_to_no_compression(self) -> None:
        # These streams go straight to a Kivy texture upload, so encode speed
        # beats file size: the default must stay 0, not PIL's own default.
        pil = Image.new("RGB", (4, 2))
        stream = io.BytesIO(b"png-bytes")
        stream.seek(4)  # so the rewind is observable

        with patch.object(
            image_pipeline, "get_pil_image_as_png_bytes", return_value=stream
        ) as mock_encode:
            result = encode_png_stream(pil)

        mock_encode.assert_called_once_with(pil, compress_level=0)
        assert result is stream
        assert result.tell() == 0

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
