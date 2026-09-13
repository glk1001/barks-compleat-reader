set shell := ["bash", "-uc"]

import '../barks-comic-building/justfile'

# `offline` comes from the imported barks-comic-building justfile — do not redefine it
# here, just errors on a duplicate definition. The imported `uv_run` points at that
# repo, so this one needs its own project path.
_reader_uv_run := "uv run " + offline + " --project " + justfile_directory()

_default2:
    just --list --unsorted

# Fire up the Compleat Barks Reader
reader win_left="-1" win_height="0":
    {{_reader_uv_run}} "{{source_dir()}}/main.py" --win-left {{win_left}} --win-height {{win_height}}

# Fire up the Compleat Barks Reader in 1080p
reader-1080p win_left="10" win_top="10" win_height="1020":
    {{_reader_uv_run}} "{{source_dir()}}/main.py" --win-left {{win_left}} --win-top {{win_top}} --win-height {{win_height}}

# Get panels info for a volume or volumes
panels-info volume:
    {{_reader_uv_run}} "{{source_dir()}}/scripts/panels-info.py" --log-level WARNING --volume {{volume}}

# Image dimensions utils
inset-width height:
    @bash "{{source_dir()}}/scripts/inset_width.sh" {{height}}

view-width height:
    @bash "{{source_dir()}}/scripts/view_width.sh" {{height}}

# Run the Barks reader CI locally
act-ci:
    act -P ubuntu-latest=catthehacker/ubuntu:act-latest -P macos-latest=catthehacker/ubuntu:act-latest -P windows-latest=catthehacker/ubuntu:act-latest |& tee /tmp/act-output.log

# `serve` is used rather than `python3 -m http.server` because that one ignores
# Range requests, so a browser cannot seek into a video and the walkthrough's
# chapter buttons appear to hang. GitHub Pages does support ranges, so this only
# bites locally. Note `serve` drops the .html: /app.html redirects to /app.

# Serve the website locally, for checking the demo videos and their chapters
serve-website port="8080":
    bunx --bun serve "{{source_dir()}}/website" --listen {{port}}
