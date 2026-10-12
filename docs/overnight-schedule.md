# The nightly schedule: wake, run, sleep

<!-- cspell:ignore gmktec gregspc runuser nmcli conhost journalctl OptiPlex lastwake -->

Each overnight machine wakes itself from sleep at **01:00**, pulls this repo, runs its
overnight run, and goes back to sleep, but only if it woke up for the run. A machine
already in use at 01:00 runs it and stays awake. The machinery lives outside the repo,
on each machine:

| Machine | Job (edit this) | Runs | Limit | Job output |
|---|---|---|---|---|
| The main machine (gregspc2) | `~/bin/nightly-job` | `git pull --ff-only`, then `scripts/run_overnight.sh` (with `build-check`: the build tree is here) | 5 h | `journalctl -u nightly-job` |
| The overnight host (gmktec) | `~/bin/nightly-job` | `git pull --ff-only`, then `scripts/run_overnight.sh --skip build-check` | 5 h | `journalctl -u nightly-job` |
| The Windows laptop (win_lg) | `~\nightly-job\nightly-job.ps1` | `git pull --ff-only`, then `uv run --offline scripts/run_overnight_desktop.py` | 3 h | `~\nightly-job\nightly-job.log` |
| The Windows desktop (greg-dell; schedule off for now) | `~\nightly-job\nightly-job.ps1` | the same as the laptop's | 5 h | `~\nightly-job\nightly-job.log` |

A run's results are where they always are: `build/overnight/<stamp>/summary.txt`. A
failed pull does not stop the run: it tests the checkout as it is, and on Windows the
runner's `update` stage records the failure in the summary (on Linux it shows only in
the job output). Pulling first, rather than leaving it to the runner, means a pull that
changes the runner itself takes effect the same night.

On the main machine the run tests the working checkout as it is at 01:00, uncommitted
work included.

## Linux: the main machine and the overnight host

A systemd timer with `WakeSystem=true` (`nightly-job.timer`) sets the hardware clock's
wake alarm and starts `nightly-job.service`, which runs `/usr/local/sbin/nightly-job-run`
as root. That wrapper decides whether the machine woke for the run (the kernel logged a
resume, `PM: suspend exit`, in the last 5 minutes), waits up to 60 s for NetworkManager
to report `connected` (not `nm-online`, which counts docker and tailscale interfaces and
returns before the wired link is up), runs the job as `greg` under `systemd-inhibit` and
`timeout`, and suspends again if it woke for it. The setup, with its own README, is in
`~/nightly-job-setup/`.

| To | Run |
|---|---|
| Run it now (stays awake afterwards) | `sudo systemctl start --no-block nightly-job` |
| Watch it | `journalctl -u nightly-job -f` |
| See whether it is running | `systemctl is-active nightly-job` (`activating` while it runs) |
| Stop it | `sudo systemctl stop nightly-job` |
| See the next scheduled run | `systemctl list-timers nightly-job.timer` (no line: off) |
| Turn the schedule off | `sudo systemctl disable --now nightly-job.timer` |
| Turn it back on | `sudo systemctl enable --now nightly-job.timer` |
| Skip tonight only | `sudo systemctl stop nightly-job.timer` (back after a reboot or `start`) |
| Test the wake, sleep and wake again | `sudo bash ~/nightly-job-setup/test.sh` |
| Install, or reinstall after changing the wrapper or units | `sudo bash ~/nightly-job-setup/install.sh` |

From another machine, prefix with `ssh -t <host> '...'`. Without `--no-block`,
`systemctl start` waits for the whole run.

- **Stopping** ends every process the service started (the runner, the app, Xvfb).
  `summary.txt` lists only the stages that finished. Stopped during `dep-drift`, the
  run may leave `uv.lock` modified: `git checkout uv.lock`.
- **Turning the schedule off** does not stop a run already going, and a run can still be
  started by hand.
- **`test.sh`** schedules a wake 3 minutes ahead and suspends the machine; with the real
  job in place it starts a real run. The machine goes back to sleep within seconds of
  the job ending, so a short job's wake is easy to miss: the journal shows it.
- **The job's environment**: cwd `/`, `HOME` set, the system `PATH` only (the job adds
  `~/.local/bin` for uv), no desktop session. The runner's own `systemd-inhibit` fails
  without the polkit rule in `docs/setup.md`, harmlessly: the wrapper's inhibitor already
  holds off sleep.

## Windows: the laptop

A Task Scheduler task, `nightly-job`, daily at 01:00 with "Wake the computer to run this
task", as `gregg` and only while gregg is logged on (no stored password; locked or in
standby is fine). It runs `~\nightly-job\nightly-job-run.ps1` hidden (`conhost
--headless`), which decides whether the laptop woke for the run (still in Modern
Standby, or Kernel-Power 507 "exiting Modern Standby" in the last 5 minutes), waits up
to 60 s for an Internet connection, runs the job with `SetThreadExecutionState` holding
it awake, and returns to standby if it woke for it. Task Scheduler's own limit (3 h 15
min) backs up the wrapper's 3 h.

**This replaces `scripts\windows\register-overnight-task.ps1`** on the laptop: do not
register that task too, or two runs start in a night.

