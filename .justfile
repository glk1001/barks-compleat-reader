set dotenv-load

import '../barks-comic-building/.justfile'

_default2:
    just --list --unsorted

# Fire up the Compleat Barks Reader
reader:
    uv run "{{source_dir()}}/src/barks_reader/main.py"

# Get panels info for a volume or volumes
panels-info volume:
    uv run "{{source_dir()}}/scripts/panels-info.py" --volume {{volume}}

inset-width height:
    @bash "{{source_dir()}}/scripts/inset_width.sh" {{height}}

inset-view height:
    @bash "{{source_dir()}}/scripts/inset_view.sh" {{height}}
