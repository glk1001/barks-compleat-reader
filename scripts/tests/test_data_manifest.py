"""Tests for the data-pack manifest: its fingerprints, its cache, and the check."""

# cspell:ignore gregspc

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import data_manifest
import pytest
from barks_reader.core import config_info as config_info_module
from barks_reader.core.data_pack import DataPackInfo, pack_manifest_json
from data_manifest import (
    Fingerprint,
    compare,
    compare_pack,
    fingerprint,
    fingerprints,
    manifest_json,
)

if TYPE_CHECKING:
    from pathlib import Path


def _folder(root: Path, files: dict[str, bytes]) -> Path:
    for rel, content in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(content)
    return root


class TestFingerprint:
    def test_counts_and_sizes_the_files_under_a_folder(self, tmp_path: Path) -> None:
        root = _folder(tmp_path / "d", {"a.json": b"12345", "sub/b.json": b"678"})
        found = fingerprint(root, {})
        assert found is not None
        assert (found.files, found.bytes) == (2, 8)

    def test_a_single_file_is_its_own_entry(self, tmp_path: Path) -> None:
        zip_file = tmp_path / "Barks Panels.zip"
        zip_file.write_bytes(b"zip")
        found = fingerprint(zip_file, {})
        assert found is not None
        assert (found.files, found.bytes) == (1, 3)

    def test_a_missing_folder_has_none(self, tmp_path: Path) -> None:
        assert fingerprint(tmp_path / "gone", {}) is None

    def test_a_same_size_edit_changes_it(self, tmp_path: Path) -> None:
        """Size alone misses this: Vol. 26's 027.json changed at the same size (2026-10-19)."""
        root = _folder(tmp_path / "d", {"027.json": b"aaaa"})
        before = fingerprint(root, {})
        (root / "027.json").write_bytes(b"bbbb")
        assert fingerprint(root, {}) != before

    def test_an_added_removed_or_renamed_file_changes_it(self, tmp_path: Path) -> None:
        root = _folder(tmp_path / "d", {"a": b"x", "b": b"y"})
        before = fingerprint(root, {})
        (root / "c").write_bytes(b"z")
        assert fingerprint(root, {}) != before
        (root / "c").unlink()
        assert fingerprint(root, {}) == before
        (root / "b").rename(root / "b2")
        assert fingerprint(root, {}) != before

    def test_the_same_content_anywhere_has_the_same_fingerprint(self, tmp_path: Path) -> None:
        files = {"a": b"x", "sub/b": b"y"}
        here = fingerprint(_folder(tmp_path / "here", files), {})
        there = fingerprint(_folder(tmp_path / "there", files), {})
        assert here == there

    def test_what_a_desktop_leaves_is_not_data(self, tmp_path: Path) -> None:
        root = _folder(tmp_path / "d", {"a": b"x"})
        before = fingerprint(root, {})
        _folder(root, {".DS_Store": b"1", "Thumbs.db": b"2", "desktop.ini": b"3", "._a": b"4"})
        assert fingerprint(root, {}) == before


