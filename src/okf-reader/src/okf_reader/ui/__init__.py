"""Kivy widgets and app for the OKF reader (imports only from okf_reader.core)."""

import os

_APP_NAME = "okf-reader"

# Stop Kivy from parsing the process argv on import, so the CLI (typer) owns the
# command line — otherwise Kivy intercepts things like --help. Runs before viewer.py
# imports kivy. setdefault: never override a host app that set its own preference.
os.environ.setdefault("KIVY_NO_ARGS", "1")

# Pin the SDL2 window class so compositors/window managers can identify the window
# (taskbar icon, desktop-entry matching). Same idiom as barks_reader.core.config_info;
# setdefault means an embedding app (e.g. the Barks reader, which sets these before
# any kivy import) keeps its own identity.
os.environ.setdefault("SDL_APP_ID", _APP_NAME)
os.environ.setdefault("SDL_VIDEO_WAYLAND_WMCLASS", _APP_NAME)
os.environ.setdefault("SDL_VIDEO_X11_WMCLASS", _APP_NAME)
