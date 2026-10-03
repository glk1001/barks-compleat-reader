"""The Windows backend for ``gui_probe.py``: real input through ``SendInput``.

Keys and clicks go into the OS input queue exactly as a keyboard's would, so
they reach the app through Windows, SDL and Kivy - the path a user's keyboard or
remote takes, and the one where the suite's input bugs were found. Nothing is
fed into the app from inside it.

``SendInput`` goes to the foreground window, which is why the probe brings the
app to the front before every burst - without sending any input to do it, so
nothing ever reaches a window other than the app's. A locked screen or a minimized remote
session accepts nothing; ``doctor`` checks for both.

Its calls work only on Windows; the module imports anywhere, so its key table
and structures can be tested on every platform.
"""

# cspell:ignore DEVMODE DPIAWARENESSCONTEXT EXTENDEDKEY KEYBDINPUT KEYEVENTF LEFTDOWN
# cspell:ignore LEFTUP MAPVK MOUSEEVENTF MOUSEINPUT SWITCHDESKTOP HARDWAREINPUT REMOTESESSION
# cspell:ignore VSC shcore wparam lparam INPUTUNION KEYUP creationflags getwindowsversion
# cspell:ignore taskkill pids Toolhelp SNAPPROCESS PROCESSENTRY
# cspell:ignore PIXELFORMATDESCRIPTOR DOUBLEBUFFER Accum

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pathlib import Path

_ON_WINDOWS = sys.platform == "win32"
_user32: Any = ctypes.WinDLL("user32", use_last_error=True) if _ON_WINDOWS else None
_kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True) if _ON_WINDOWS else None

_ULONG_PTR = ctypes.c_size_t

_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MAPVK_VK_TO_VSC = 0
_VK_SHIFT = 0x10
_SW_RESTORE = 9
_DESKTOP_SWITCHDESKTOP = 0x0100
_SM_REMOTESESSION = 0x1000
_SYNCHRONIZE = 0x00100000
_TH32CS_SNAPPROCESS = 0x00000002
_WM_CLOSE = 0x0010
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_WAIT_OBJECT_0 = 0
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
_PFD_DOUBLEBUFFER = 0x00000001
_PFD_DRAW_TO_WINDOW = 0x00000004
_PFD_SUPPORT_OPENGL = 0x00000020
_GL_RENDERER = 0x1F01
# PIXELFORMATDESCRIPTOR's one-byte fields, in order, between dwFlags and dwLayerMask.
_PFD_BYTE_FIELDS = (
    "iPixelType", "cColorBits", "cRedBits", "cRedShift", "cGreenBits", "cGreenShift",
    "cBlueBits", "cBlueShift", "cAlphaBits", "cAlphaShift", "cAccumBits", "cAccumRedBits",
    "cAccumGreenBits", "cAccumBlueBits", "cAccumAlphaBits", "cDepthBits", "cStencilBits",
    "cAuxBuffers", "iLayerType", "bReserved",
)  # fmt: skip
# How long `kill_tree` gives the app to close its window and exit before it is
# ended by force: long enough for Kivy to stop and coverage to save its data.
CLOSE_GRACE_SECS = 10

# X11 keysym names (what the suite and gui-probe.sh use) -> Windows virtual keys.
# The arrows and the editing block sit on the extended part of a real keyboard,
# and a key sent without the extended flag reaches SDL as its numeric-pad twin.
VIRTUAL_KEYS: dict[str, tuple[int, bool]] = {
    "Escape": (0x1B, False),
    "Return": (0x0D, False),
    "Tab": (0x09, False),
    "BackSpace": (0x08, False),
    "space": (0x20, False),
    "Up": (0x26, True),
    "Down": (0x28, True),
    "Left": (0x25, True),
    "Right": (0x27, True),
    "Delete": (0x2E, True),
    "Home": (0x24, True),
    "End": (0x23, True),
    "Prior": (0x21, True),
    "Next": (0x22, True),
}


class _MOUSEINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", _ULONG_PTR),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _RECT(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


_ENUM_WINDOWS_PROC: Any = (
    ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM) if _ON_WINDOWS else None
)


def _declare() -> None:
    """Give every call its real signature, so 64-bit handles are not cut to 32 bits."""
    u, k = _user32, _kernel32
    u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    u.SendInput.restype = wintypes.UINT
    u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    u.MapVirtualKeyW.restype = wintypes.UINT
    u.VkKeyScanW.argtypes = [wintypes.WCHAR]
    u.VkKeyScanW.restype = ctypes.c_short
    u.EnumWindows.argtypes = [_ENUM_WINDOWS_PROC, wintypes.LPARAM]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    u.AttachThreadInput.restype = wintypes.BOOL
    k.GetCurrentThreadId.restype = wintypes.DWORD
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    u.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    u.OpenInputDesktop.restype = wintypes.HANDLE
    u.SwitchDesktop.argtypes = [wintypes.HANDLE]
    u.CloseDesktop.argtypes = [wintypes.HANDLE]
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def _make_dpi_aware() -> None:
    """Work in physical pixels, so window rectangles and screenshots agree on a scaled display."""
    try:
        _user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        if _user32.SetProcessDpiAwarenessContext(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return
    except AttributeError:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)  # ty: ignore[unresolved-attribute]
    except (AttributeError, OSError):
        _user32.SetProcessDPIAware()


