#!/bin/bash
# Bring a sibling repo up to its upstream, as the main repo is pulled before a run.
#
# Nothing else pulls the sibling repos on an overnight machine, and one left behind
# fails the siblings stage on a name this repo has since changed: on 2026-10-05 the
# Linux overnight machine's barks-comic-building was six days old and its type checks
# failed on two title-search methods this repo had dropped and the sibling had stopped
# calling that morning.
#
# Only a repo that is behind its upstream, has not diverged from it and has no
# uncommitted changes to tracked files is moved, by a fast-forward; anything else is
# left as it is and said, so a session working in the sibling never has its work
# pulled from under it.
#
# Usage: pull_sibling.sh REPO
# Exit: 0 up to date or fast-forwarded; 1 left as it is (the reason on stdout).

set -uo pipefail

repo="${1:?usage: pull_sibling.sh REPO}"
name="$(basename "$repo")"
git=(git -C "$repo")

if ! "${git[@]}" fetch --quiet 2>/dev/null; then
    echo "siblings: ${name}: could not fetch; tested as it is"
    exit 1
fi
if ! "${git[@]}" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    echo "siblings: ${name}: its branch has no upstream; tested as it is"
    exit 1
fi
behind="$("${git[@]}" rev-list --count 'HEAD..@{u}')"
ahead="$("${git[@]}" rev-list --count '@{u}..HEAD')"
if ((behind == 0)); then
    echo "siblings: ${name}: up to date"
    exit 0
fi
if ((ahead > 0)); then
    echo "siblings: ${name}: ${behind} commit(s) behind and ${ahead} ahead of its upstream" \
        "(diverged); not pulled, tested as it is"
    exit 1
fi
if [[ -n "$("${git[@]}" status --porcelain --untracked-files=no)" ]]; then
    echo "siblings: ${name}: ${behind} commit(s) behind, with uncommitted changes;" \
        "not pulled, tested as it is"
    exit 1
fi
if ! "${git[@]}" merge --ff-only --quiet '@{u}' 2>/dev/null; then
    echo "siblings: ${name}: ${behind} commit(s) behind, but the fast-forward failed;" \
        "tested as it is"
    exit 1
fi
echo "siblings: ${name}: pulled ${behind} commit(s), now at $("${git[@]}" log -1 --format='%h %s')"
