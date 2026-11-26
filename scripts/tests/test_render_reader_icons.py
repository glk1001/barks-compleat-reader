"""Tests for the icon renderer: its table, the how-to's black glyphs and what it writes."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import generated_files
import pytest
import render_reader_icons
from barks_reader.core import system_file_paths
from render_reader_icons import ICONS, Icon, IconRenderError, black_glyph, render_all
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from pathlib import Path

WHITE_SVG = '<svg><path stroke="#ffffff"/></svg>'
ACTION_BAR = "Reader Icons/ActionBar Icons"
# The icons the app keeps outside the action bar's folder, among the pictures there.
VARIOUS_ICONS = {
    "Various/goto-title-button.png",
    "Various/icon-eye-off.png",
    "Various/icon-eye-open.png",
    "Various/speech-bubble-icon.png",
}


def _fake_inkscape(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
    """Stand in for Inkscape: write the SVG's text where the PNG was asked for."""
    svg = command[1]
    target = next(arg for arg in command if arg.startswith("--export-filename="))
    with open(svg, encoding="utf-8") as source:  # noqa: PTH123
        text = source.read()
    with open(target.split("=", 1)[1], "w", encoding="utf-8") as png:  # noqa: PTH123
        png.write(f"png of {text}")
    return subprocess.CompletedProcess(command, 0, "", "")


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Make the sources, a Reader Files folder and the how-to's folder."""
    sources = write_tree(
        tmp_path / "sources",
        {"glyph.svg": WHITE_SVG, "dot.svg": '<svg><circle fill="#1f1a17"/></svg>'},
    )
    reader_files = tmp_path / "Reader Files"
    (reader_files / ACTION_BAR).mkdir(parents=True)
    how_to = tmp_path / "docs"
    how_to.mkdir()
    return sources, reader_files, how_to


TWO = (
    Icon("glyph.svg", f"{ACTION_BAR}/glyph.png", "icon-glyph.png"),
    Icon("dot.svg", how_to="icon-dot.png"),
)


class TestTheTable:
    def test_every_source_is_there(self) -> None:
        missing = [path.name for path in render_reader_icons.source_paths() if not path.is_file()]

        assert missing == []

    def test_every_svg_in_the_folder_is_in_the_table(self) -> None:
        drawn = {path.name for path in render_reader_icons.SOURCES_DIR.glob("*.svg")}

        assert drawn == {icon.svg for icon in ICONS}

    def test_the_app_s_icons_are_the_ones_installed(self) -> None:
        """Every icon the app needs has a source, and nothing is installed it does not read."""
        needed = {asset.value.relative_path for asset in system_file_paths._Asset}  # noqa: SLF001
        app_icons = {path for path in needed if path.startswith(f"{ACTION_BAR}/")} | VARIOUS_ICONS

        assert needed >= VARIOUS_ICONS
        assert {icon.installed for icon in ICONS if icon.installed is not None} == app_icons

    def test_no_two_icons_are_written_to_one_file(self) -> None:
        installed = [icon.installed for icon in ICONS if icon.installed is not None]
        how_to = [icon.how_to for icon in ICONS if icon.how_to is not None]

        assert len(set(installed)) == len(installed)
        assert len(set(how_to)) == len(how_to)

    def test_every_how_to_icon_can_be_shown_black(self) -> None:
        for icon in ICONS:
            if icon.how_to is not None:
                source = render_reader_icons.SOURCES_DIR / icon.svg
                black_glyph(source.read_text(encoding="utf-8"), icon.svg)

    def test_the_how_to_shows_only_icons_that_are_rendered(self) -> None:
        how_to = (render_reader_icons.HOW_TO_DIR / "how-to-use.md").read_text(encoding="utf-8")
        rendered = {icon.how_to for icon in ICONS if icon.how_to is not None}

        shown = {
            part.split('"', 1)[0] for part in how_to.split('<img src="')[1:] if "icon-" in part[:6]
        }

        assert shown
        assert shown <= rendered


class TestBlackGlyph:
    def test_a_white_glyph_is_drawn_black(self) -> None:
        assert black_glyph(WHITE_SVG, "glyph.svg") == '<svg><path stroke="#000000"/></svg>'

    def test_a_picture_with_no_white_is_left_as_it_is(self) -> None:
        picture = '<svg><circle fill="#f3d105"/></svg>'

        assert black_glyph(picture, "disc.svg") == picture

    def test_one_that_draws_in_both_is_refused(self) -> None:
        both = '<svg><path stroke="#ffffff"/><path stroke="#000000"/></svg>'

        with pytest.raises(IconRenderError, match=r"eye\.svg draws in black as well as white"):
            black_glyph(both, "eye.svg")


