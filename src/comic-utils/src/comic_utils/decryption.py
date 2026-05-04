"""Shared exception type for panel-bytes decryption failures.

The compiled :func:`comic_utils.get_panel_bytes.get_decrypted_bytes`
returns ``b""`` on any failure (wrong key, unauthorised caller, malformed
input). Callers wrap that empty-bytes sentinel and raise
:class:`DecryptionError` so failure has a single, catchable type instead
of surfacing as ``UnidentifiedImageError`` further down the pipeline.
"""

from __future__ import annotations


class DecryptionError(RuntimeError):
    """Raised when panel-bytes decryption returns no data."""
