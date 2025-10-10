echo Ruff checking uncommited python files:

echo
git diff --name-only --diff-filter=ACMRTUXB HEAD | grep '\.py$'

echo
git diff --name-only --diff-filter=ACMRTUXB HEAD | grep '\.py$' | xargs uvx ruff check