class TestCache:
    def test_an_unchanged_file_is_not_hashed_again(self, tmp_path: Path) -> None:
        root = _folder(tmp_path / "d", {"a": b"x"})
        cache: data_manifest.Cache = {}
        first = fingerprint(root, cache)
        cache[str(root / "a")][2] = "planted"  # same size and time: the cached md5 is used
        assert fingerprint(root, cache) != first

    def test_a_file_whose_time_moved_is_hashed_again(self, tmp_path: Path) -> None:
        root = _folder(tmp_path / "d", {"a": b"x"})
        cache: data_manifest.Cache = {}
        first = fingerprint(root, cache)
        cache[str(root / "a")][2] = "planted"
        stat = (root / "a").stat()
        os.utime(root / "a", ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        assert fingerprint(root, cache) == first


class TestCompare:
    @staticmethod
    def _manifest(entries: dict[str, Fingerprint | None]) -> dict:
        return json.loads(manifest_json(entries, "gregspc2", datetime(2026, 10, 19, tzinfo=UTC)))

    def test_matching_entries_have_no_differences(self) -> None:
        found = {"Indexes": Fingerprint(46, 100, "m"), "Statistics": None}
        assert compare(self._manifest(found), found) == []

    def test_each_kind_of_difference_is_named(self) -> None:
        manifest = self._manifest(
            {
                "Indexes": Fingerprint(46, 100, "new"),
                "Various": Fingerprint(1, 1, "v"),
                "Statistics": None,
            }
        )
        found = {
            "Indexes": Fingerprint(43, 90, "old"),
            "Various": None,
            "Statistics": Fingerprint(1, 2, "s"),
            "Extra": Fingerprint(1, 1, "e"),
        }
        lines = compare(manifest, found)
        assert lines == [
            "Extra: here, but not in the manifest",
            "Indexes: DIFFERS - here 43 files, 0.0 MB, expected 46 files, 0.0 MB",
            "Statistics: here (1 files, 0.0 MB), absent on gregspc2",
            "Various: MISSING here (expected 1 files, 0.0 MB)",
        ]

    def test_no_png_panels_here_is_no_difference(self) -> None:
        manifest = self._manifest({data_manifest.PNG_PANELS_ENTRY: Fingerprint(3675, 9, "p")})
        assert compare(manifest, {data_manifest.PNG_PANELS_ENTRY: None}) == []

    def test_png_panels_here_must_match(self) -> None:
        manifest = self._manifest({data_manifest.PNG_PANELS_ENTRY: Fingerprint(3675, 9, "p")})
        found: dict[str, Fingerprint | None] = {
            data_manifest.PNG_PANELS_ENTRY: Fingerprint(3600, 9, "q")
        }
        assert compare(manifest, found) == [
            "PNG panels: DIFFERS - here 3,600 files, 0.0 MB, expected 3,675 files, 0.0 MB"
        ]


class TestComparePack:
    """The Reader Files folders against the published pack's version file."""

    @staticmethod
    def _pack(entries: dict[str, dict]) -> DataPackInfo:
        return DataPackInfo(5, "data-v5", datetime(2026, 9, 29, tzinfo=UTC), "main-pc", entries)

    def test_a_pack_holding_this_data_is_no_difference(self) -> None:
        found: dict[str, Fingerprint | None] = {
            name: Fingerprint(1, 2, "m") for name in data_manifest.READER_FILES_ENTRIES
        }
        pack = self._pack({name: asdict(fp) for name, fp in found.items() if fp is not None})

        assert compare_pack(pack, found) == []

    def test_a_changed_missing_or_unpacked_entry_is_named(self) -> None:
        found: dict[str, Fingerprint | None] = {
            name: Fingerprint(1, 2, "m") for name in data_manifest.READER_FILES_ENTRIES
        }
        entries = {name: asdict(Fingerprint(1, 2, "m")) for name in found}
        entries["Indexes"]["md5"] = "rebuilt"
        del entries["Statistics"]
        found["Various"] = None

        assert compare_pack(self._pack(entries), found) == ["Indexes", "Statistics", "Various"]


class TestMain:
    @pytest.fixture
    def data(self, tmp_path: Path) -> Path:
        return _folder(tmp_path / "Indexes", {"MAIN.seg": b"segment", "volumes.json": b"{}"})

    def _main(self, tmp_path: Path, data: Path, *args: str) -> int:
        with (
            patch.object(data_manifest, "MANIFEST_PATH", tmp_path / "data-manifest.json"),
            patch.object(data_manifest, "CACHE_PATH", tmp_path / "build" / "cache.json"),
            patch.object(data_manifest, "REPO_ROOT", tmp_path),
            patch.object(data_manifest, "data_roots", return_value={"Indexes": data}),
        ):
            return data_manifest.main(list(args))

    def test_a_written_manifest_then_matches(self, tmp_path: Path, data: Path) -> None:
        assert self._main(tmp_path, data, "--write") == 0
        assert self._main(tmp_path, data) == 0

    def test_a_folder_changed_since_warns_and_says_which(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._main(tmp_path, data, "--write")
        (data / "MAIN.seg").write_bytes(b"rebuilt")
        assert self._main(tmp_path, data) == data_manifest.DIFFER_EXIT
        assert "Indexes: DIFFERS" in capsys.readouterr().out

    def test_no_manifest_is_an_error(self, tmp_path: Path, data: Path) -> None:
        assert self._main(tmp_path, data) == 1

    def test_unreadable_settings_are_an_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(data_manifest, "data_roots", side_effect=RuntimeError("no config")):
            assert data_manifest.main([]) == 1
        assert "cannot read this machine's settings: no config" in capsys.readouterr().out

    def test_the_cache_is_kept_for_the_next_run(self, tmp_path: Path, data: Path) -> None:
        self._main(tmp_path, data, "--write")
        cached = json.loads((tmp_path / "build" / "cache.json").read_text(encoding="utf-8"))
        assert str(data / "MAIN.seg") in cached

    def _write_pack_record(self, tmp_path: Path, data: Path, *, indexes_changed: bool) -> Path:
        found = fingerprint(data, {})
        assert found is not None
        entries = {
            name: {"files": 0, "bytes": 0, "md5": "-"}
            for name in data_manifest.READER_FILES_ENTRIES
        }
        entries["Indexes"] = asdict(found)
        if indexes_changed:
            entries["Indexes"]["md5"] = "changed"
        record = tmp_path / "data-pack-manifest.json"
        record.write_text(
            pack_manifest_json(5, "data-v5", datetime(2026, 9, 29, tzinfo=UTC), "main-pc", entries),
            encoding="utf-8",
        )
        return record

    def _main_with_pack(self, tmp_path: Path, data: Path, record: Path, *args: str) -> int:
        with patch.object(data_manifest, "PACK_MANIFEST_PATH", record):
            return self._main(tmp_path, data, *args)

    def test_pack_names_the_folders_changed_since_the_published_pack(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        record = self._write_pack_record(tmp_path, data, indexes_changed=True)

        assert self._main_with_pack(tmp_path, data, record, "--pack") == data_manifest.DIFFER_EXIT

        out = capsys.readouterr().out
        assert "the published data pack data-v5 (built 2026-09-29) is behind this PC:" in out
        assert "Indexes" in out
        assert "a new data pack is due" in out

    def test_pack_without_a_published_record_is_an_error(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        record = tmp_path / "data-pack-manifest.json"

        assert self._main_with_pack(tmp_path, data, record, "--pack") == 1
        assert "no versioned data pack is published yet" in capsys.readouterr().out

    def test_on_the_main_pc_the_plain_check_also_holds_the_data_to_the_pack(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._main(tmp_path, data, "--write")
        record = self._write_pack_record(tmp_path, data, indexes_changed=True)

        with patch.object(data_manifest.platform, "node", return_value=platform.node()):
            status = self._main_with_pack(tmp_path, data, record)

        assert status == data_manifest.DIFFER_EXIT
        out = capsys.readouterr().out
        assert "every folder matches the manifest" in out
        assert "the published data pack data-v5 (built 2026-09-29) is behind this PC:" in out
        assert "Indexes" in out

    def test_on_the_main_pc_no_published_record_is_only_a_note(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._main(tmp_path, data, "--write")

        status = self._main_with_pack(tmp_path, data, tmp_path / "data-pack-manifest.json")

        assert status == 0
        assert "no versioned data pack is published yet" in capsys.readouterr().out

    def test_elsewhere_the_plain_check_leaves_the_pack_alone(
        self, tmp_path: Path, data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._main(tmp_path, data, "--write")
        record = self._write_pack_record(tmp_path, data, indexes_changed=True)

        with patch.object(data_manifest.platform, "node", return_value="another-pc"):
            status = self._main_with_pack(tmp_path, data, record)

        assert status == 0
        assert "data pack" not in capsys.readouterr().out


class TestDataRoots:
    def test_folders_come_from_the_data_dir_and_the_ini(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text(
            "[Barks Reader]\n"
            f"prebuilt_dir = {tmp_path / 'The Comics' / 'Chronological'}\n"
            f"png_barks_panels_dir = {tmp_path / 'Barks Panels Pngs'}\n",
            encoding="utf-8",
        )
        cfg = SimpleNamespace(app_data_dir=tmp_path / "data", app_config_path=ini)
        with patch.object(config_info_module, "ConfigInfo", return_value=cfg):
            roots = data_manifest.data_roots()
        assert roots["Indexes"] == tmp_path / "data" / "Reader Files" / "Indexes"
        assert roots["Barks Panels.zip"] == tmp_path / "data" / "Reader Files" / "Barks Panels.zip"
        assert roots[data_manifest.PREBUILT_ENTRY] == tmp_path / "The Comics" / "Chronological"
        assert roots[data_manifest.PNG_PANELS_ENTRY] == tmp_path / "Barks Panels Pngs"

    def test_an_ini_without_the_png_panels_has_none(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text("[Barks Reader]\n", encoding="utf-8")
        cfg = SimpleNamespace(app_data_dir=tmp_path, app_config_path=ini)
        with patch.object(config_info_module, "ConfigInfo", return_value=cfg):
            roots = data_manifest.data_roots()
        assert roots[data_manifest.PNG_PANELS_ENTRY] is None
        assert roots[data_manifest.PREBUILT_ENTRY] is not None  # the app's default

    def test_every_entry_is_fingerprinted_even_when_absent(self, tmp_path: Path) -> None:
        found = fingerprints({"Indexes": tmp_path / "none", "PNG panels": None}, {})
        assert found == {"Indexes": None, "PNG panels": None}


class TestPackManifest:
    """The version file the data packs carry."""

    @pytest.fixture
    def reader_files(self, tmp_path: Path) -> Path:
        root = tmp_path / "Reader Files"
        for name in data_manifest.READER_FILES_ENTRIES:
            if name.endswith(".zip"):
                root.mkdir(exist_ok=True)
                (root / name).write_bytes(b"zip")
            else:
                _folder(root / name, {"a.json": b"{}"})
        return root

    def _main(self, tmp_path: Path, *args: str) -> int:
        with patch.object(data_manifest, "CACHE_PATH", tmp_path / "build" / "cache.json"):
            return data_manifest.main(list(args))

    def test_lists_the_entries_the_build_packs(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert data_manifest.main(["--list-entries"]) == 0
        assert capsys.readouterr().out.splitlines() == list(data_manifest.READER_FILES_ENTRIES)

    def test_writes_the_version_and_every_fingerprint(
        self, tmp_path: Path, reader_files: Path
    ) -> None:
        out = tmp_path / "stage" / "Reader Files" / "data-pack.json"
        with patch.object(data_manifest.platform, "node", return_value="main-pc"):
            status = self._main(
                tmp_path,
                "--write-pack-manifest",
                str(out),
                "--version",
                "7",
                "--reader-files",
                str(reader_files),
            )

        assert status == 0
        info = DataPackInfo.from_json(out.read_text(encoding="utf-8"))
        assert (info.version, info.tag, info.built_on) == (7, "data-v7", "main-pc")
        assert set(info.entries) == set(data_manifest.READER_FILES_ENTRIES)
        panels = fingerprint(reader_files / "Barks Panels.zip", {})
        assert panels is not None
        assert info.entries["Barks Panels.zip"] == asdict(panels)

    def test_a_missing_entry_writes_nothing(
        self, tmp_path: Path, reader_files: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (reader_files / "Barks Panels.zip").unlink()
        out = tmp_path / "data-pack.json"

        status = self._main(
            tmp_path,
            "--write-pack-manifest",
            str(out),
            "--version",
            "7",
            "--reader-files",
            str(reader_files),
        )

        assert status == 1
        assert not out.exists()
        assert "not under" in capsys.readouterr().out

    def test_the_version_and_the_folder_are_both_needed(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            self._main(tmp_path, "--write-pack-manifest", str(tmp_path / "x.json"))