class TestRenderAll:
    def test_the_app_s_icon_is_white_and_the_how_to_s_black(
        self, folders: tuple[Path, Path, Path]
    ) -> None:
        sources, reader_files, how_to = folders

        with (
            patch.object(render_reader_icons.shutil, "which", return_value="inkscape"),
            patch.object(render_reader_icons.subprocess, "run", side_effect=_fake_inkscape),
        ):
            written = render_all(reader_files, how_to, sources, TWO)

        assert written == [
            reader_files / ACTION_BAR / "glyph.png",
            how_to / "icon-glyph.png",
            how_to / "icon-dot.png",
        ]
        assert "#ffffff" in written[0].read_text(encoding="utf-8")
        assert "#000000" in written[1].read_text(encoding="utf-8")
        assert "#1f1a17" in written[2].read_text(encoding="utf-8")

    def test_inkscape_is_asked_for_a_square_of_the_size(
        self, folders: tuple[Path, Path, Path]
    ) -> None:
        sources, reader_files, how_to = folders

        with (
            patch.object(render_reader_icons.shutil, "which", return_value="/usr/bin/inkscape"),
            patch.object(render_reader_icons.subprocess, "run", side_effect=_fake_inkscape) as run,
        ):
            render_all(reader_files, how_to, sources, TWO[:1])

        command = run.call_args_list[0].args[0]
        assert command[0] == "/usr/bin/inkscape"
        assert command[1] == str(sources / "glyph.svg")
        assert command[-4:] == ["-w", "512", "-h", "512"]
        assert "--export-type=png" in command

    def test_a_source_that_is_not_there_is_named_and_nothing_is_written(
        self, folders: tuple[Path, Path, Path]
    ) -> None:
        sources, reader_files, how_to = folders
        (sources / "dot.svg").unlink()

        with pytest.raises(IconRenderError, match=r"No such source in .*: dot\.svg"):
            render_all(reader_files, how_to, sources, TWO)

        assert list(how_to.iterdir()) == []

    def test_a_folder_to_install_into_that_is_not_there_is_named(
        self, folders: tuple[Path, Path, Path], tmp_path: Path
    ) -> None:
        sources, _reader_files, how_to = folders

        with pytest.raises(IconRenderError, match="No such folder to install into"):
            render_all(tmp_path / "elsewhere", how_to, sources, TWO)

    def test_a_render_that_fails_leaves_both_places_as_they_were(
        self, folders: tuple[Path, Path, Path]
    ) -> None:
        sources, reader_files, how_to = folders
        installed = reader_files / ACTION_BAR / "glyph.png"
        installed.write_text("the icon shown now", encoding="utf-8")
        calls: list[list[str]] = []

        def second_fails(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if len(calls) == 2:  # noqa: PLR2004
                return subprocess.CompletedProcess(command, 1, "", "bad path data")
            return _fake_inkscape(command, **kwargs)

        with (
            patch.object(render_reader_icons.shutil, "which", return_value="inkscape"),
            patch.object(render_reader_icons.subprocess, "run", side_effect=second_fails),
            pytest.raises(IconRenderError, match=r"could not render .*: bad path data"),
        ):
            render_all(reader_files, how_to, sources, TWO)

        assert installed.read_text(encoding="utf-8") == "the icon shown now"
        assert list(how_to.iterdir()) == []

    def test_no_inkscape_is_said(self, folders: tuple[Path, Path, Path]) -> None:
        sources, reader_files, how_to = folders

        with (
            patch.object(render_reader_icons.shutil, "which", return_value=None),
            pytest.raises(IconRenderError, match="Inkscape is not installed"),
        ):
            render_all(reader_files, how_to, sources, TWO)


class TestMain:
    def test_list_says_where_each_source_goes(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert render_reader_icons.main(["--list"]) == 0

        out = capsys.readouterr().out.splitlines()
        assert len(out) == len(ICONS)
        assert f"icon-power.svg: {ACTION_BAR}/icon-power.png, icon-power.png" in out
        assert "how-to-read-dot-full.svg: icon-read-dot-full.png" in out

    def test_it_renders_into_the_folder_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(render_reader_icons, "render_all", return_value=[tmp_path]) as render:
            status = render_reader_icons.main(["--reader-files-dir", str(tmp_path)])

        assert status == 0
        render.assert_called_once_with(tmp_path)
        assert "Rendered 1 icons" in capsys.readouterr().out

    def test_with_no_folder_named_it_renders_into_this_machine_s_own(self, tmp_path: Path) -> None:
        dirs = generated_files.ReaderDirs(
            how_to=tmp_path,
            intro=tmp_path,
            statistics=tmp_path,
            indexes=tmp_path,
            reader_files=tmp_path / "Reader Files",
        )
        with (
            patch.object(generated_files, "reader_dirs", return_value=dirs),
            patch.object(render_reader_icons, "render_all", return_value=[]) as render,
        ):
            assert render_reader_icons.main([]) == 0

        render.assert_called_once_with(tmp_path / "Reader Files")

    def test_a_refusal_is_printed_and_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            render_reader_icons, "render_all", side_effect=IconRenderError("no Inkscape")
        ):
            status = render_reader_icons.main(["--reader-files-dir", str(tmp_path)])

        assert status == 1
        assert "no Inkscape" in capsys.readouterr().err