def _key_input(vk: int, *, extended: bool, up: bool) -> _INPUT:
    flags = (_KEYEVENTF_EXTENDEDKEY if extended else 0) | (_KEYEVENTF_KEYUP if up else 0)
    scan = _user32.MapVirtualKeyW(vk, _MAPVK_VK_TO_VSC)
    item = _INPUT(type=_INPUT_KEYBOARD)
    item.u.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _unicode_input(char: str, *, up: bool) -> _INPUT:
    item = _INPUT(type=_INPUT_KEYBOARD)
    flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if up else 0)
    item.u.ki = _KEYBDINPUT(wVk=0, wScan=ord(char), dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _mouse_input(flags: int) -> _INPUT:
    item = _INPUT(type=_INPUT_MOUSE)
    item.u.mi = _MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _send(*items: _INPUT) -> None:
    """Queue the events in one call, so nothing else can land between them."""
    array = (_INPUT * len(items))(*items)
    sent = _user32.SendInput(len(items), array, ctypes.sizeof(_INPUT))
    if sent != len(items):
        error = ctypes.get_last_error()  # ty: ignore[unresolved-attribute]
        msg = (
            f"SendInput queued {sent} of {len(items)} events (error {error}):"
            " a locked screen, a minimized remote session, or a window of higher"
            " integrity in front refuses injected input"
        )
        raise RuntimeError(msg)


def _is_sdl_window(hwnd: int) -> bool:
    """Return whether `hwnd` is an SDL window (Kivy's; class "SDL_app")."""
    class_name = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, class_name, 256)
    return class_name.value.startswith("SDL")


def descendants(root: int, parents: dict[int, int]) -> set[int]:
    """Return `root` and every process below it, from each process's parent in `parents`."""
    tree = {root}
    grew = True
    while grew:
        below = {pid for pid, parent in parents.items() if parent in tree and pid not in tree}
        tree |= below
        grew = bool(below)
    return tree


def _process_parents() -> dict[int, int]:
    """Return each running process's parent, from a Toolhelp snapshot."""
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return {}
    parents: dict[int, int] = {}
    try:
        entry = _PROCESSENTRY32W(dwSize=ctypes.sizeof(_PROCESSENTRY32W))
        more = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            more = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    return parents


def find_window_of_processes(pids: set[int]) -> int | None:
    """Return a visible top-level window owned by one of `pids`, SDL's own first.

    For a window that has no title of its own to find it by (the first-run
    installer's: Kivy leaves it untitled, so a titled-only search finds nothing).
    An SDL window (Kivy's; class "SDL_app") is preferred over any other window the
    processes own. Call after a ``Win32Backend`` exists, which declares the calls.
    """
    sdl: list[int] = []
    other: list[int] = []

    def visit(hwnd: int, _lparam: int) -> bool:
        if not _user32.IsWindowVisible(hwnd):
            return True
        owner = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value not in pids:
            return True
        (sdl if _is_sdl_window(hwnd) else other).append(hwnd)
        return True

    _user32.EnumWindows(_ENUM_WINDOWS_PROC(visit), 0)
    return (sdl or other or [None])[0]


class _PIXELFORMATDESCRIPTOR(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("nSize", wintypes.WORD),
        ("nVersion", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        *((name, ctypes.c_ubyte) for name in _PFD_BYTE_FIELDS),
        ("dwLayerMask", wintypes.DWORD),
        ("dwVisibleMask", wintypes.DWORD),
        ("dwDamageMask", wintypes.DWORD),
    ]


def _session_id() -> int | None:
    """Return this process's Windows session: 0 is the services' (ssh), 1 up a user's."""
    if not _ON_WINDOWS:
        return None
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
    session = wintypes.DWORD()
    if not kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session)):
        return None
    return session.value


