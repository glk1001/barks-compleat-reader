#!/usr/bin/env bash

case "$(uname -s)" in
    Linux*)
        OS="linux"
        ;;
    Darwin*)
        OS="macos"
        ;;
    CYGWIN*|MINGW*|MSYS*|Windows_NT*)
        OS="windows"
        ;;
    *)
        OS="unknown"
        ;;
esac

echo "Detected OS: $OS"

