# Setting up a machine

<!-- cspell:ignore xsel libgl libmtdev graphifyy setacvalueindex setactive Mirametrix Winlogon wikitext waketimers -->

What a clean machine needs, in the order to do it, for either of two jobs:

- **a development machine**: run the app from source, run the tests and the gates, build
  the standalone executable;
- **an overnight host**: a second machine that runs `scripts/run_overnight.sh --skip
  build-check`, set up over ssh from the main one.

Most steps are the same for both; the ones only one of them needs say so. It is written for
Ubuntu (26.04 LTS is what the overnight host runs); Windows and macOS are at the end. The
checks in the last step say what is still missing, so a step skipped here shows up there.

## 1. System packages

```bash
sudo apt install git-lfs build-essential gh tmux \
    xvfb xserver-xephyr xautomation x11-utils imagemagick xclip xdotool
```

| Package | What needs it |
|---|---|
| `git-lfs` | `comic_utils/cpi.db` is stored in LFS; without it the file is a small pointer and the payment tables fail. |
| `build-essential` | The C compiler Nuitka builds the standalone executable with (`scripts/build.sh`, the overnight `build` stage). CI also installs `patchelf` and `ccache`: the build ran without `patchelf` on Ubuntu 26.04, and `ccache` only makes rebuilds faster. |
| `gh` | The GitHub CLI: CI status, and `get-win-build.sh`, `upload-data-zips.sh` and `upload-website-videos.sh`. Run `gh auth login` once. |
| `tmux` | Keeps an overnight run going when the ssh session that started it drops. Optional. |
| `xvfb` | The headless GUI tests (`run_gui_tests.sh --headless`), everything the overnight run does on a display, and the benchmark baseline over ssh. |
| `xserver-xephyr` | The GUI tests in a window, on the desktop (`run_gui_tests.sh` without `--headless`), and the `verify` skill. Development machine only; an overnight host runs headless. |
| `xautomation` | `xte`, which the GUI tests press keys with. |
| `x11-utils` | `xdpyinfo` and `xwininfo`, which the GUI probe uses to find the app's window. |
| `imagemagick` | `import` and `convert`: a GUI test's screenshots and final frame. |
| `xclip` | Kivy's X clipboard (`xsel` also does). Without either, Kivy logs a critical line at every boot and every GUI test fails its clean-log check. |
| `xdotool` | The smoke stage presses Escape in the built app with it. `gui-probe.sh doctor` calls it optional, since the GUI tests use `xte`, but the overnight smoke stage fails without it. |

A desktop install already has the OpenGL and input libraries Kivy loads. On a server or
minimal image, add `libgl1 libmtdev1t64`, as CI does.

## 2. User tools

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv: Python, the venv, every dependency
sudo apt install just                                     # or: the installer in README.md
curl -fsSL https://bun.sh/install | bash                  # bun: runs cspell (bunx cspell)
uv tool install graphifyy==0.9.20                         # graphify; the package has two y's
```

- **uv** installs Python itself (the version `.python-version` names), so no system Python
  setup is needed.
- **bun** is what the cspell hooks and `full-lint.sh` run cspell with. Without it every
  commit fails its spell-check hook.
- **graphify** keeps `graphify-out/` current. It is optional: the overnight `graphify`
  stage skips itself without it, and `check-overnight-host.sh` only advises it.

These go in `~/.local/bin` and `~/.bun/bin`. A shell started by `ssh host 'command'`
does not read the interactive part of `~/.bashrc`, so if something is to run over ssh
without a login shell, put both directories on `PATH` where that shell will see them
(`~/.profile`, or above the interactive check in `~/.bashrc`).

## 3. The repositories

The four repositories sit beside each other, since the scripts find the others at `..`:

```bash
mkdir -p ~/Prj/github/barks-compleat-digital && cd ~/Prj/github/barks-compleat-digital
for repo in barks-compleat-reader barks-comic-building barks-ocr barks-wiki; do
    git clone "https://github.com/glk1001/${repo}.git"
