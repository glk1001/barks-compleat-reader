# Plan: an overnight run on Windows

<!-- cspell:ignore ntfs iomap Ventoy Mirametrix -->

> Status: **steps 1-3 written 2026-09-30; step 1's clean run and step 3's two nights to
> come.** Saved here so it survives across machines and sessions; do it on the Windows
> laptop. Tick a step off here, with its commit, as it lands.
>
> - Step 1 the runner, by hand: WRITTEN (`scripts/run_overnight_windows.py`). First run by
>   hand, 2026-09-30: every stage ran as meant; the failures were the laptop's, not the
>   runner's (below, "First run"). A clean pass waits on them.
> - Step 2 keeping the machine awake and fit to run: DONE (the runner holds the display;
>   the one-off setup is in `docs/setup.md`, Windows)
> - Step 3 the nightly schedule: WRITTEN (`scripts/windows/register-overnight-task.ps1`);
>   not yet registered, two nights to see
> - Step 4 the validate stage, once the data is there: BLOCKED (the prebuilt comics are on
>   the Ventoy stick, not yet on the laptop; two titles' files have a `?` Windows cannot
>   name, "Two titles Windows cannot name" below)

## Context

`scripts/run_overnight.sh` is Linux-only: it runs its GUI stages on Xvfb, keeps the
machine awake with `systemd-inhibit`, and is bash. On Windows, CI already covers, on every
push: the unit suite without the data pack, the Nuitka build, and a smoke test of that
build that presses Escape (`smoke-test-build.sh`, twice: OpenGL and ANGLE). What CI
cannot cover is the real data pack, the real OpenGL drawing on real hardware, the built
executable doing real work, and long runs.

The GUI suite already runs on Windows by hand: `scripts/run_gui_tests.py`, through
`gui_probe.py`'s Win32 backend (real keys by `SendInput`), one worker in a visible
window, about 13 minutes (`docs/plans/cross-platform-gui-tests.md`, step 3, and
`docs/plans/gui-test-suite.md`, 2026-09-23 and 24). Its first runs found Windows-only bugs
no Linux run could: History and Reading crashed the reader with the JPG panels zip (a
backslash inside a zip member name, 4c173998), a log marker named its page with
backslashes (abe1aa4d), and the fullscreen exit drew the window frame for ~255ms
(1ec76c4c). That class of bug is what a nightly Windows run is for.

**Machine: the Windows laptop**, not the VM. The laptop draws through the reader's normal
OpenGL; the VirtualBox VM needs `--angle` (Direct3D), which does not test that path. The
laptop is also a touchscreen, for later (below).

## The stages

In this order, each logged to `build/overnight/<stamp>/<stage>.log`:

| Stage | What it runs | Why on Windows | Time |
|---|---|---|---|
| `update` | `git pull --ff-only`, `uv sync --locked` | The run tests what is on `main` that night. | 1 min |
| `pytest` | `uv run pytest` with the data pack | CI's Windows leg skips every test that needs it. | 1 min |
| `fetch-build` | CI's `barks-reader-win.exe` for **this checkout's commit** | The built-app stage must test the same code as the others. | 1 min |
| `gui` | `run_gui_tests.py`, the workspace app | Real OpenGL and Windows paths through every screen. | 23 min |
| `built-app` | `run_gui_tests.py --app <exe>` | CI only checks the build starts; packaging bugs (DLLs, onefile paths, zip members) show only when it reads comics. | 20 min |
| `soak` | `run_gui_tests.py --soak`, one seed | A long random walk: crashes, stuck screens, file handles. | 19 min |
| `validate` | `validate-barks-reader-files.py --full-load-check --strict-wiki` | The whole library through Windows paths and zip reading. Skips itself until step 4. | 5 min |

