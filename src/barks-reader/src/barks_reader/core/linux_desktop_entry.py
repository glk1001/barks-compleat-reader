from __future__ import annotations

import filecmp
import os
import shutil
import sys
from pathlib import Path

from loguru import logger

from .config_info import APP_NAME, IS_COMPILED
from .platform_info import PLATFORM, Platform

_DESKTOP_ENTRY_FILENAME = f"{APP_NAME}.desktop"
# Where to install the icon inside the user's hicolor theme. PNGs go under a
# size-specific dir; ``scalable`` is canonically for SVG only and some docks
# (notably GNOME's Dash to Panel) skip PNGs found there during icon lookup.
# 128x128 matches our app-icon.png (close enough — the spec only requires the
# nominal directory size to bracket the actual icon size).
_HICOLOR_ICON_REL = Path("icons") / "hicolor" / "128x128" / "apps"
# The Desktop Entry spec's reserved characters: an Exec= argument holding one must be
# double-quoted, and inside the quotes these four take a backslash.
_EXEC_RESERVED_CHARS = frozenset(" \t\n\"'\\><~|&;$*?#()`")
_EXEC_ESCAPED_IN_QUOTES = frozenset('"`$\\')


def write_linux_desktop_entry(source_icon_path: Path, app_title: str) -> None:
    """Install a freedesktop ``.desktop`` entry and copy the app icon into hicolor.

    Sets up the user's hicolor icon theme entry plus a desktop file so Wayland/X11
    docks can resolve the taskbar icon for the running window.

    Wayland compositors (and modern X11 docks) match a running window's app_id /
    WM_CLASS against ``StartupWMClass`` in an installed ``.desktop`` file to decide
    which icon to show. The ``Icon=`` field then references the icon by *name* (not
    path), and the icon is loaded from a hicolor-theme directory. Using a name +
    theme install is more reliable across compositors than an absolute path,
    especially when the path contains spaces.

    Idempotent: rewrites the file only when its contents would change, copies the
    icon only when source and dest differ.

    Args:
        source_icon_path: Absolute path to the PNG icon Kivy uses for the app window.
        app_title: Human-readable name shown under the icon.

    """
    if PLATFORM != Platform.LINUX:
        return

    icon_name = _install_hicolor_icon(source_icon_path)
    _install_desktop_file(icon_name, app_title)


def _install_hicolor_icon(source_icon_path: Path) -> str:
    """Copy the icon into the hicolor theme; return the icon name to reference.

    Falls back to the absolute path if the install fails so the entry still has a
    chance to render the icon (the original behaviour).
    """
    if not source_icon_path.is_file():
        logger.warning(f"Icon source missing: {source_icon_path}")
        return str(source_icon_path)

    suffix = source_icon_path.suffix or ".png"
    icon_dir = _xdg_data_home() / _HICOLOR_ICON_REL
    target = icon_dir / f"{APP_NAME}{suffix}"

    try:
        icon_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(f"Could not create icon dir {icon_dir}: {exc}")
        return str(source_icon_path)

    if not _files_match(source_icon_path, target):
        try:
            shutil.copyfile(source_icon_path, target)
            logger.info(f"Installed hicolor icon: {target}")
        except OSError as exc:
            logger.warning(f"Could not copy icon to {target}: {exc}")
            return str(source_icon_path)

    return APP_NAME


def _install_desktop_file(icon_ref: str, app_title: str) -> None:
    desktop_dir = _xdg_data_home() / "applications"
    try:
        desktop_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(f"Could not create {desktop_dir}: {exc}")
        return

    desktop_file = desktop_dir / _DESKTOP_ENTRY_FILENAME
    content = _build_entry_content(icon_ref, app_title)

    if _entry_is_current(desktop_file, content):
        return

    try:
        desktop_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Could not write desktop entry {desktop_file}: {exc}")
        return

    logger.info(f"Wrote desktop entry: {desktop_file}")


def _entry_is_current(desktop_file: Path, content: str) -> bool:
    """Return whether the installed entry already holds `content`.

    An entry that cannot be read, or is not UTF-8 (another tool edited it), is not
    current: it is rewritten, and if it cannot be written either, that is logged.
    """
    if not desktop_file.is_file():
        return False
    try:
        return desktop_file.read_text(encoding="utf-8") == content
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning(f"Could not read desktop entry {desktop_file}: {exc}")
        return False


def _xdg_data_home() -> Path:
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    return Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"


def _files_match(a: Path, b: Path) -> bool:
    if not b.is_file():
        return False
    try:
        # By content: an updated icon of the same byte size must still be copied.
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _build_entry_content(icon_ref: str, app_title: str) -> str:
    exec_cmd = _resolve_exec_command()
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app_title}\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon_ref}\n"
        f"StartupWMClass={APP_NAME}\n"
        "Categories=Graphics;Viewer;\n"
        "Terminal=false\n"
    )


def _resolve_exec_command() -> str:
    """Best-effort command line for menu launching.

    Only ``StartupWMClass`` actually drives icon matching, so this is mostly
    cosmetic — but the freedesktop spec requires an ``Exec=`` for application
    entries, and a sane value lets the user launch from the menu/dock.
    """
    if IS_COMPILED:
        # The compiled standalone binary IS the app - no interpreter/script pair (the
        # dev-mode branch below would emit "Exec=<interpreter> <binary>" with a spurious
        # argument that aborts the Typer CLI). Use sys.argv[0]: Nuitka onefile guarantees
        # it is the absolute path of the launched binary, whereas sys.executable is the
        # version-specific EXTRACTED binary inside the onefile cache dir.
        return _exec_arg(str(Path(sys.argv[0]).resolve()))

    script = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if script and script.is_file():
        return f"{_exec_arg(sys.executable)} {_exec_arg(str(script))}"
    return _exec_arg(sys.executable)


def _exec_arg(arg: str) -> str:
    """Quote one ``Exec=`` argument as the Desktop Entry spec reads it.

    The spec's quoting is not a shell's: only double quotes quote, a literal ``%``
    is ``%%`` (or it is a field code), and the string-value escapes apply before
    the quoting, so every backslash is doubled again on its way into the file.
    """
    arg = arg.replace("%", "%%")
    if any(c in _EXEC_RESERVED_CHARS for c in arg):
        escaped = "".join(f"\\{c}" if c in _EXEC_ESCAPED_IN_QUOTES else c for c in arg)
        arg = f'"{escaped}"'
    return arg.replace("\\", "\\\\").replace("\n", "\\n")
