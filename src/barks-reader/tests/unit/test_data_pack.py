"""The data pack version file, the search for newer packs, and the folder swap."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
from barks_reader.core import data_pack
from barks_reader.core.data_pack import (
    DATA_PACK_DIR_ENV_VAR,
    DATA_PACK_FILE_NAME,
    DATA_PACK_FILE_NAMES,
    PACK_MEMBER,
    DataPackInfo,
    PackUnreadableError,
    ReaderFilesStrandedError,
    UpdateStatus,
    find_update,
    installed_version_text,
    look_for_update,
    pack_dir_for_update,
    read_from_pack,
    read_installed,
    swap_reader_files,
    verify_extracted,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_BUILT = datetime(2026, 10, 29, 6, 30, tzinfo=UTC)
_FIELDS = '{"version": 6, "tag": "t", "built_at": "2026-10-29", "built_on": "h", "entries": {}}'


def _info(version: int = 6, entries: dict | None = None) -> DataPackInfo:
    if entries is None:
        entries = {"Indexes": {"files": 2, "bytes": 10, "md5": "x"}}
    return DataPackInfo(version, f"data-v{version}", _BUILT, "main-pc", entries)


def _write_pack(path: Path, info: DataPackInfo | None, extra: dict[str, str] | None = None) -> Path:
    with ZipFile(path, "w") as pack:
        if info is not None:
            pack.writestr(PACK_MEMBER, info.to_json())
        for name, text in (extra or {}).items():
            pack.writestr(name, text)
    return path


def _write_packs(pack_dir: Path, *infos: DataPackInfo | None) -> None:
    pack_dir.mkdir(exist_ok=True)
    for name, info in zip(DATA_PACK_FILE_NAMES, infos, strict=True):
        _write_pack(pack_dir / name, info)


class TestDataPackInfo:
    def test_round_trips_through_json(self) -> None:
        info = _info()

        assert DataPackInfo.from_json(info.to_json()) == info

    def test_the_json_is_sorted_with_a_trailing_newline(self) -> None:
        text = _info().to_json()

        assert text.startswith('{\n  "built_at": "2026-10-29T06:30:00+00:00",')
        assert text.endswith("}\n")

    @pytest.mark.parametrize(
        "text",
        [
            "not json",
            '{"version": 6}',
            _FIELDS.replace('"version": 6', '"version": "6"'),
            _FIELDS.replace('"version": 6', '"version": true'),
            _FIELDS.replace("2026-10-29", "yesterday"),
        ],
    )
    def test_a_file_of_another_shape_is_rejected(self, text: str) -> None:
        with pytest.raises(ValueError, match="not a data pack version file"):
            DataPackInfo.from_json(text)

    def test_displays_as_the_about_box_names_it(self) -> None:
        assert _info().display() == "Data pack 6 (29 Oct 2026)"
        assert _info().short() == "data pack 6"
        assert installed_version_text(_info()) == "Data pack 6 (29 Oct 2026)"
        assert installed_version_text(None) == "Data pack: not versioned"


class TestReading:
    def test_reads_the_installed_version_file(self, tmp_path: Path) -> None:
        (tmp_path / DATA_PACK_FILE_NAME).write_text(_info().to_json())

        assert read_installed(tmp_path) == _info()

    def test_a_folder_without_one_is_unversioned(self, tmp_path: Path) -> None:
        assert read_installed(tmp_path) is None
        assert read_installed(tmp_path / "nowhere") is None

    def test_a_broken_one_is_unversioned_and_logged(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        (tmp_path / DATA_PACK_FILE_NAME).write_text("{}")

        assert read_installed(tmp_path) is None
        assert any("Ignoring the data pack version file" in line for line in loguru_sink)

    def test_reads_a_pack_without_extracting_it(self, tmp_path: Path) -> None:
        pack = _write_pack(tmp_path / "p.barkspack", _info(), {"Reader Files/a.txt": "a"})

        assert read_from_pack(pack) == _info()

    def test_a_pack_without_the_file_is_unversioned(self, tmp_path: Path) -> None:
        assert read_from_pack(_write_pack(tmp_path / "old.barkspack", None)) is None

    def test_a_pack_that_cannot_be_read_is_not_mistaken_for_an_old_one(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "junk.barkspack").write_text("not a zip")
        with pytest.raises(PackUnreadableError, match=r'junk\.barkspack" could not be read: File'):
            read_from_pack(tmp_path / "junk.barkspack")
        with pytest.raises(PackUnreadableError, match="absent"):
            read_from_pack(tmp_path / "absent.barkspack")

        good = _write_pack(tmp_path / "good.barkspack", _info())
        truncated = tmp_path / "truncated.barkspack"
        truncated.write_bytes(good.read_bytes()[: good.stat().st_size // 2])
        with pytest.raises(PackUnreadableError, match="truncated"):
            read_from_pack(truncated)

        with ZipFile(tmp_path / "broken.barkspack", "w") as pack:
            pack.writestr(PACK_MEMBER, "{}")
        with pytest.raises(PackUnreadableError, match="not a data pack version file"):
            read_from_pack(tmp_path / "broken.barkspack")


class TestPackDir:
    def test_the_env_var_wins_everywhere(self, tmp_path: Path) -> None:
        env = {DATA_PACK_DIR_ENV_VAR: str(tmp_path)}

        assert pack_dir_for_update(Path("/exe"), is_compiled=True, env=env) == tmp_path
        assert pack_dir_for_update(Path("/exe"), is_compiled=False, env=env) == tmp_path

    def test_a_standalone_build_looks_beside_the_executable(self) -> None:
        assert pack_dir_for_update(Path("/exe"), is_compiled=True, env={}) == Path("/exe")

    def test_the_reader_and_the_installer_share_one_lookup(self, tmp_path: Path) -> None:
        _write_packs(tmp_path / "exe", _info(6), _info(6))
        installed = tmp_path / "Reader Files"
        installed.mkdir()
        (installed / DATA_PACK_FILE_NAME).write_text(_info(5).to_json())

        check = look_for_update(tmp_path / "exe", installed, is_compiled=True, env={})

        assert check.status is UpdateStatus.UPDATE_AVAILABLE
        assert check.installed == _info(5)
        assert check.available == _info(6)
        assert (
            look_for_update(tmp_path / "exe", installed, is_compiled=False, env={}).status
            is UpdateStatus.NO_PACK_DIR
        )

    def test_a_development_run_looks_nowhere(self) -> None:
        assert pack_dir_for_update(Path("/exe"), is_compiled=False, env={}) is None
        assert (
            pack_dir_for_update(Path("/exe"), is_compiled=False, env={DATA_PACK_DIR_ENV_VAR: ""})
            is None
        )


class TestFindUpdate:
    def test_newer_packs_are_an_update(self, tmp_path: Path) -> None:
        _write_packs(tmp_path, _info(6), _info(6))

        check = find_update(tmp_path, _info(5))

        assert check.status is UpdateStatus.UPDATE_AVAILABLE
        assert check.available == _info(6)
        assert check.offer_message() == (
            "Data pack 6 (29 Oct 2026) is beside the Barks Reader. Install it now?"
            " The reader will close, install it, and start again."
        )

    def test_an_unversioned_install_takes_any_versioned_pack(self, tmp_path: Path) -> None:
        _write_packs(tmp_path, _info(1), _info(1))

        assert find_update(tmp_path, None).status is UpdateStatus.UPDATE_AVAILABLE

    def test_nowhere_to_look(self) -> None:
        check = find_update(None, _info(5))

        assert check.status is UpdateStatus.NO_PACK_DIR
        assert check.available is None
        assert DATA_PACK_DIR_ENV_VAR in check.no_update_message()

    def test_a_missing_pack(self, tmp_path: Path) -> None:
        tmp_path.joinpath(DATA_PACK_FILE_NAMES[0]).write_bytes(b"")

        check = find_update(tmp_path, _info(5))

        assert check.status is UpdateStatus.PACKS_MISSING
        assert check.missing == (DATA_PACK_FILE_NAMES[1],)
        assert check.no_update_message() == (
            "No newer data pack beside the Barks Reader (installed: data pack 5;"
            f' looked in "{tmp_path}" and did not find "{DATA_PACK_FILE_NAMES[1]}").'
        )

    def test_both_missing_and_an_unversioned_install(self, tmp_path: Path) -> None:
        check = find_update(tmp_path, None)

        assert check.status is UpdateStatus.PACKS_MISSING
        assert "installed: an unversioned data pack" in check.no_update_message()
        assert '"barks-reader-data-1.barkspack" and "barks-reader-data-2.barkspack"' in (
            check.no_update_message()
        )

    def test_packs_from_before_the_version_file(self, tmp_path: Path) -> None:
        _write_packs(tmp_path, None, _info(6))

        check = find_update(tmp_path, None)

        assert check.status is UpdateStatus.PACKS_NOT_VERSIONED
        assert check.missing == (DATA_PACK_FILE_NAMES[0],)
        assert "carry no version" in check.no_update_message()

    def test_a_pack_that_cannot_be_read_says_so_not_that_it_is_old(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        _write_packs(tmp_path, _info(6), _info(6))
        pack = tmp_path / DATA_PACK_FILE_NAMES[1]
        pack.write_bytes(pack.read_bytes()[:100])

        check = find_update(tmp_path, _info(5))

        assert check.status is UpdateStatus.PACK_UNREADABLE
        assert check.missing == (DATA_PACK_FILE_NAMES[1],)
        assert check.available is None
        message = check.no_update_message()
        assert message.startswith(
            f'The data pack "{DATA_PACK_FILE_NAMES[1]}" in "{tmp_path}" could not be read ('
        )
        assert "SHA256SUMS.txt" in message
        assert "carry no version" not in message
        assert any("could not be read" in line for line in loguru_sink)

    def test_packs_of_different_versions(self, tmp_path: Path) -> None:
        _write_packs(tmp_path, _info(6), _info(7))

        check = find_update(tmp_path, _info(5))

        assert check.status is UpdateStatus.PACKS_DISAGREE
        assert "(data pack 6 and data pack 7)" in check.no_update_message()

    @pytest.mark.parametrize("installed", [5, 6])
    def test_packs_no_newer_than_the_install(self, tmp_path: Path, installed: int) -> None:
        _write_packs(tmp_path, _info(5), _info(5))

        check = find_update(tmp_path, _info(installed))

        assert check.status is UpdateStatus.NOT_NEWER
        assert check.no_update_message() == (
            f'No newer data pack beside the Barks Reader: the packs in "{tmp_path}" are'
            f" data pack 5, and data pack {installed} is installed."
        )


class TestVerifyExtracted:
    def test_a_matching_folder_has_no_problems(self, tmp_path: Path) -> None:
        info = _info(
            entries={
                "Indexes": {"files": 1, "bytes": 1, "md5": "x"},
                "Barks Panels.zip": {"files": 1, "bytes": 3, "md5": "y"},
            }
        )
        (tmp_path / DATA_PACK_FILE_NAME).write_text(info.to_json())
        (tmp_path / "Indexes").mkdir()
        (tmp_path / "Barks Panels.zip").write_bytes(b"abc")

        assert verify_extracted(tmp_path, info) == []

    def test_each_problem_is_named(self, tmp_path: Path) -> None:
        info = _info(
            entries={
                "Indexes": {"files": 1, "bytes": 1, "md5": "x"},
                "Barks Panels.zip": {"files": 1, "bytes": 3, "md5": "y"},
            }
        )
        (tmp_path / DATA_PACK_FILE_NAME).write_text(_info(5).to_json())
        (tmp_path / "Barks Panels.zip").write_bytes(b"ab")

        assert verify_extracted(tmp_path, info) == [
            'the extracted "data-pack.json" is data pack 5, not 6',
            '"Indexes" was not extracted',
            '"Barks Panels.zip" is 2 bytes, not the 3 the pack says',
        ]

    def test_a_missing_version_file_is_a_problem(self, tmp_path: Path) -> None:
        assert verify_extracted(tmp_path, _info(entries={})) == [
            'no "data-pack.json" was extracted'
        ]


@pytest.fixture
def reader_files(tmp_path: Path) -> Path:
    installed = tmp_path / "Reader Files"
    installed.mkdir()
    (installed / "old.txt").write_text("old")
    new = tmp_path / "Reader Files.new"
    new.mkdir()
    (new / "new.txt").write_text("new")
    return installed


class TestSwap:
    def test_the_new_folder_takes_the_installed_folders_place(self, reader_files: Path) -> None:
        old = swap_reader_files(reader_files, sleep=lambda _s: None)

        assert old == reader_files.with_name("Reader Files.old")
        assert (reader_files / "new.txt").read_text() == "new"
        assert (reader_files.with_name("Reader Files.old") / "old.txt").read_text() == "old"
        assert not reader_files.with_name("Reader Files.new").exists()

    def test_without_an_installed_folder_nothing_is_moved_aside(self, tmp_path: Path) -> None:
        new = tmp_path / "Reader Files.new"
        new.mkdir()
        reader_files = tmp_path / "Reader Files"

        assert swap_reader_files(reader_files, sleep=lambda _s: None) is None
        assert reader_files.is_dir()
        assert not reader_files.with_name("Reader Files.old").exists()

    def test_a_rename_blocked_for_a_while_is_retried(
        self, reader_files: Path, loguru_sink: list[str]
    ) -> None:
        failures = iter([True, True, False])
        waits: list[float] = []

        def rename(source: Path, target: Path) -> None:
            if next(failures, False):
                raise PermissionError(13, "in use")
            source.rename(target)

        old = swap_reader_files(
            reader_files, attempts=5, delay=0.5, sleep=waits.append, rename=rename
        )

        assert old is not None
        assert waits == [0.5, 0.5]
        assert (reader_files / "new.txt").exists()
        assert sum("try 1 of 5" in line for line in loguru_sink) == 1

    def test_a_rename_blocked_for_good_gives_up_with_the_folders_as_they_were(
        self, reader_files: Path
    ) -> None:
        def rename(source: Path, target: Path) -> None:
            if source.name.endswith(".new"):
                raise PermissionError(13, "in use")
            source.rename(target)

        with pytest.raises(PermissionError):
            swap_reader_files(reader_files, attempts=2, sleep=lambda _s: None, rename=rename)

        assert (reader_files / "old.txt").read_text() == "old"
        assert (reader_files.with_name("Reader Files.new") / "new.txt").exists()
        assert not reader_files.with_name("Reader Files.old").exists()

    def test_the_put_back_is_retried_too(self, reader_files: Path, loguru_sink: list[str]) -> None:
        # The .new rename fails for good; the put-back fails once, then goes through.
        put_back_failures = iter([True, False])

        def rename(source: Path, target: Path) -> None:
            if source.name.endswith(".new"):
                raise OSError(5, "sharing violation")
            if source.name.endswith(".old") and next(put_back_failures, False):
                raise OSError(5, "sharing violation")
            source.rename(target)

        with pytest.raises(OSError, match="sharing violation"):
            swap_reader_files(reader_files, attempts=2, sleep=lambda _s: None, rename=rename)

        assert (reader_files / "old.txt").read_text() == "old"
        assert not reader_files.with_name("Reader Files.old").exists()
        retried = [line for line in loguru_sink if "try 1 of 2" in line]
        assert len(retried) == len([".new", ".old"])
        assert 'Renaming "' + str(reader_files.with_name("Reader Files.new")) in retried[0]
        assert 'Renaming "' + str(reader_files.with_name("Reader Files.old")) in retried[1]

    def test_a_put_back_that_fails_for_good_names_where_the_data_is(
        self, reader_files: Path
    ) -> None:
        def rename(source: Path, target: Path) -> None:
            if target == reader_files:
                raise PermissionError(13, "in use")
            source.rename(target)

        old = reader_files.with_name("Reader Files.old")
        with pytest.raises(ReaderFilesStrandedError) as info:
            swap_reader_files(reader_files, attempts=2, sleep=lambda _s: None, rename=rename)

        assert info.value.old_dir == old
        assert info.value.reader_files_dir == reader_files
        assert isinstance(info.value.__cause__, PermissionError)
        assert f'Putting "{old}" back as "{reader_files}" failed' in str(info.value)
        assert not reader_files.exists()
        assert (old / "old.txt").read_text() == "old"

    def test_leftovers_of_an_interrupted_update_are_removed(self, reader_files: Path) -> None:
        old = reader_files.with_name("Reader Files.old")
        old.mkdir()

        data_pack.clear_leftovers(reader_files)

        assert not old.exists()
        assert not reader_files.with_name("Reader Files.new").exists()
        assert (reader_files / "old.txt").exists()

    def test_a_stranded_old_folder_is_put_back_not_removed(
        self, reader_files: Path, loguru_sink: list[str]
    ) -> None:
        old = reader_files.with_name("Reader Files.old")
        reader_files.rename(old)

        data_pack.clear_leftovers(reader_files)

        assert (reader_files / "old.txt").read_text() == "old"
        assert not old.exists()
        assert not reader_files.with_name("Reader Files.new").exists()
        assert any(f'Putting the leftover "{old}" back' in line for line in loguru_sink)


class TestSpawnDetached:
    @pytest.fixture
    def popen(self) -> Iterator[MagicMock]:
        with patch.object(data_pack.subprocess, "Popen") as popen:
            yield popen

    def test_starts_the_command_in_its_own_session(
        self, popen: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(data_pack, "PLATFORM", data_pack.Platform.LINUX)

        data_pack.spawn_detached(["/exe/reader", "--install-data-pack"])

        popen.assert_called_once_with(
            ["/exe/reader", "--install-data-pack"], start_new_session=True, close_fds=True
        )

    def test_on_windows_it_is_a_detached_process_group(
        self, popen: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(data_pack, "PLATFORM", data_pack.Platform.WIN)
        monkeypatch.setattr(data_pack.subprocess, "DETACHED_PROCESS", 8, raising=False)
        monkeypatch.setattr(data_pack.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)

        data_pack.spawn_detached(["reader.exe"])

        popen.assert_called_once_with(["reader.exe"], creationflags=8 | 512, close_fds=True)
