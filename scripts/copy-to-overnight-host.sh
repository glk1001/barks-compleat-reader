#!/usr/bin/env bash
#
# Set up another machine, over ssh, to run scripts/run_overnight.sh.
#
# Run it here, on the main machine. On the other one (HOST, anything ssh takes:
# user@host or an alias) it:
#   1. clones the four repos from GitHub into the same folder under its home as
#      here (git-lfs first, for cpi.db), and runs uv sync in the three with a
#      Python project; a repo already there is left alone - pull it yourself;
#   2. writes .env.runtime with only its BARKS_ lines (the comic archives' key
#      and the reader's folders), mode 600, unless one is already there;
#   3. copies the data the overnight run reads, each folder to the same path
#      under that machine's home. A folder that is a symlink here (into
#      /mnt/2tb_drive) arrives as a real folder there; Reader Files, a link into
#      the Books tree, is made a link again. rsync, so a rerun copies only what
#      changed, and an interrupted copy resumes;
#   4. rewrites the absolute paths in the profile's barks-reader.ini to that
#      machine's home, when its home is not this one's;
#   5. runs scripts/check-overnight-host.sh there, which says what is still missing.
#
# Not copied: the comic build tree (about 330 GB) - that machine runs with
# --skip build-check; .benchmarks (this machine's timings: calibrate there with
# run_gui_tests.sh --calibrate); the profile's Kivy logs.
#
# Assumes: that machine has git, git-lfs, rsync and uv, and can clone the repos
# from GitHub. It needs about 36 GB free under its home.
#
# Usage: scripts/copy-to-overnight-host.sh [--dry-run] [--no-repos] [--no-data] HOST
#   --dry-run   say what would be done and copied; change nothing there
#   --no-repos  skip steps 1 and 2 (the repos and .env.runtime)
#   --no-data   skip steps 3 and 4 (the data and the profile)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPOS=(barks-compleat-reader barks-comic-building barks-ocr barks-wiki)
SYNCED_REPOS=(barks-compleat-reader barks-comic-building barks-ocr)

# What the overnight run reads beyond the repos, as paths under the home folder
# (found by tracing the stages' file opens): the prebuilt comics, the PNG panels,
# the Fantagraphics volumes (the profile's fanta_dir), the reader's own files, and
# the profile itself.
DATA=(
    "Books/Carl Barks/The Comics"
    "Books/Carl Barks/Barks Panels Pngs"
    "Books/Carl Barks/Compleat Barks Disney Reader"
    "Documents/Fantagraphics Complete Carl Barks Disney Library"
    "opt/barks-reader/config"
)
# Links to make there, as here: path under home -> target under home.
LINKS=(
    "opt/barks-reader/Reader Files|Books/Carl Barks/Compleat Barks Disney Reader/Reader Files"
)
INI="opt/barks-reader/config/barks-reader.ini"

dry_run=""
repos=1
data=1
while [[ "${1:-}" == --* ]]; do
    case "$1" in
    --dry-run) dry_run=1 ;;
    --no-repos) repos="" ;;
    --no-data) data="" ;;
    *)
        echo "copy-to-overnight-host: unknown option $1" >&2
        exit 2
        ;;
    esac
    shift
done
host="${1:?usage: copy-to-overnight-host.sh [--dry-run] [--no-repos] [--no-data] HOST}"

say() { echo "copy-to-overnight-host: $*"; }

# Run a shell command on the host (a dry run only shows the ones that change it).
# A command ssh runs gets a bare PATH: the startup files that add the per-user tool
# folders (uv's installer uses ~/.local/bin, bun ~/.bun/bin) are not read, so a
# tool installed there looked missing. Every command puts them on PATH first.
REMOTE_PATH='export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"'
remote() { ssh "$host" "${REMOTE_PATH}; $1"; }
change() {
    if [[ -n "$dry_run" ]]; then
        echo "  would run there: $1"
    else
        remote "$1"
    fi
}
# Quote a value for the host's shell.
q() { printf '%q' "$1"; }

