"""Shared image-loading pipeline primitives.

Provides the single set of building blocks used by every place that needs to
turn a path (filesystem ``Path`` or ``zipfile.Path``) into a display-ready
image: panel previews, index thumbnails, and full comic pages. Each stage is
a pure function, so pipelines can be composed freely and exercised
end-to-end with real ZIP fixtures.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from comic_utils.pil_image_utils import (
    get_pil_image_as_png_bytes,
    load_pil_image_from_bytes,
    load_pil_image_from_zip,
)
from PIL import Image as PilImage
from PIL import ImageOps

if TYPE_CHECKING:
    from comic_utils.comic_consts import PanelPath
    from PIL.Image import Image


def read_raw_bytes(panel_path: PanelPath) -> bytes:
    """Read raw image bytes from either a filesystem ``Path`` or a ``zipfile.Path``.

    This reads bytes verbatim and never decrypts. Decryption of encrypted zip
    members must go through :func:`load_pil` (``encrypted_zip=True``), which
    delegates to ``comic_utils.pil_image_utils.load_pil_image_from_zip`` — the
    canonical entry point the compiled panel-key module's caller allow-list
    permits. This module is *not* on that allow-list, so it must never call the
    decryptor directly.

    Args:
        panel_path: Source path.

    Returns:
        Raw file bytes.

    Raises:
        TypeError: If *panel_path* is neither ``Path`` nor ``zipfile.Path``.

    """
    if isinstance(panel_path, zipfile.Path):
        return panel_path.read_bytes()

    if isinstance(panel_path, Path):
        return panel_path.read_bytes()

    msg = f"Unsupported PanelPath type: {type(panel_path)}"
    raise TypeError(msg)


def decode_pil(raw: bytes, *, ext: str | None = None) -> Image:
    """Decode raw bytes to a fully-loaded PIL image.

    Args:
        raw: Raw image bytes.
        ext: Optional extension hint (e.g. ``".png"``). When provided, PIL is
            restricted to the matching format (enforced by
            ``load_pil_image_from_bytes``). When ``None``, PIL auto-detects
            the format.

    Returns:
        A PIL image with pixel data loaded into memory.

    """
    if ext is not None:
        return load_pil_image_from_bytes(raw, ext)
    image = PilImage.open(io.BytesIO(raw))
    image.load()
    return image


def load_pil(
    panel_path: PanelPath,
    *,
    encrypted_zip: bool = False,
    use_ext_hint: bool = False,
) -> Image:
    """Read-and-decode shortcut: ``panel_path → PIL image``.

    Args:
        panel_path: Source path.
        encrypted_zip: When ``True`` and *panel_path* is a ``zipfile.Path``,
            decrypt via the allow-listed ``load_pil_image_from_zip``. Ignored
            for filesystem paths.
        use_ext_hint: When ``True``, pass the path's suffix to
            :func:`decode_pil` so PIL validates the format. (The encrypted-zip
            path always validates by extension.)

    Returns:
        A loaded PIL image.

    """
    if encrypted_zip and isinstance(panel_path, zipfile.Path):
        # Decryption must run inside comic_utils.pil_image_utils: the compiled
        # panel-key module restricts the decryptor to an allow-list of caller
        # modules that does NOT include this one. load_pil_image_from_zip is the
        # canonical allow-listed entry point (read + decrypt + decode-with-ext).
        return load_pil_image_from_zip(panel_path, encrypted=True)

    raw = read_raw_bytes(panel_path)
    ext = panel_path.suffix if use_ext_hint else None
    return decode_pil(raw, ext=ext)


def convert_mode(pil_image: Image, mode: str) -> Image:
    """Return *pil_image* converted to the given PIL mode (e.g. ``"RGBA"``)."""
    return pil_image.convert(mode)


def resize_contain(pil_image: Image, max_width: int, max_height: int) -> Image:
    """Shrink *pil_image* to fit within ``(max_width, max_height)`` using LANCZOS."""
    return ImageOps.contain(
        pil_image,
        (max_width, max_height),
        PilImage.Resampling.LANCZOS,
    )


def encode_png_stream(pil_image: Image, *, compress_level: int = 0) -> io.BytesIO:
    """Encode *pil_image* as PNG bytes in an ``io.BytesIO`` positioned at 0."""
    stream = get_pil_image_as_png_bytes(pil_image, compress_level=compress_level)
    stream.seek(0)
    return stream
