set shell := ["bash", "-uc"]

# The comic-building recipes, when that repo is cloned beside this one. `mod?` keeps
# the reader's own recipes working without it.

# The barks-comic-building recipes: `just comics` lists them, `just comics build 9`
mod? comics '../barks-comic-building'

# `uv run` re-syncs the project before every command and revalidates over the network
# any dependency it cannot resolve from disk or its cache, so with no connection every
# recipe would fail. UV_OFFLINE=1 runs from the installed venv; after adding or
# changing a dependency, when the sync genuinely has to reach the network:
#
#     UV_OFFLINE=0 just reader
export UV_OFFLINE := env("UV_OFFLINE", "1")

uv_run := "uv run --project " + source_dir()

_default:
    @just --list --unsorted

# The comic-building lookups used most from here, flat: `just info 23`, not
# `just comics info 23`. Anything else comic-building stays under `just comics`.

# Get Fanta volume page and status info
[group('comics')]
info volume: (comics::info volume)

# Get one-pager build state (all one-pagers, or just one volume's)
[group('comics')]
one-pager-info volume="": (comics::one-pager-info volume)

# Get cover configured state (all covers, or just one volume's)
[group('comics')]
cover-info volume="": (comics::cover-info volume)

# Fire up the Compleat Barks Reader
reader win_left="-1" win_height="0":
    {{uv_run}} "{{source_dir()}}/main.py" --win-left {{win_left}} --win-height {{win_height}}

# Fire up the Compleat Barks Reader in 1080p
reader-1080p win_left="10" win_top="10" win_height="1020":
    {{uv_run}} "{{source_dir()}}/main.py" --win-left {{win_left}} --win-top {{win_top}} --win-height {{win_height}}

# Get panels info for a volume or volumes
panels-info volume:
    {{uv_run}} "{{source_dir()}}/scripts/panels-info.py" --log-level WARNING --volume {{volume}}

# Width of an inset image at the given height (inset aspect ratio 1.036)
inset-width height:
    @bash "{{source_dir()}}/scripts/inset_width.sh" {{height}}

# Width of a view image at the given height (view aspect ratio 1.31)
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
