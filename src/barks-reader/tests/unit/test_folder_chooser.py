"""Where the folder chooser's Left key goes (``core.folder_chooser``)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest
from barks_reader.core import folder_chooser
from barks_reader.core.folder_chooser import (
    drives,
    folder_and_selection_for_typed,
    folders_left_of,
    highlight_after,
    is_parent_entry,
    start_folder,
)

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


class TestStartFolder:
    """The parent of the setting's folder, or home when the setting names no real place."""

    def test_a_folder_that_exists_opens_on_its_parent(self, tmp_path: Path) -> None:
        (tmp_path / "library").mkdir()
        assert start_folder(str(tmp_path / "library"), Path("/home/reader")) == tmp_path

    def test_a_folder_gone_from_a_parent_that_is_there_still_opens_on_the_parent(
        self, tmp_path: Path
    ) -> None:
        assert start_folder(str(tmp_path / "gone"), Path("/home/reader")) == tmp_path

    @pytest.mark.parametrize(
        "value", ["<Fantagraphics Volumes Not Set>", "", "library", "comics/library"]
    )
    def test_a_value_that_is_no_full_path_opens_on_home(
        self, value: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Not on the folder the app was started from: the parent of such a value is "."."""
        (tmp_path / "comics").mkdir()
        monkeypatch.chdir(tmp_path)
        assert start_folder(value, Path("/home/reader")) == Path("/home/reader")

    def test_a_full_path_whose_parent_is_gone_opens_on_home(self, tmp_path: Path) -> None:
        home = Path("/home/reader")
        assert start_folder(str(tmp_path / "gone" / "library"), home) == home


class TestTheParentEntry:
    @pytest.mark.parametrize(
        "entry",
        ["/library/comics/../", "/library/comics/..", "C:\\library\\..\\", "C:\\library\\..", ".."],
    )
    def test_the_row_for_the_folder_above_whichever_way_its_separators_lean(
        self, entry: str
    ) -> None:
        assert is_parent_entry(entry) is True

    @pytest.mark.parametrize(
        "entry", ["/library/comics", "/library/comics/", "/library/more..", "/library/..more/", ""]
    )
    def test_a_folder_is_not_it_even_one_named_with_dots(self, entry: str) -> None:
        assert is_parent_entry(entry) is False


class TestATypedPath:
    def test_a_folder_that_exists_is_listed_and_selected(self, tmp_path: Path) -> None:
        (tmp_path / "library").mkdir()
        typed = folder_and_selection_for_typed(str(tmp_path / "library"))
        assert typed == (tmp_path / "library", tmp_path / "library")

    def test_a_name_half_typed_lists_the_folder_it_is_in(self, tmp_path: Path) -> None:
        assert folder_and_selection_for_typed(str(tmp_path / "lib")) == (
            tmp_path,
            tmp_path / "lib",
        )

    def test_a_path_with_nothing_of_it_there_moves_nothing(self, tmp_path: Path) -> None:
        assert folder_and_selection_for_typed(str(tmp_path / "no" / "such" / "place")) is None

    def test_a_tilde_is_the_reader_s_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "comics").mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        typed = folder_and_selection_for_typed("~/comics")
        assert typed == (tmp_path / "comics", tmp_path / "comics")


class TestTheHighlight:
    _ENTRIES = ("..", "alpha", "beta", "notes.txt")

    @pytest.mark.parametrize(
        ("current", "delta", "index"),
        [("alpha", 1, 2), ("alpha", -1, 0), ("..", -1, 0), ("notes.txt", 1, 3), ("alpha", 5, 3)],
    )
    def test_it_moves_from_the_entry_highlighted_and_stops_at_the_ends(
        self, current: str, delta: int, index: int
    ) -> None:
        assert highlight_after(self._ENTRIES, current, delta) == index

    @pytest.mark.parametrize("current", [None, "gone"])
    @pytest.mark.parametrize("delta", [1, -1])
    def test_with_nothing_listed_highlighted_it_starts_at_the_top(
        self, current: str | None, delta: int
    ) -> None:
        assert highlight_after(self._ENTRIES, current, delta) == 0

    def test_an_empty_list_has_only_its_first_place(self) -> None:
        assert highlight_after((), None, 1) == 0
