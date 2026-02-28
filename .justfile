import '../barks-comic-building/.justfile'

_default2:
    just --list --unsorted

# Fire up the Compleat Barks Reader
reader win_left="-1" win_height="0":
    uv run --project "{{source_dir()}}" "{{source_dir()}}/main.py" --win-left {{win_left}} --win-height {{win_height}}

# Fire up the Compleat Barks Reader in 1080p
reader-1080p win_left="10" win_top="10" win_height="1020":
    uv run --project "{{source_dir()}}" "{{source_dir()}}/main.py" --win-left {{win_left}} --win-top {{win_top}} --win-height {{win_height}}

# Get panels info for a volume or volumes
panels-info volume:
    uv run --project "{{source_dir()}}" "{{source_dir()}}/scripts/panels-info.py" --log-level WARNING --volume {{volume}}

inset-width height:
    @bash "{{source_dir()}}/scripts/inset_width.sh" {{height}}

view-width height:
    @bash "{{source_dir()}}/scripts/view_width.sh" {{height}}
