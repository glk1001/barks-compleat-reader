#!/usr/bin/env bash
# Check the censorship-fixes CSV against the story tables and the on-disk fixes trees
# (the check-censorship-csv pre-push hook).
#
# The data is here (barks-fantagraphics/data) but the checker is in the sibling
# barks-comic-building repo, so this runs that repo's console script out of its own
# synced venv, not ours. --offline so a push never waits on the network to resolve
# it, and `env -u VIRTUAL_ENV` because pre-commit exports *our* venv, which uv then
# warns it is ignoring - a warning on every push that means nothing is wrong.
#
# Worktrees: the sibling is found beside the main checkout (git's common dir), not
# at "..", which from .claude/worktrees/<name> is the worktrees directory. And that
# venv installs barks-fantagraphics, which holds the CSV, editable from the main
# checkout, so --with-editable puts this checkout's copy first and a worktree checks
# its own CSV. That takes `python -m`: the barks-check-build console script's shebang
# is the sibling venv's own python, which never sees the --with layer. From the main
# checkout it all comes to what it was.
#
# Assumes the sibling repo is checked out and synced (uv sync) beside this one.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
main_checkout="$(dirname "$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir)")"
siblings_dir="$(dirname "$main_checkout")"

exec env -u VIRTUAL_ENV uv run --offline \
    --project "${siblings_dir}/barks-comic-building" \
    --with-editable "${repo_root}/src/barks-fantagraphics" \
    python -m barks_comic_building.build.check_build_comics_integrity \
    --log-level SUCCESS --censorship-only
