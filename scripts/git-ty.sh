echo Ty checking uncommited python files:

echo
git diff --name-only --diff-filter=ACMRTUXB HEAD | grep '\.py$'

echo
git diff --name-only --diff-filter=ACMRTUXB HEAD | grep '\.py$' | xargs uv run ty check --respect-ignore-files

