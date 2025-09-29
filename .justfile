import '../barks-comic-building/.justfile'

_default2:
    just --list --unsorted

# Fire up the Compleat Barks Reader
reader win_left="-1" win_height="0":
    {{uv_run}}  "{{source_dir()}}/main.py" --win-left {{win_left}} --win-height {{win_height}}

# Get panels info for a volume or volumes
panels-info volume:
    {{uv_run}}  "{{source_dir()}}/scripts/panels-info.py" --log-level WARNING --volume {{volume}}

inset-width height:
    @bash "{{source_dir()}}/scripts/inset_width.sh" {{height}}

view-width height:
    @bash "{{source_dir()}}/scripts/view_width.sh" {{height}}
