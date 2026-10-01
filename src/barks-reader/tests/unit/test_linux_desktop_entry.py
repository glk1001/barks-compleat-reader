"""The Linux .desktop entry and hicolor icon that let a dock show the app's icon."""

# ruff: noqa: SLF001

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from barks_reader.core import linux_desktop_entry as lde
from barks_reader.core.config_info import APP_NAME
from barks_reader.core.platform_info import Platform

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Point XDG_DATA_HOME under tmp_path, on Linux, running from source."""
    home = tmp_path / "share"
    monkeypatch.setenv("XDG_DATA_HOME", str(home))
    with (
        patch.object(lde, "PLATFORM", Platform.LINUX),
        patch.object(lde, "IS_COMPILED", False),  # noqa: FBT003
        patch.object(lde, lde._resolve_exec_command.__name__, return_value="barks-reader"),
    ):
        yield home


@pytest.fixture
def icon(tmp_path: Path) -> Path:
    path = tmp_path / "art" / "app-icon.png"
    path.parent.mkdir()
    path.write_bytes(b"png bytes")
    return path


def _desktop_file(data_home: Path) -> Path:
    return data_home / "applications" / f"{APP_NAME}.desktop"


def test_the_icon_is_installed_and_named_in_the_entry(data_home: Path, icon: Path) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    installed = data_home / "icons" / "hicolor" / "128x128" / "apps" / f"{APP_NAME}.png"
    assert installed.read_bytes() == b"png bytes"
    assert _desktop_file(data_home).read_text(encoding="utf-8") == (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Barks Reader\n"
        "Exec=barks-reader\n"
        f"Icon={APP_NAME}\n"
        f"StartupWMClass={APP_NAME}\n"
        "Categories=Graphics;Viewer;\n"
        "Terminal=false\n"
    )


@pytest.mark.usefixtures("data_home")
def test_an_unchanged_entry_is_not_rewritten(icon: Path) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    with patch.object(Path, Path.write_text.__name__) as write_text:
        lde.write_linux_desktop_entry(icon, "Barks Reader")

    write_text.assert_not_called()


def test_a_changed_entry_is_rewritten(data_home: Path, icon: Path) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    lde.write_linux_desktop_entry(icon, "Compleat Barks")

    assert "Name=Compleat Barks\n" in _desktop_file(data_home).read_text(encoding="utf-8")


@pytest.mark.usefixtures("data_home")
def test_an_icon_of_the_same_size_is_not_copied_again(icon: Path) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    with patch.object(lde.shutil, lde.shutil.copyfile.__name__) as copyfile:
        lde.write_linux_desktop_entry(icon, "Barks Reader")

    copyfile.assert_not_called()


def test_a_missing_icon_is_referenced_by_its_path(data_home: Path, tmp_path: Path) -> None:
    missing = tmp_path / "no-such-icon.png"

    lde.write_linux_desktop_entry(missing, "Barks Reader")

    assert f"Icon={missing}\n" in _desktop_file(data_home).read_text(encoding="utf-8")
    assert not (data_home / "icons").exists()


def test_an_icon_that_cannot_be_copied_is_referenced_by_its_path(
    data_home: Path, icon: Path
) -> None:
    with patch.object(lde.shutil, lde.shutil.copyfile.__name__, side_effect=OSError("full")):
        lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert f"Icon={icon}\n" in _desktop_file(data_home).read_text(encoding="utf-8")


def test_an_icon_dir_that_cannot_be_made_leaves_the_icon_by_its_path(
    data_home: Path, icon: Path
) -> None:
    data_home.mkdir()
    (data_home / "icons").write_text("a file where the icon tree goes", encoding="utf-8")

    lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert f"Icon={icon}\n" in _desktop_file(data_home).read_text(encoding="utf-8")


def test_an_applications_dir_that_cannot_be_made_writes_no_entry(
    data_home: Path, icon: Path, loguru_sink: list[str]
) -> None:
    data_home.mkdir()
    (data_home / "applications").write_text("a file, not a dir", encoding="utf-8")

    lde.write_linux_desktop_entry(icon, "Barks Reader")  # the app starts all the same

    assert (data_home / "applications").is_file()
    assert any("Could not create" in line for line in loguru_sink)


def test_an_entry_that_cannot_be_written_is_logged_not_raised(
    data_home: Path, icon: Path, loguru_sink: list[str]
) -> None:
    _desktop_file(data_home).mkdir(parents=True)  # a dir where the entry goes

    lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert any("Could not write desktop entry" in line for line in loguru_sink)


def test_an_icon_whose_size_cannot_be_read_does_not_match(tmp_path: Path) -> None:
    target = tmp_path / "installed.png"
    target.write_bytes(b"png bytes")
    assert lde._files_match(tmp_path / "vanished.png", target) is False


def test_nothing_is_written_off_linux(data_home: Path, icon: Path) -> None:
    with patch.object(lde, "PLATFORM", Platform.WIN):
        lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert not data_home.exists()


def test_the_data_home_defaults_to_local_share(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert lde._xdg_data_home() == Path.home() / ".local" / "share"


class TestExecCommand:
    def test_a_compiled_build_launches_itself(self) -> None:
        with (
            patch.object(lde, "IS_COMPILED", True),  # noqa: FBT003
            patch.object(sys, "argv", ["/opt/barks reader/barks-reader"]),
        ):
            assert lde._resolve_exec_command() == shlex.quote(
                str(Path("/opt/barks reader/barks-reader").resolve())
            )

    def test_from_source_the_interpreter_runs_the_script(self, tmp_path: Path) -> None:
        script = tmp_path / "main.py"
        script.write_text("", encoding="utf-8")
        with (
            patch.object(lde, "IS_COMPILED", False),  # noqa: FBT003
            patch.object(sys, "argv", [str(script)]),
        ):
            assert lde._resolve_exec_command() == (
                f"{shlex.quote(sys.executable)} {shlex.quote(str(script.resolve()))}"
            )

    def test_with_no_script_the_interpreter_alone(self) -> None:
        with (
            patch.object(lde, "IS_COMPILED", False),  # noqa: FBT003
            patch.object(sys, "argv", [""]),
        ):
            assert lde._resolve_exec_command() == shlex.quote(sys.executable)