| To | Run (PowerShell or Git Bash on the laptop) |
|---|---|
| Run it now (stays awake afterwards) | `powershell -Command "Start-ScheduledTask nightly-job"` |
| See whether it is running | `powershell -Command "(Get-ScheduledTask nightly-job).State"` (`Running`, then `Ready`) |
| Stop it | `powershell -Command "Stop-ScheduledTask nightly-job"` |
| See the next scheduled run | `powershell -Command "(Get-ScheduledTaskInfo nightly-job).NextRunTime"` |
| Turn the schedule off | `powershell -Command "Disable-ScheduledTask nightly-job"` |
| Turn it back on | `powershell -Command "Enable-ScheduledTask nightly-job"` |
| Test the wake | `powershell -ExecutionPolicy Bypass -File C:/Users/gregg/nightly-job/test.ps1` |
| Re-register the task | `powershell -ExecutionPolicy Bypass -File C:/Users/gregg/nightly-job/install.ps1` |

From the main machine: `ssh win_lg 'powershell -NoProfile -Command "Start-ScheduledTask
nightly-job"'`. A task started over ssh still runs on the laptop's desktop, which the GUI
stages need. Write paths with forward slashes: the laptop's ssh shell, and Git Bash, is
bash, which eats backslashes.

- **For the run to happen**: on AC (wake timers are off on battery, and on battery the
  CPU throttles), logged on, a browser closed (a GUI stage needs 6 GB free), and nobody
  at the keyboard: a stray key fails the test it lands in. The one-off settings (no
  sign-in after standby, the presence timeout) are `docs/setup.md`'s.
- **Watching**: `nightly-job.log` gets the run's console output only when the job ends;
  the stages' own logs in `build\overnight\<stamp>\` grow as it goes.
- **Stopping** may leave child processes, the reader app or a test still in progress:
  close the app's window if it stays open.
- **`--offline`**: `uv run --offline` syncs from uv's cache only, so a pull that adds a
  package uv has not cached stops the job before the runner starts. `uv run --no-sync`
  would leave the sync to the runner's `update` stage, which may download.
- **Execution policy**: the scripts run with `-ExecutionPolicy Bypass` for that one
  process; the laptop's own policy is left at Windows' default.
- **The wake** on Modern Standby is dark: the screen stays off, so it is easy to miss.
  Windows' wake record (`Power-Troubleshooter` event 1) names the task; Kernel-Power 507
  may give the reason as "Input Mouse" all the same.

## Windows: the desktop (greg-dell)

A Dell OptiPlex 7050 SFF with 8 GB, set up as the laptop is, with the same three
scripts in `~\nightly-job\` adapted to it. Its `nightly-job` task is installed but
**disabled** until the machine has more memory; a second task, `nightly-job-now`, starts
the same run by hand meanwhile. How it differs from the laptop:

- **Classic S3 sleep, not Modern Standby.** The wake is a full one, fans and all. The
  wrapper decides it woke for the run from Kernel-Power 107 ("resumed from sleep") or
  Power-Troubleshooter 1 in the last 5 minutes.
- **Limits**: 5 h in the wrapper, 5 h 15 min in Task Scheduler. The first run
  (2026-10-12, through `test.ps1`) passed in 2h02m: `gui` 48 min, `built-app` 39 min,
  `soak` 24 min.
- **Memory**: about 4 GB of the 8 is free at idle, which is the runner's own floor on a
  machine this size (half its memory), so a GUI stage might not start.
  `nightly-job.ps1` sets `BARKS_OVERNIGHT_MIN_FREE_MB=3072`, and so does a user
  environment variable, for runs started by hand. Remove both when the memory goes up.
- **`nightly-job-now`** has the same action and account as `nightly-job` but no trigger
  and no wake: Windows will not start a disabled task. It runs on the desktop like the
  nightly one, and the machine stays awake afterwards.
- **`test.ps1`** turns its copy of the task on, so the wake test works while
  `nightly-job` is disabled. The laptop's copies the task's settings as they are.
- **Ping goes unanswered**: Windows' firewall drops it. Watch a wake with ssh, or
  afterwards in `powercfg /lastwake`, which names the task.
- **The ssh shell is PowerShell**, not bash: the commands go without the
  `powershell -Command` wrapper, and `~` and backslashes work as written.

| To | Run (from the main machine) |
|---|---|
| Run it now (stays awake afterwards) | `ssh greg-dell Start-ScheduledTask nightly-job-now` |
| See whether it is running | `ssh greg-dell '(Get-ScheduledTask nightly-job-now).State'` |
| The newest run's results so far | `ssh greg-dell 'gc ((ls ~\source\repos\barks-compleat-reader\build\overnight -Dir \| sort Name)[-1].FullName + "\summary.txt")'` |
| Stop it | `ssh greg-dell Stop-ScheduledTask nightly-job-now` |
| Test the wake (the ssh session drops as it sleeps) | `ssh greg-dell 'powershell -ExecutionPolicy Bypass -File $HOME\nightly-job\test.ps1'` |
| Remove the test's task afterwards | `ssh greg-dell 'Unregister-ScheduledTask nightly-job-test -Confirm:$false'` |
| Turn the schedule on | `ssh greg-dell Enable-ScheduledTask nightly-job` |

`summary.txt` is rewritten after each stage; `nightly-job.log` gets the run's output only
when it ends. As on the laptop, greg must be logged on with the screen unlocked; the
display may be off.