done
git lfs install
(cd barks-compleat-reader && git lfs pull && uv sync)
(cd barks-comic-building && uv sync)
(cd barks-ocr && uv sync)
```

`barks-comic-building`'s venv is used from here too: the censorship-fixes pre-push hook
runs its checker (`scripts/check-censorship-csv.sh`), and the overnight `siblings` stage
runs its tests. `barks-wiki` is read-only from this repository (see `CLAUDE.md`).

On an overnight host, `scripts/copy-to-overnight-host.sh HOST`, run on the main machine,
does this step and steps 5 and 6 over ssh: see "On another machine" in `README.md`.

## 4. The git hooks

```bash
cd barks-compleat-reader
uv run prek install
```

prek is not a system package: `uv sync` installs it into `.venv` from the `dev`
dependency group. This one command writes all three hooks (pre-commit, pre-push with the
full suite, commit-msg with cspell). `git lfs install` also claims the pre-push slot, so
run `prek install` after it, never before; prek then keeps the LFS hook as
`pre-push.legacy` and chains to it. To check, `.git/hooks/pre-push` should name
`--hook-type=pre-push`, and `.git/hooks/pre-push.legacy` should hold `git lfs pre-push`.

## 5. Secrets and the generated modules

`.env.runtime` (gitignored) holds the key that decrypts the comic archives and where the
app's profile and data live:

```
BARKS_ZIPS_KEY=...
BARKS_READER_CONFIG_DIR=...
BARKS_READER_DATA_DIR=...
```

Copy its `BARKS_` lines from the main machine. Then generate the two gitignored modules
every workspace boot imports:

```bash
bash scripts/generate-panel-module.sh   # comic_utils/get_panel_bytes.py; needs BARKS_ZIPS_KEY
bash scripts/build.sh                   # barks_reader/_version.py (its first step writes it)
```

Without them the app dies on an import at boot, and ty, pyrefly and `full-lint.sh` refuse
to run. Running the app does not create either.

## 6. The data

The reader's files (panel zips, indexes, fonts, the shipped wiki copy) go under
`$BARKS_READER_DATA_DIR/Reader Files`, and the Fantagraphics volumes under
`~/Books/Carl Barks/Fantagraphics-original`. The `siblings` stage checks every volume's
folder there. `copy-to-overnight-host.sh` copies all of it (about 36 GB) but not the comic
build tree (about 330 GB), which is why an overnight host runs with `--skip build-check`.

## 7. Optional system rules

**Touch tests** (`run_gui_tests.sh --touch`, the overnight `touch` stage). A udev rule lets
the test's virtual touchscreen be created, and stops the desktop from using it:

```bash
sudo cp scripts/udev/70-barks-gui-touch.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --action=change --sysname-match=uinput
```

Without it the overnight `touch` stage skips itself.

**Sleep during an overnight run started over ssh.** The run keeps the machine awake with
`systemd-inhibit`, which asks for a password when started from a remote session. The
stages go on meanwhile, but the machine may sleep. A polkit rule for the one user stops
the question. Write it as root, from a terminal on that machine (`pkexec` over ssh has no
password agent):

```
// /etc/polkit-1/rules.d/49-<user>-inhibit-sleep.rules
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.login1.inhibit-block-sleep" ||
         action.id == "org.freedesktop.login1.inhibit-block-idle") &&
        subject.user == "<user>") {
        return polkit.Result.YES;
    }
});
```

`ssh host 'systemd-inhibit --what=sleep:idle sleep 1'` then returns without asking.

## 8. One-off measurements

The lint stage compares the benchmarks against a baseline, and the GUI tests hold each
logged duration to budgets calibrated per machine. Record both once, on the machine
itself (over ssh there is no display, so both run on Xvfb):

```bash
xvfb-run -a bash scripts/record_benchmark_baseline.sh
bash scripts/run_gui_tests.sh --headless --calibrate
```

Both are machine-local (`.benchmarks/`, gitignored). Until the calibration is done, the
committed budgets, measured on the main machine, apply.

## 9. Check it

```bash
bash scripts/check-overnight-host.sh                    # repos, .env.runtime, data, tools, the probe
BARKS_PROBE_HEADLESS=1 bash scripts/gui-probe.sh doctor  # the GUI-test tools, with apt package names
bash scripts/gui-probe.sh doctor                         # the same with a window, on a desktop
gh auth status
```

`check-overnight-host.sh` exits 0 when everything required is there and lists what is
missing otherwise; what it only advises (graphify, the touch rule, the calibration) never
fails it. It checks an overnight host's needs, which a development machine shares.

## Windows and macOS

Both run the app, the unit tests and the build. Windows also runs the GUI tests
(`scripts/run_gui_tests.py`, one worker in a visible window) and its own overnight run
(`scripts/run_overnight_windows.py`; plan and stages in `docs/plans/windows-overnight.md`).

- **Windows.** uv from its installer, bun with `winget install Oven-sh.Bun`. That package
  has no `bunx`: beside `bun.exe`, add a `bunx.cmd` holding `@"%~dp0bun.exe" x %*`. After
  `prek install`, change `.git/hooks/pre-push.legacy`'s first line from `#!/bin/sh` to
  `#!/usr/bin/env sh`, or every push fails with "Executable `/bin/sh` not found".
  (Both were found under pre-commit and not yet re-checked under prek; see `CLAUDE.md`.)
  The standalone app's own install steps are in `README.md`.
