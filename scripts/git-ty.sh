echo Ty checking uncommited python files:

echo
# Get changed Python files, excluding paths listed in ty.toml [src.exclude]
EXCLUDED_PATTERNS=(
    "experiments/"
    "scraps/"
    "benchmarks/"
    "pyarmor_runtime_000000/"
    "tests/test_barks_tags.py"
    "tests/test_panel_bounding.py"
    "tests/test_whoosh_search_engine.py"
    "tests/unit/test_image_selector.py"
    "tests/unit/test_main_screen_nav.py"
    "tests/unit/test_main_screen_window.py"
)

FILES=$(git diff --name-only --diff-filter=ACMRTUXB HEAD | grep '\.py$')

for pattern in "${EXCLUDED_PATTERNS[@]}"; do
    FILES=$(echo "$FILES" | grep -v "$pattern")
done

if [ -z "$FILES" ]; then
    echo "No files to check."
    exit 0
fi

echo "$FILES"
echo
echo "$FILES" | xargs uv run ty check --respect-ignore-files
