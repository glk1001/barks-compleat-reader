---
name: overnight-runs
description: Run, set up, check or debug the overnight runs (run_overnight.sh on Linux, run_overnight_desktop.py on Windows and macOS, other machines over ssh, cross-platform coverage) — stages, options, results and the macOS permission gotchas.
---

# Overnight runs

**Run the whole repo overnight** (the data-pack validators, full-lint, the suite with coverage,
in random order and against upgraded dependencies, the sibling repos' tests, a Nuitka build and
its smoke test, every GUI stage below against that build, GUI timing drift, unused code that
nothing ran (`dead_code_report.py`, warns only), mutation testing of all of `core/` and the
fantagraphics search modules (`BARKS_OVERNIGHT_MUTATION_SCOPE=core` or `fantagraphics` gives a
machine one share, kept in its gitignored `.env.overnight`), and last `tidy`: the built app's old
unpack folders (`prune_onefile_cache.py`, the newest three kept) and `uv cache prune`, warns
only, the desktop runner's last stage too; `--list`, `--only`, `--skip`, `--app PATH`; results in
`build/overnight/<stamp>/summary.txt`, where a warn-only stage shows WARNED):
```bash
bash scripts/run_overnight.sh
```
To run it on another machine, `bash scripts/copy-to-overnight-host.sh [--dry-run] [--no-repos] [--no-data] HOST`
sets that one up over ssh (repos, `.env.runtime`'s `BARKS_` lines, about 36 GB of data;
not the build tree, so it runs with `--skip build-check`), and
`bash scripts/check-overnight-host.sh` there says what is still missing.
For another distro, `bash scripts/run_overnight_container.sh fedora` runs a slice (the suite,
a build made there, the base GUI suite, and a smoke test of the host's build) in a podman
container on the second Linux PC, on demand (`docs/overnight-schedule.md`, "Another distro").
Each machine's data pack is a copy that nothing re-syncs, and a stale one passes every other
stage. So both runners start with `data`: `scripts/data_manifest.py` compares the Reader Files
folders, prebuilt comics and PNG panels there with `scripts/data-manifest.json`, and warns
naming each folder that differs. After changing data on the main PC, run
`uv run scripts/data_manifest.py --write` and commit the manifest (its own `data` stage
warns until then), then copy the changed folders to every machine.
On Windows or macOS, `uv run python scripts/run_overnight_desktop.py` (same options and
summary) runs what only a desktop machine can: the suite with the data pack, the GUI suite
on the workspace app and (Windows only, so far) on CI's build of this commit, a soak,
`validate`, the wiki copy's freshness (barks-wiki pulled first, where safe), and the coverage of what only that platform runs; on Windows nightly through
the wake, run and sleep task in `docs/overnight-schedule.md` (which schedules the Linux
machines too, and lists the commands to run, watch, stop and pause each one;
`scripts/windows/register-overnight-task.ps1` is the simpler alternative), and
`uv run python scripts/check_windows_overnight_host.py` (on a Mac,
`scripts/check_macos_overnight_host.py`) says what a machine still lacks for it (setup: `docs/setup.md`, Windows and "A macOS overnight machine", a clean Mac's checklist).
Plan: `docs/plans/windows-overnight.md`. On a Mac, start it
on the Mac's own desktop, not over ssh, from an app holding the probe's Accessibility and
Screen Recording permissions (`docs/plans/macos-gui-tests.md`). macOS grants them to the app
that started the process: Terminal for a run typed in Terminal, but for one Claude Code starts,
`~/.local/share/claude/ClaudeCode.app` (`com.anthropic.claude-code`), which Claude Code runs
through since 2.1 as a background process that outlives `/exit`. Check first with
`uv run python scripts/gui_probe.py doctor`: with either permission missing every GUI stage is
"not run". To grant them, add the app under System Preferences, Security & Privacy, Privacy,
Accessibility and Screen Recording (`+`, then Cmd-Shift-G and the path: dragging the app in
from its hidden folder did not take). On the guest on 2026-10-02, a process in a Claude Code
shell asking for them (`AXIsProcessTrustedWithOptions` with its prompt option, then a screen
capture) was what got ClaudeCode.app both, with no restart. Screen Recording can need the
app restarted, which for ClaudeCode.app means quitting every Claude Code session.
Pull before starting it (`git pull --ff-only; uv run python scripts/run_overnight_desktop.py`):
its `update` stage pulls too, but the runner is loaded by then, so a pull that changes the
runner itself takes effect only on the next run (on 2026-10-01 a run started that way lacked
the new coverage stage). The nightly task `register-overnight-task.ps1` registers does
not pull first; the one in `docs/overnight-schedule.md` does.
`uv run python scripts/coverage_all_platforms.py LINUX_HOST WINDOWS_HOST [MACOS_HOST]`
combines the machines' coverage of the newest commit all ran overnight (`--commit`), or of
commits with the same `src/` tree, reported against that source: each platform, all
together, and what only each desktop platform ran (report only).
