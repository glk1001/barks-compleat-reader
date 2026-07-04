"""Kivy widgets and app for the OKF reader (imports only from okf_reader.core)."""

import os

# Stop Kivy from parsing the process argv on import, so the CLI (typer) owns the
# command line — otherwise Kivy intercepts things like --help. Runs before viewer.py
# imports kivy. setdefault: never override a host app that set its own preference.
os.environ.setdefault("KIVY_NO_ARGS", "1")