def opengl_renderer() -> str | None:
    """Return the renderer Windows' own OpenGL gives a window here, or None if it gives none.

    Read straight from WGL, on a hidden window of its own: Kivy, asked instead,
    stops on a modal "OpenGL 2.0 NOT found" box where there is no driver (the
    VirtualBox guest's "GDI Generic", OpenGL 1.1), waiting for a click that an
    unattended run never gives. None too in session 0, where an ssh login runs:
    Windows offers no GPU driver there, so every machine would answer "GDI
    Generic" (win_lg's did, a real GPU and all) and the answer is not the desktop's.
    """
    if not _ON_WINDOWS or _session_id() == 0:
        return None
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    opengl32 = ctypes.WinDLL("opengl32")
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]  # fmt: skip
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    pfd_p = ctypes.POINTER(_PIXELFORMATDESCRIPTOR)
    gdi32.ChoosePixelFormat.argtypes = [wintypes.HDC, pfd_p]
    gdi32.SetPixelFormat.argtypes = [wintypes.HDC, ctypes.c_int, pfd_p]
    gdi32.SetPixelFormat.restype = wintypes.BOOL
    opengl32.wglCreateContext.argtypes = [wintypes.HDC]
    opengl32.wglCreateContext.restype = wintypes.HANDLE
    opengl32.wglMakeCurrent.argtypes = [wintypes.HDC, wintypes.HANDLE]
    opengl32.wglMakeCurrent.restype = wintypes.BOOL
    opengl32.wglDeleteContext.argtypes = [wintypes.HANDLE]
    opengl32.glGetString.argtypes = [ctypes.c_uint]
    opengl32.glGetString.restype = ctypes.c_char_p

    hwnd = user32.CreateWindowExW(0, "STATIC", "gl-probe", 0, 0, 0, 1, 1, None, None, None, None)
    if not hwnd:
        return None
    name = None
    hdc = user32.GetDC(hwnd)
    try:
        pfd = _PIXELFORMATDESCRIPTOR(
            nSize=ctypes.sizeof(_PIXELFORMATDESCRIPTOR),
            nVersion=1,
            dwFlags=_PFD_DRAW_TO_WINDOW | _PFD_SUPPORT_OPENGL | _PFD_DOUBLEBUFFER,
            cColorBits=32,
        )
        fmt = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
        context = (
            opengl32.wglCreateContext(hdc)
            if fmt and gdi32.SetPixelFormat(hdc, fmt, ctypes.byref(pfd))
            else None
        )
        if context:
            try:
                if opengl32.wglMakeCurrent(hdc, context):
                    name = opengl32.glGetString(_GL_RENDERER)
                    opengl32.wglMakeCurrent(None, None)
            finally:
                opengl32.wglDeleteContext(context)
    finally:
        user32.ReleaseDC(hwnd, hdc)
        user32.DestroyWindow(hwnd)
    return name.decode(errors="replace") if name else None