- **A Windows overnight machine**, once, besides the above. `uv run python
  scripts/check_windows_overnight_host.py` checks every step below and says what is
  still missing (the Windows `check-overnight-host.sh`); run it last, and again after a
  Windows update.
  - **Tools**: Git for Windows (its Git Bash, which runs the repo's `bash` scripts, and
    git-lfs), `winget install GitHub.cli` then `gh auth login` (the `fetch-build` stage),
    uv and bun as above. Then steps 3 to 5 above as written, in Git Bash: the clone
    (with `git lfs install` before it), `uv sync`, `prek install`, `.env.runtime` and the
    two generated modules.
  - **The reader's data**: the installer's data packs into `~\barks-reader` (the
    standalone install in `README.md`), which gives `Reader Files`; `.env.runtime`'s
    `BARKS_READER_DATA_DIR` at `~/barks-reader` and `BARKS_READER_CONFIG_DIR` at
    `~/barks-reader/config`; the Fantagraphics volumes wherever the profile's `fanta_dir`
    says (here `~\Documents\Fantagraphics Complete Carl Barks Disney Library`).
  - **The wiki copy**, refreshed from barks-wiki: clone it beside this repo with LF line
    endings (`git clone -c core.autocrlf=false https://github.com/glk1001/barks-wiki.git`),
    then from its root `..\barks-compleat-reader\.venv\Scripts\python.exe -B
    scripts\export_reader_wiki.py "$HOME\barks-reader\Reader Files\Carl Barks Wiki" --apply
    --clean`. The export writes CRLF on Windows (to be fixed there), so put the copy back
    to LF afterwards (all text: pages, a `.py`, a `.tsv`, a `.wikitext`; the host check
    warns while they are CRLF), from this repo's root:
    ```powershell
    .venv\Scripts\python.exe -c "from pathlib import Path; [p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n')) for p in Path(r'$HOME\barks-reader\Reader Files\Carl Barks Wiki').rglob('*') if p.is_file()]"
    ```
    `check_wiki_copy.py` on Windows calls the LF copy stale until the export is fixed.

  The GUI stages inject real keys, which reach only an unlocked screen that is on, so
  nothing may blank or lock it overnight:
  - **Sign-in when away: Never** (Settings, Accounts, Sign-in options, "If you've been
    away, when should Windows require you to sign in again?"). It also decides whether a
    wake from standby lands on the lock screen, which fails every GUI stage.
  - **No screen saver with a password**, and the display and sleep timeouts on AC longer
    than a run (the runner holds the display on while it runs, but the scheduled task
    wakes a machine that slept before it).
  - **On a laptop without a presence sensor**, the hidden "Non-sensor Input Presence
    Timeout" (240 s) turns the display off, and a Modern Standby machine then goes to
    standby: `powercfg /setacvalueindex SCHEME_CURRENT
    8619b916-e004-4dd8-9b66-dae86f806698 5adbbfbc-074e-4da1-ba38-db8b36b2c8f3 10800`, then
    `powercfg /setactive SCHEME_CURRENT` (PowerShell; in `cmd`, two lines).
  - **No webcam presence software.** The LG laptop came with LG Glance by Mirametrix, whose
    Walk Away Lock locked the session 90 seconds after the last input, whatever Windows'
    own settings said; it was removed (`Get-AppxPackage *Glance* | Remove-AppxPackage`).
    To find the like on another machine: the Winlogon/Operational log's event 4 (a lock)
    comes before Kernel-Power's display-off (566, reason 12), not after it.
  - **Developer Mode** (Settings, System, For developers): four GUI tests build a
    library of symlinks, which Windows lets a user make only in Developer Mode (else
    `WinError 1314`, "A required privilege is not held by the client").
  - **Awake at 02:00**: on AC power (on battery the CPU throttles and the timing budgets
    can fail), and "Allow wake timers" on for AC (Control Panel, Power Options, the plan's
    advanced settings, Sleep; `powercfg /waketimers` lists the task's once registered), or
    the task cannot wake a machine that went to standby.
  - **Windows Update's active hours** covering the run, so it does not restart under it.
  - **Calibrated**: `uv run python scripts/run_gui_tests.py --calibrate` once, so the
    timing budgets are this machine's.
  - **The nightly task**: `powershell -ExecutionPolicy Bypass -File
    scripts\windows\register-overnight-task.ps1` (02:00; `-At` for another time).
  - **The data under `~\Books\Carl Barks`**, the Linux machines' layout. The code's
    default root is there (`barks_fantagraphics.comics_consts.BARKS_ROOT_DIR`, fixed: the
    unit suite's override tests read it), and so is the profile's `prebuilt_dir`. The
    installed app keeps `Reader Files` in `BARKS_READER_DATA_DIR` instead
    (`~\barks-reader`), so bridge the two with a junction rather than a second copy:
    ```powershell
    $d = "$HOME\Books\Carl Barks\Compleat Barks Disney Reader"
    New-Item -ItemType Directory -Force $d
    New-Item -ItemType Junction -Path "$d\Reader Files" -Target "$HOME\barks-reader\Reader Files"
    ```
    The prebuilt comics (`The Comics\Chronological`, 8.9 GB, from the stick; see the plan's
    step 4) are copied to `~\Books\Carl Barks\The Comics`, where `prebuilt_dir` points:
    `robocopy "<stick>\barks-reader-windows\The Comics" "$HOME\Books\Carl Barks\The Comics" /E`.
- **macOS.** Only CI runs it (`.github/workflows/`), which installs `ccache` with Homebrew
  for the build.
