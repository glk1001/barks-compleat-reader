echo Ty checking uncommited python files:

echo
# Get changed Python files, excluding paths listed in ty.toml [src.exclude]
TOML_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../ty.toml"
mapfile -t EXCLUDED_PATTERNS < <(
    awk '/^exclude = \[/{found=1; next} found && /^\]/{exit} found{print}' "$TOML_FILE" \
    | grep -v '^\s*#' \
    | sed 's/^\s*"\(.*\)",\?\s*$/\1/' \
    | sed 's|^\*\*/||'
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