class Win32Backend:
    """The ``gui_probe.Backend`` for Windows."""

    # A group of its own, so the probe's console never forwards its Ctrl+C to the
    # app, and no console window pops up for the uv or python child.
    creation_flags = _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW
    start_new_session = False

    def __init__(self) -> None:
        _declare()
        _make_dpi_aware()

    @staticmethod
    def workspace_app_argv(repo_root: Path) -> list[str]:
        return ["uv", "run", "--directory", str(repo_root), "python", "main.py"]

    def find_window(self, title: str) -> int | None:
        found: list[int] = []

        def visit(hwnd: int, _lparam: int) -> bool:
            # SDL's windows only: a browser tab or an editor showing the app's name
            # has it in its title too, and would take the keys meant for the app.
            if not _user32.IsWindowVisible(hwnd) or not _is_sdl_window(hwnd):
                return True
            length = _user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            text = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, text, length + 1)
            if title in text.value:
                found.append(hwnd)
                return False
            return True

        _user32.EnumWindows(_ENUM_WINDOWS_PROC(visit), 0)
        return found[0] if found else None

    def client_geometry(self, window: int) -> tuple[int, int, int, int]:
        rect = _RECT()
        if not _user32.GetClientRect(window, ctypes.byref(rect)):
            msg = "GetClientRect failed: the app window has gone"
            raise RuntimeError(msg)
        origin = wintypes.POINT(0, 0)
        _user32.ClientToScreen(window, ctypes.byref(origin))
        return rect.right - rect.left, rect.bottom - rect.top, origin.x, origin.y

    def bring_to_front(self, window: int) -> bool:
        if _user32.GetForegroundWindow() == window:
            return True
        if _user32.IsIconic(window):
            _user32.ShowWindow(window, _SW_RESTORE)
        # Windows lets only the thread that owns the foreground hand it on. Joining
        # that thread's input for the moment of the switch makes this probe one of
        # its own, without sending a key anywhere: a key sent to take the foreground
        # would land in whatever window had it.
        foreground = _user32.GetForegroundWindow()
        owner = _user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        this = _kernel32.GetCurrentThreadId()
        attached = (
            bool(owner)
            and owner != this
            and bool(
                _user32.AttachThreadInput(this, owner, True)  # noqa: FBT003
            )
        )
        try:
            _user32.BringWindowToTop(window)
            _user32.SetForegroundWindow(window)
        finally:
            if attached:
                _user32.AttachThreadInput(this, owner, False)  # noqa: FBT003
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if _user32.GetForegroundWindow() == window:
                return True
            time.sleep(0.05)
        return False

    def move_pointer(self, x: int, y: int) -> None:
        _user32.SetCursorPos(x, y)

    def click(self, x: int, y: int) -> None:
        _user32.SetCursorPos(x, y)
        _send(_mouse_input(_MOUSEEVENTF_LEFTDOWN), _mouse_input(_MOUSEEVENTF_LEFTUP))

    def send_key(self, name: str) -> None:
        if name in VIRTUAL_KEYS:
            vk, extended = VIRTUAL_KEYS[name]
            _send(
                _key_input(vk, extended=extended, up=False),
                _key_input(vk, extended=extended, up=True),
            )
        elif len(name) == 1:
            self.send_char(name)
        else:
            msg = f"no Windows key for the name {name!r}; add it to VIRTUAL_KEYS"
            raise ValueError(msg)

    def send_char(self, char: str) -> None:
        # A character the keyboard layout has goes as its real key (with Shift if
        # it needs it), as a person typing would send it; any other as Unicode.
        scan = _user32.VkKeyScanW(char)
        if scan == -1:
            _send(_unicode_input(char, up=False), _unicode_input(char, up=True))
            return
        vk, shift = scan & 0xFF, bool(scan & 0x100)
        events = [
            _key_input(vk, extended=False, up=False),
            _key_input(vk, extended=False, up=True),
        ]
        if shift:
            events = [
                _key_input(_VK_SHIFT, extended=False, up=False),
                *events,
                _key_input(_VK_SHIFT, extended=False, up=True),
            ]
        _send(*events)

    def capture(self, rect: tuple[int, int, int, int], out: Path) -> None:
        from PIL import ImageGrab  # noqa: PLC0415 (only a screenshot needs Pillow)

        width, height, x, y = rect
        ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True).save(out)

    def process_alive(self, pid: int) -> bool:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)  # noqa: FBT003
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            _kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == _STILL_ACTIVE
        finally:
            _kernel32.CloseHandle(handle)

    def kill_tree(self, pid: int, max_secs: float) -> None:
        # Closed first, as a user closes it: the app then exits as it would for
        # them, and coverage, when the app runs under it, saves its data at exit. On
        # Linux SDL turns the probe's SIGTERM into the same quit. `taskkill` without
        # /F would ask too, but the app's window belongs to the python under uv.
        handle = _kernel32.OpenProcess(_SYNCHRONIZE, False, pid)  # noqa: FBT003
        if handle and self._close(pid, handle):
            _kernel32.CloseHandle(handle)
            return
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607 (a system tool, on PATH)
            capture_output=True,
            check=False,
        )
        if handle:
            try:
                _kernel32.WaitForSingleObject(handle, int(max_secs * 1000))
            finally:
                _kernel32.CloseHandle(handle)

    @staticmethod
    def _close(pid: int, handle: int) -> bool:
        """Ask the app's window to close; return whether `pid` then exits in time."""
        window = find_window_of_processes(descendants(pid, _process_parents()))
        if window is None or not _user32.PostMessageW(window, _WM_CLOSE, 0, 0):
            return False
        waited = _kernel32.WaitForSingleObject(handle, CLOSE_GRACE_SECS * 1000)
        if waited == _WAIT_OBJECT_0:
            return True
        print(  # noqa: T201
            f"gui-probe: the app did not exit within {CLOSE_GRACE_SECS}s of closing its"
            " window; ending it by force"
        )
        return False

    def doctor_checks(self) -> list[tuple[str, str]]:
        checks: list[tuple[str, str]] = [("OK", f"Windows {sys.getwindowsversion().major}")]  # ty: ignore[unresolved-attribute]
        desktop = _user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)  # noqa: FBT003
        unlocked = bool(desktop) and bool(_user32.SwitchDesktop(desktop))
        if desktop:
            _user32.CloseDesktop(desktop)
        checks.append(
            ("OK", "an unlocked, connected desktop")
            if unlocked
            else ("FAIL", "the desktop is locked or disconnected: injected input would go nowhere")
        )
        if _user32.GetSystemMetrics(_SM_REMOTESESSION):
            # Whether its window is minimized is not something Windows says here.
            why = "minimize its window and it stops drawing, and injected input goes nowhere"
            checks.append(("WARN", f"a Remote Desktop session: {why}"))
        if self.find_window("Compleat Barks Disney Reader") is not None:
            checks.append(("FAIL", "a Barks Reader window is open - close it before a run"))
        try:
            from PIL import ImageGrab  # noqa: F401, PLC0415

            checks.append(("OK", "Pillow (screenshots)"))
        except ImportError:
            checks.append(
                ("FAIL", "Pillow not importable - run the probe with the workspace's Python")
            )
        return checks