# Where the repos live, relative to home, as here.
parent_rel="${REPO_ROOT%/*}"
parent_rel="${parent_rel#"$HOME"/}"
[[ "$parent_rel" != /* ]] || {
    say "the repos are not under your home folder ($REPO_ROOT); cannot mirror them"
    exit 2
}

remote_home="$(remote 'printf %s "$HOME"')"
say "$host: home is $remote_home"
missing_tools="$(remote 'for t in git git-lfs rsync uv; do command -v "$t" >/dev/null || printf "%s " "$t"; done')"
if [[ -n "$missing_tools" ]]; then
    say "$host lacks: $missing_tools- install them there first"
    exit 1
fi
parent="${remote_home}/${parent_rel}"

if [[ -n "$repos" ]]; then
    say "1. the repos, in $parent"
    change "git lfs install --skip-repo >/dev/null && mkdir -p $(q "$parent")"
    for repo in "${REPOS[@]}"; do
        url="$(git -C "${REPO_ROOT}/../${repo}" remote get-url origin)"
        if remote "test -d $(q "${parent}/${repo}/.git")"; then
            say "   ${repo}: already there, left alone"
        else
            change "git clone --quiet $(q "$url") $(q "${parent}/${repo}")"
        fi
    done
    for repo in "${SYNCED_REPOS[@]}"; do
        change "cd $(q "${parent}/${repo}") && env -u VIRTUAL_ENV uv sync --frozen --quiet"
    done

    say "2. .env.runtime (its BARKS_ lines only)"
    env_file="${parent}/barks-compleat-reader/.env.runtime"
    if remote "test -f $(q "$env_file")"; then
        say "   already there, left alone"
    elif [[ -n "$dry_run" ]]; then
        echo "  would write there: $env_file, from $(grep -c '^BARKS_' "${REPO_ROOT}/.env.runtime") BARKS_ lines"
    else
        grep '^BARKS_' "${REPO_ROOT}/.env.runtime" |
            remote "umask 077 && cat > $(q "$env_file")"
    fi

    # Two gitignored modules every workspace boot imports: a fresh clone has neither,
    # and without them each GUI test dies at boot. The panel module needs the key
    # just written; _version.py is written as build.sh writes it (the overnight
    # build stage rewrites it each night).
    say "   the generated modules"
    reader="${parent}/barks-compleat-reader"
    change "cd $(q "$reader") && { test -f src/comic-utils/src/comic_utils/get_panel_bytes.py || bash scripts/generate-panel-module.sh; }"
    change "cd $(q "$reader") && { test -f src/barks-reader/src/barks_reader/_version.py || printf 'COPYRIGHT_YEARS = \"2025-2026\"\n\nVERSION = \"%s\"\n' \"\$(git describe --tags --dirty --always)\" > src/barks-reader/src/barks_reader/_version.py; }"
fi

if [[ -n "$data" ]]; then
    say "3. the data"
    rsync_opts=(-a --partial --info=progress2 --protect-args --exclude "kivy/logs/")
    for rel in "${DATA[@]}"; do
        # Resolve a symlinked folder here, so its contents are what is copied.
        src="$(readlink -f "${HOME}/${rel}")"
        dest="${remote_home}/${rel}"
        say "   ${rel}  ($(du -sh "$src" | cut -f1))"
        if [[ -z "$dry_run" ]]; then
            remote "mkdir -p $(q "$dest")"
            rsync "${rsync_opts[@]}" "${src}/" "${host}:${dest}/"
        elif remote "test -d $(q "$dest")"; then
            rsync "${rsync_opts[@]}" --dry-run --stats "${src}/" "${host}:${dest}/" |
                grep -E '^(Number of regular files transferred|Total transferred file size)'
        else
            echo "  would copy all of it to ${dest}"
        fi
    done
    for link in "${LINKS[@]}"; do
        name="${remote_home}/${link%%|*}"
        target="${remote_home}/${link#*|}"
        # A real folder there (an older install's Reader Files) would get the link
        # put inside it by ln, and the app would go on reading the old folder: it is
        # moved aside, not deleted, and said so.
        if remote "test -d $(q "$name") && ! test -L $(q "$name")"; then
            aside="${name}.before-copy-$(date +%Y%m%d-%H%M%S)"
            say "   ${name} is a folder there, not a link: moving it to ${aside}"
            change "mv $(q "$name") $(q "$aside")"
        fi
        change "mkdir -p $(q "$(dirname "$name")") && ln -sfn $(q "$target") $(q "$name")"
    done

    say "4. the profile's paths"
    if [[ "$remote_home" == "$HOME" ]]; then
        say "   same home there; nothing to rewrite"
    else
        change "sed -i $(q "s#${HOME}/#${remote_home}/#g") $(q "${remote_home}/${INI}")"
    fi
fi

say "5. what is still missing there"
if [[ -n "$dry_run" ]]; then
    echo "  would run there: bash scripts/check-overnight-host.sh"
elif remote "test -d $(q "${parent}/barks-compleat-reader")"; then
    remote "cd $(q "${parent}/barks-compleat-reader") && bash scripts/check-overnight-host.sh" || true
else
    say "   no checkout of barks-compleat-reader there yet (run without --no-repos)"
fi
