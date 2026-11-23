"""Where the folder chooser's Left key goes (``core.folder_chooser``)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest
from barks_reader.core import folder_chooser
from barks_reader.core.folder_chooser import drives, folders_left_of

_C, _D, _E = PureWindowsPath("C:/"), PureWindowsPath("D:/"), PureWindowsPath("E:/")


class TestFoldersLeftOf:
    def test_a_folder_s_parent_and_nothing_else(self) -> None:
        assert folders_left_of(PureWindowsPath("C:/Comics/Barks"), [_C, _D]) == [
            PureWindowsPath("C:/Comics")
        ]

    def test_a_folder_under_a_drive_s_top_goes_to_the_top_not_the_next_drive(self) -> None:
        assert folders_left_of(PureWindowsPath("C:/Comics"), [_C, _D]) == [_C]

    @pytest.mark.parametrize(
        ("at", "in_turn"),
        [(_C, [_D, _E]), (_D, [_E, _C]), (_E, [_C, _D])],
    )
    def test_a_drive_s_top_goes_to_the_other_drives_in_turn_and_round(
        self, at: PureWindowsPath, in_turn: list[PureWindowsPath]
    ) -> None:
        assert folders_left_of(at, [_C, _D, _E]) == in_turn

    def test_a_drive_is_known_whatever_the_case_of_its_letter(self) -> None:
        assert folders_left_of(PureWindowsPath("d:/"), [_C, _D, _E]) == [_E, _C]

    def test_a_share_s_top_goes_to_every_drive_from_the_first(self) -> None:
        share = PureWindowsPath("//server/comics/")
        assert share.parent == share
        assert folders_left_of(share, [_C, _D]) == [_C, _D]

    def test_the_only_drive_s_top_stays_where_it_is(self) -> None:
        assert folders_left_of(_C, [_C]) == [_C]

    def test_with_no_drives_the_top_folder_stays_where_it_is(self) -> None:
        assert folders_left_of(PurePosixPath("/"), []) == [PurePosixPath("/")]
        assert folders_left_of(PurePosixPath("/home/reader"), []) == [PurePosixPath("/home")]


class TestDrives:
    def test_windows_drives_are_its_own_list_of_them(self) -> None:
        with (
            patch.object(folder_chooser.sys, "platform", "win32"),
            patch.object(
                folder_chooser.os, "listdrives", create=True, return_value=["C:\\", "D:\\"]
            ),
        ):
            assert drives() == [Path("C:\\"), Path("D:\\")]

    def test_no_other_system_has_any(self) -> None:
        with patch.object(folder_chooser.sys, "platform", "linux"):
            assert drives() == []