About 65 minutes, in one visible window (the first run's times; the plan guessed 40-45).

- **`fetch-build`** is `scripts/get-win-build.sh`'s logic in Python, with one change: that
  script takes the newest Build Verification run on `main`, but this stage wants the run
  whose head is `git rev-parse HEAD` (`gh run list --commit <sha> --workflow "Build
  Verification"`), waiting for it if it is still building. When there is none, or it
  failed, `fetch-build` fails and `built-app` skips itself, saying why. The artifact goes
  under `build/overnight/<stamp>/`, not over the last night's.
- **The soak seed** comes from the day of the year, as the Linux run's do, but one a night
  rather than three, since one worker runs them one after another
  (`BARKS_OVERNIGHT_SOAK_SEEDS` overrides); 1000 keys (`BARKS_OVERNIGHT_SOAK_STEPS`).
- **A settings variant**, maybe later: one of `run_gui_matrix.sh`'s variants a night
  (virtual keyboard, double page, ...), by weekday, through `--ini key=value`. The whole
  matrix is six more 13-minute suites; one a night covers it in a week.

**Left to Linux, CI or the main machine**, since they behave the same on every platform
or cannot run here: lint, ty, pyrefly, cspell, the wiki checks, random order, dependency
drift, audit, mutation testing, coverage and graphify; `build-check` and the sibling repos'
tests (the main machine's build tree and pipelines); `smoke` (CI's); the GUI timing drift
(the budgets are still held per test by `--calibrate`, step 2).

## Step 1: the runner, by hand

`scripts/run_overnight_windows.py`, Python rather than bash: Git Bash sets `TERM`, which
has loguru colour a log file (ccc3d4f3), and its console is cp1252. The shape follows
`run_overnight.sh`:

- `--list`, `--only`, `--skip`, `--app PATH` (use that exe; no `fetch-build`);
- `build/overnight/<stamp>/summary.txt` in the Linux format, rewritten after every stage
  (passed, FAILED, WARNED, skipped or stopped, and the time), so the two machines' results
  read alike;
- every file read and written names UTF-8 (the harness learnt this the hard way,
  6c05532c);
- a stage that fails does not stop the others, except that nothing runs after a failed
  `update`;
- exit status 0 only when no stage failed.

Before the GUI stages it runs `gui_probe.py doctor` and stops them, with its reasons, if
the screen is locked, the session is a minimized remote one, or the app's window is
already open. `SendInput` reaches none of those.

Done when a run by hand, from PowerShell, passes every stage but `validate` and writes a
summary a Linux run's reader would recognise. Unit tests for the stage table and the
summary format, like `scripts/tests/`'s for the Linux helpers.

## Step 2: keeping the machine awake and fit to run

- **Awake.** During the run, `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED
  | ES_DISPLAY_REQUIRED)`: the Windows `systemd-inhibit`, and the display too, since
  `SendInput` needs a screen that is on and unlocked. Cleared when the run ends, however
  it ends.
- **Unlocked.** The screen must not lock during the night (Settings, Accounts, Sign-in
  options: "If you've been away, when should Windows require you to sign in again?" set
  to Never), and no screen saver with a password. `doctor` catches a locked screen at the
  start; a lock mid-run fails the GUI stage that meets it.
- **Left alone.** A key or a click from anyone goes to the app and fails the test (the
  teardown's STRAY INPUT check names it).
- **Windows Update.** Active hours to cover the run, so it does not restart the machine
  under it.
- **Calibrated.** `run_gui_tests.py --calibrate` once, so the timing budgets are the
  laptop's own.

Add these to `docs/setup.md`'s Windows section as the machine's one-off setup.

## Step 3: the nightly schedule

A Task Scheduler task, nightly (02:00, say), running the runner through `uv run`, set to
**"Run only when user is logged on"**: `SendInput` needs the interactive desktop, which a
task run without a logged-on user does not have. "Wake the computer to run this task" on,
and "Stop the task if it runs longer than" 2 hours, in case a stage hangs. A
`scripts/windows/` export of the task (XML) or a PowerShell line that registers it, so a
second machine is set up the same way.

The results stay on the laptop. Reading them from the main machine (ssh into the laptop,
or the summary pushed somewhere both can see) is a later choice.

## Step 4: the validate stage, once the data is there

`validate-barks-reader-files.py --full-load-check` does not read the comic build tree
(about 330 GB; only `build-check` does), but it does need what `copy-to-overnight-host.sh`
sends a Linux host, about 34 GB:

| Data | Size | Needed by |
|---|---|---|
| The prebuilt comics (`The Comics/Chronological`, the profile's `prebuilt_dir`) | 8.9 GB | Phase 7, always on: every title's prebuilt CBZ must exist |
| The Fantagraphics volumes (the profile's `fanta_dir`) | 9.2 GB | Phase 9, `--full-load-check`: decodes every page |
| The PNG panels | 3.8 GB | the panel phases |
| `Reader Files` | 2.8 GB | everything |

Of `The Comics` (18 GB) the reader reads only `Chronological`: 465 CBZs, one per title,
no symlinks or folders. The rest is views made of symlinks (`Chronological Years/`,
`Comics and Stories/`, ...), which Windows would not follow, and `aaa-Chronological-dirs/`,
the build's per-title folders. On 2026-09-30 `Chronological` went onto the Ventoy stick
(exFAT) as `barks-reader-windows/The Comics/Chronological`: 463 files, byte for byte,
without the two below. An NTFS stick before it crashed the kernel's `ntfs3` driver
(`kernel BUG at fs/iomap/buffered-io.c:1061`, writing a 153-byte file of
`aaa-Chronological-dirs`), so copy to exFAT, with `rsync -rt --modify-window=1`.

On the laptop it goes to `~\Books\Carl Barks\The Comics\Chronological`, where the
profile's `prebuilt_dir` points, beside a junction for `Reader Files` (`docs/setup.md`,
Windows: the code's default root is `~\Books\Carl Barks` on every OS, while the installed
app keeps its files in `~\barks-reader`). Until `Chronological` is there, Phase 7 would
fail on every title. Until then the stage skips
itself, saying which folder is missing, rather than failing every night. (A
`--no-prebuilt` switch for `validate` that skips Phase 7 would let the rest run sooner;
decide when this step comes up.)

### Two titles Windows cannot name

Settle this before the stage can pass. Two stories' prebuilt files have a `?` in their
names, which Windows does not allow in a file name (nor exFAT, nor NTFS as Windows
writes it):

- `319 Fun? What's That? [SF 2].cbz`
- `353 Want to Buy an Island? [WDCS 235].cbz`

The name is the title as `barks_titles` spells it, through
`barks_fantagraphics.comics_utils.get_dest_comic_zip_file_stem` (chronological number,
title, issue). The reader looks a prebuilt comic up by that name
(`ComicBookLoader._get_prebuilt_comic_path`), and so does `validate`'s Phase 7. So on
Windows, with `use_prebuilt_comics` on, these two stories cannot be opened, and Phase 7
reports both missing. The default (`use_prebuilt_comics = 0`) reads them from the
Fantagraphics volumes and is unaffected.

The same function names the files where they are made: `barks-comic-building`'s
`zipping`, `build_comics`, `artifact_renaming` and `comics_integrity` use it. So does the
build's per-title folder under `aaa-Chronological-dirs/`, through
`get_dest_comic_dirname`, though the reader never reads that tree. The ways out:

1. **One name, safe everywhere (recommended).** The stem leaves out the characters
   Windows forbids (`<>:"/\|?*`), on every OS; the title shown in the app keeps its `?`.
   Then rename the two built files (and folders) on the main machine, which
   `artifact_renaming` may already do for renamed titles, and re-sync the other hosts.
   It changes `barks-fantagraphics`' behaviour, so it is a coordinated change with
   `barks-comic-building` (and a check that `barks-ocr` does not build these names).
2. **A second name on Windows only**, looked up when the first is not there. Two names for
   one file is what the one-name rule above avoids; not recommended.
3. **Accept it**: those two stories stay unreadable in Windows prebuilt mode, and Phase 7
   expects them missing on Windows. The cheapest, and it leaves a known hole.

Check first whether any other title, tag or path the app builds from a title carries a
Windows-forbidden character: these two are the only file names under `The Comics` that
do, but the question is the titles, not today's files.

## Later, not in this plan

- **Touch on Windows.** The laptop is a touchscreen, but the Linux touch tests inject
  through `uinput`. Windows would need touch injection (`InjectSyntheticPointerInput`),
  which is new work: see `docs/plans/touch-gui-tests.md`.
- **The settings matrix** in full, beyond one variant a night.

## Verification

- Step 1: a run by hand passes every stage but `validate`; `summary.txt` matches the Linux
  format; the unit tests pass in CI on all three platforms.
- Step 2: a run with the lock screen due mid-run finishes; `powercfg /requests` shows the
  runner's request while it runs and none after.
- Step 3: two scheduled nights in a row, results read the next morning; one night with a
  deliberately failing test shows FAILED and keeps its artifacts.
- Step 4: once the data is copied, `validate` passes there as it does on the Linux host.

## First run (2026-09-30)

By hand from PowerShell, in two parts (`pytest,fetch-build,validate`, then
`gui,built-app,soak --app` with the fetched exe). `fetch-build` found and downloaded CI's
build of 5bf601f4 in 38s; `validate` skipped itself (no prebuilt comics). The failures:

- **`pytest`**: two fixture tests in `barks-fantagraphics` want the FANTA_01 override under
  `~\Books\Carl Barks\...` (`comics_consts.BARKS_ROOT_DIR`, fixed); the laptop's data was
  only in the installed app's layout, `~\barks-reader`. Fixed with a junction for
  `Reader Files` there, and the prebuilt comics copied beside it (`docs/setup.md`).
- **The GUI suite, the same six on both apps** (so not packaging): four build a library of
  symlinks, which needs Developer Mode (turned on; the four pass); one tapped a 1963 story
  ("Bubbleweight Champ not in Fanta info"), a title in the index with no Fantagraphics
  volume at all, whose tap rightly opens the volume-not-available popup: the test took
  the first title on screen, which depends on the window. Fixed in `test_taps.py` (only
  titles with a volume are candidates); and the wiki tree test landed on a page, not a
  section, because the wiki opened on the user's last page: a session file left in the
  data dir from before it moved into the profile, which the app copies into any profile
  with none, so into every scratch one. Fixed in the harness
  (`block_legacy_wiki_session`); the leftover moved to `~\barks-reader\old\`. (The
  laptop's wiki copy was also stale, 804 pages, and was re-exported: see below.)
- **Then the whole suite passed**, 2026-09-30 14:00: 98 passed, none skipped (the
  prebuilt-archives test runs now the comics are there), 20 minutes.
- **barks-wiki wrote CRLF on Windows**, fixed there the same day: a clone under
  `core.autocrlf=true` was CRLF (87f71837, a `.gitattributes` forcing LF) and the export
  wrote its rewritten pages without `newline="\n"` (e75af9d4). Tested here: a fresh
  CRLF-default clone and its export are all LF, the export is byte-identical to the
  laptop's copy, and `check_wiki_copy.py` calls it current.
- **The soak**, and then `test_a_doubled_volume_is_fatal...` every time: the blank-frame
  check failed drawn frames. It cropped the window at its screen position (792, 10) out
  of the capture, as out of Linux's whole-screen one, but the Windows probe captures the
  window alone: it judged a 185-pixel strip padded with black, over 81% black before the
  app drew a thing. Fixed in `barks_gui.shots` (a window-sized capture is not cropped).
- **Found on the way, fixed**: the screen locked 90s after the last input, whatever
  Windows said: LG Glance by Mirametrix's Walk Away Lock (removed), and behind it the
  hidden 240s non-sensor presence timeout (`docs/setup.md`). The runner's display hold
  alone would not have stopped the first.
