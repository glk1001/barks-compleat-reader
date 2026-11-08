"""The Linux .desktop entry and hicolor icon that let a dock show the app's icon."""

# ruff: noqa: SLF001

from __future__ import annotations

import os
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

# These compare the Exec= line with a POSIX path written as it is. On Windows the path
# resolves to "D:\opt\..." and Exec= escapes each backslash, so they cannot match;
# the entry is only ever written on Linux.
_POSIX_PATHS_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="a Linux .desktop entry; Windows paths are escaped"
)


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
def test_an_unchanged_icon_is_not_copied_again(icon: Path) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    with patch.object(lde.shutil, lde.shutil.copyfile.__name__) as copyfile:
        lde.write_linux_desktop_entry(icon, "Barks Reader")

    copyfile.assert_not_called()


def test_a_changed_icon_of_the_same_size_is_copied(data_home: Path, icon: Path) -> None:
    """An app update can change the icon without changing its byte size, or its mtime.

    The same size and mtime are what a shallow compare goes by: only the bytes differ.
    """
    lde.write_linux_desktop_entry(icon, "Barks Reader")
    installed = data_home / "icons" / "hicolor" / "128x128" / "apps" / f"{APP_NAME}.png"
    icon.write_bytes(b"PNG BYTES")  # the same nine bytes, different content
    installed_stat = installed.stat()
    os.utime(icon, ns=(installed_stat.st_atime_ns, installed_stat.st_mtime_ns))

    lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert installed.read_bytes() == b"PNG BYTES"


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


def test_an_entry_that_is_not_utf8_is_rewritten(
    data_home: Path, icon: Path, loguru_sink: list[str]
) -> None:
    """Another tool's non-UTF-8 entry does not stop the app starting: it is replaced."""
    _desktop_file(data_home).parent.mkdir(parents=True)
    _desktop_file(data_home).write_bytes(b"[Desktop Entry]\nName=Caf\xe9\n")

    lde.write_linux_desktop_entry(icon, "Barks Reader")

    assert "Name=Barks Reader\n" in _desktop_file(data_home).read_text(encoding="utf-8")
    assert any("Could not read desktop entry" in line for line in loguru_sink)


@pytest.mark.usefixtures("data_home")
def test_an_entry_that_cannot_be_read_is_logged_not_raised(
    icon: Path, loguru_sink: list[str]
) -> None:
    lde.write_linux_desktop_entry(icon, "Barks Reader")

    with (
        patch.object(Path, Path.read_text.__name__, side_effect=PermissionError("denied")),
        patch.object(Path, Path.write_text.__name__, side_effect=PermissionError("denied")),
    ):
        lde.write_linux_desktop_entry(icon, "Barks Reader")  # the app starts all the same

    assert any("Could not read desktop entry" in line for line in loguru_sink)
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
    @_POSIX_PATHS_ONLY
    def test_a_compiled_build_launches_itself(self) -> None:
        with (
            patch.object(lde, "IS_COMPILED", True),  # noqa: FBT003
            patch.object(sys, "argv", ["/opt/barks-reader/barks-reader"]),
        ):
            assert lde._resolve_exec_command() == str(
                Path("/opt/barks-reader/barks-reader").resolve()
            )

    @_POSIX_PATHS_ONLY
    def test_a_path_with_a_space_is_double_quoted(self) -> None:
        """Only double quotes quote in Exec=: a shell's single quotes would split the path."""
        with (
            patch.object(lde, "IS_COMPILED", True),  # noqa: FBT003
            patch.object(sys, "argv", ["/opt/barks reader/barks-reader"]),
        ):
            exec_cmd = lde._resolve_exec_command()
        assert exec_cmd == f'"{Path("/opt/barks reader/barks-reader").resolve()}"'
        assert "'" not in exec_cmd

    def test_from_source_the_interpreter_runs_the_script(self, tmp_path: Path) -> None:
        script = tmp_path / "main.py"
        script.write_text("", encoding="utf-8")
        with (
            patch.object(lde, "IS_COMPILED", False),  # noqa: FBT003
            patch.object(sys, "argv", [str(script)]),
        ):
            assert lde._resolve_exec_command() == (
                f"{lde._exec_arg(sys.executable)} {lde._exec_arg(str(script.resolve()))}"
            )

    def test_with_no_script_the_interpreter_alone(self) -> None:
        with (
            patch.object(lde, "IS_COMPILED", False),  # noqa: FBT003
            patch.object(sys, "argv", [""]),
        ):
            assert lde._resolve_exec_command() == lde._exec_arg(sys.executable)

    @_POSIX_PATHS_ONLY
    def test_the_entry_holds_the_real_exec_line(self) -> None:
        """Unpatched, as the dock reads it: a quoted path on the Exec= line."""
        with (
            patch.object(lde, "IS_COMPILED", True),  # noqa: FBT003
            patch.object(sys, "argv", ["/opt/barks reader/barks-reader"]),
        ):
            content = lde._build_entry_content(APP_NAME, "Barks Reader")
        expected = Path("/opt/barks reader/barks-reader").resolve()
        assert f'Exec="{expected}"\n' in content


class TestExecArg:
    """One Exec= argument, quoted as the Desktop Entry spec reads it."""

    def test_a_plain_path_is_left_bare(self) -> None:
        assert lde._exec_arg("/usr/bin/python3.13") == "/usr/bin/python3.13"

    def test_a_percent_is_doubled_so_it_is_no_field_code(self) -> None:
        assert lde._exec_arg("/opt/100%/app") == "/opt/100%%/app"

    def test_a_percent_in_a_quoted_argument_is_doubled_too(self) -> None:
        assert lde._exec_arg("/opt/100% sure/app") == '"/opt/100%% sure/app"'

    @pytest.mark.parametrize(
        ("arg", "expected"),
        [
            ("/opt/a b", '"/opt/a b"'),
            ("/opt/it's", '"/opt/it\'s"'),
            ("/opt/(x)", '"/opt/(x)"'),
            ('/opt/say "hi"', '"/opt/say \\\\"hi\\\\""'),
            ("/opt/$HOME", '"/opt/\\\\$HOME"'),
            ("/opt/`x`", '"/opt/\\\\`x\\\\`"'),
        ],
    )
    def test_a_reserved_character_double_quotes_the_argument(self, arg: str, expected: str) -> None:
        assert lde._exec_arg(arg) == expected

    def test_a_backslash_takes_four_in_the_file(self) -> None:
        """Escaped once for the quotes, then each backslash doubled as a string value."""
        assert lde._exec_arg("/opt/a\\b") == '"/opt/a\\\\\\\\b"'

    def test_a_newline_is_written_as_its_escape(self) -> None:
        assert lde._exec_arg("/opt/a\nb") == '"/opt/a\\nb"'
