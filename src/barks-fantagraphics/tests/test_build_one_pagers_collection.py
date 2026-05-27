"""Tests for the All One-Pagers collection assembly script.

The script (``scripts/build-one-pagers-collection.py``) is environment-dependent
(real archives + the Fernet panel key), so here we lock its two pure pieces of
logic: the page *numbering* (``_build_collection_entries``) and the *idempotent*
override rebuild (``_rewrite_override_archive``). The filesystem is faked via
``tmp_path`` and a generated Fernet key, so nothing real is read or written.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics import comic_book_info as cbi
from barks_fantagraphics.barks_titles import Titles
from cryptography.fernet import Fernet

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
_SCRIPT_PATH = _SCRIPTS_DIR / "build-one-pagers-collection.py"


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the (hyphenated, non-importable) assembly script as a module.

    The module builds a ``Fernet`` and imports ``cli_setup`` at import time, so we
    provide a generated key and put ``scripts/`` on the path first.
    """
    monkeypatch.setenv("BARKS_ZIPS_KEY", Fernet.generate_key().decode())
    monkeypatch.syspath_prepend(str(_SCRIPTS_DIR))

    spec = importlib.util.spec_from_file_location("build_one_pagers_collection", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRewriteOverrideArchiveIdempotency:
    def test_preserves_fixes_drops_stale_collection_pages_no_dupes(
        self, script: ModuleType, tmp_path: Path
    ) -> None:
        base = script.ONE_PAGER_COLLECTION_PAGE_BASE
        override = tmp_path / "06 - Some Volume.cbz"

        # Seed with a real volume fix and a STALE collection page (>= base).
        with zipfile.ZipFile(override, "w") as zf:
            zf.writestr("234.png", b"FIX_BYTES")
            zf.writestr(f"{base:03d}.png", b"STALE_COLLECTION_BYTES")

        # New collection entries (one page) to write.
        entries = [(f"{base:03d}.png", b"NEW_ENCRYPTED_BYTES", tmp_path / f"{base}.json")]

        script._rewrite_override_archive(override, entries)  # noqa: SLF001

        with zipfile.ZipFile(override, "r") as zf:
            names = zf.namelist()
            # The volume fix is preserved verbatim (copied raw, not decrypted).
            assert zf.read("234.png") == b"FIX_BYTES"
            # The stale collection page was dropped and replaced by the new one.
            assert zf.read(f"{base:03d}.png") == b"NEW_ENCRYPTED_BYTES"
            # No duplicate entries (idempotent rebuild).
            assert sorted(names) == sorted(["234.png", f"{base:03d}.png"])

    def test_creates_archive_when_absent(self, script: ModuleType, tmp_path: Path) -> None:
        base = script.ONE_PAGER_COLLECTION_PAGE_BASE
        override = tmp_path / "missing.cbz"
        entries = [(f"{base:03d}.png", b"ENC", tmp_path / f"{base}.json")]

        script._rewrite_override_archive(override, entries)  # noqa: SLF001

        assert override.is_file()
        with zipfile.ZipFile(override, "r") as zf:
            assert zf.namelist() == [f"{base:03d}.png"]


class TestBuildCollectionEntriesNumbering:
    def test_entries_are_sequential_in_located_order(
        self, script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        base = script.ONE_PAGER_COLLECTION_PAGE_BASE

        # Two located one-pagers (chronological ONE_PAGERS order: IF_THE_HAT_FITS first).
        fake_locations = {
            Titles.IF_THE_HAT_FITS: (5, 123, 0),
            Titles.FASHION_IN_FLIGHT: (6, 45, 0),
        }
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", fake_locations)
        monkeypatch.setattr(script, "ONE_PAGER_LOCATIONS", fake_locations)

        # Redirect the reader panel-segments root into tmp_path.
        segments_root = tmp_path / "segments"
        monkeypatch.setattr(script, "FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT", segments_root)

        restored_root = tmp_path / "restored"

        db = MagicMock()
        db.get_fantagraphics_restored_volume_image_dir.side_effect = lambda v: (
            restored_root / str(v)
        )
        db.get_fantagraphics_volume_title.side_effect = lambda v: f"Vol{v}"

        # Create the source image + segment files the script reads.
        for vol, page in ((5, 123), (6, 45)):
            img_dir = restored_root / str(vol)
            img_dir.mkdir(parents=True, exist_ok=True)
            (img_dir / f"{page:03d}.png").write_bytes(b"IMG")
            seg_dir = segments_root / f"Vol{vol}"
            seg_dir.mkdir(parents=True, exist_ok=True)
            (seg_dir / f"{page:03d}.json").write_text("{}")

        entries = script._build_collection_entries(db)  # noqa: SLF001

        # Arcnames are sequential from the base, in located (chronological) order.
        assert [arcname for arcname, _enc, _seg in entries] == [
            f"{base:03d}.png",
            f"{base + 1:03d}.png",
        ]
        # Dest segments are written into the collection's nominal volume (Vol1).
        assert [seg for _arcname, _enc, seg in entries] == [
            segments_root / "Vol1" / f"{base:03d}.json",
            segments_root / "Vol1" / f"{base + 1:03d}.json",
        ]
        # Each image was encrypted (non-empty bytes, not the plaintext).
        for _arcname, encrypted, _seg in entries:
            assert encrypted
            assert encrypted != b"IMG"

    def test_missing_source_image_raises(
        self, script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (5, 123, 0)})
        monkeypatch.setattr(script, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (5, 123, 0)})
        monkeypatch.setattr(
            script, "FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT", tmp_path / "segments"
        )

        db = MagicMock()
        db.get_fantagraphics_restored_volume_image_dir.side_effect = lambda v: tmp_path / str(v)
        db.get_fantagraphics_volume_title.side_effect = lambda v: f"Vol{v}"

        with pytest.raises(FileNotFoundError):
            script._build_collection_entries(db)  # noqa: SLF001
