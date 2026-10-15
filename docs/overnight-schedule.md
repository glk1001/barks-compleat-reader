# The nightly schedule: wake, run, sleep

<!-- cspell:ignore gmktec gregspc runuser nmcli conhost journalctl OptiPlex lastwake Autologon cctk logind UNATTENDSLEEP -->
<!-- docs-refs: skip -->
<!-- (check_docs_refs.py: the job scripts named here live on each machine, outside the repo) -->

Each overnight machine wakes itself from sleep at **01:00**, pulls this repo, runs its
overnight run, and goes back to sleep, but only if it woke up for the run. A machine
already in use at 01:00 runs it and stays awake. The machinery lives outside the repo,
on each machine:

| Machine | Job (edit this) | Runs | Limit | Job output |
|---|---|---|---|---|
| The main machine (gregspc2) | `~/bin/nightly-job` | `git pull --ff-only`, then `scripts/run_overnight.sh` (with `build-check`: the build tree is here) | 5 h | `journalctl -u nightly-job` |
| The overnight host (gmktec) | `~/bin/nightly-job` | `git pull --ff-only`, then `scripts/run_overnight.sh --skip build-check` | 5 h | `journalctl -u nightly-job` |
| The Linux laptop (hp-notebook) | `~/bin/nightly-job` | the same as gmktec's | 5 h | `journalctl -u nightly-job` |
| The Windows laptop (win_lg) | `~\nightly-job\nightly-job.ps1` | `git pull --ff-only`, `uv sync`, then `uv run --offline scripts/run_overnight_desktop.py` | 3 h | `~\nightly-job\nightly-job.log` |
| The Windows desktop (greg-dell) | `~\nightly-job\nightly-job.ps1` | the same as the laptop's | 5 h | `~\nightly-job\nightly-job.log` |

A run's results are where they always are: `build/overnight/<stamp>/summary.txt`. A
failed pull does not stop the run: it tests the checkout as it is, and on Windows the
runner's `update` stage records the failure in the summary (on Linux it shows only in
the job output). Pulling first, rather than leaving it to the runner, means a pull that
changes the runner itself takes effect the same night. The main machine collects the run
logs of gmktec, greg-dell, its two VMs and itself in `assets/logs-overnight-runs/`
([below](#the-logs-collected)); the two laptops' stay on them.

On the main machine the run tests the working checkout as it is at 01:00, uncommitted
work included.

## Linux: the main machine and the overnight hosts

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

### The Linux laptop (hp-notebook)

An HP 250 G6 (Core i3-6006U, 2 cores and 4 threads; 3.3 GB, with a 3.7 GB swap file;
Ubuntu 26.04), set up on 2026-10-14 as gmktec is: the repos, data and tools by
`scripts/copy-to-overnight-host.sh hp-notebook`, and gmktec's `~/nightly-job-setup/`
copied and adapted. How it differs:

- **Not timed yet.** Its first run is the 01:00 one of 2026-10-15. gmktec's takes
  3h17m on 16 threads and 12 GB, `gui` 2h51m of it, so this one may reach the 5 h limit
  or swap heavily; if it does, trim the job's stages. The wake has not been tested
  either (`test.sh`): that first night is the test.
- **Not on battery**: the wrapper checks for the charger first, and on battery skips the
  job (`on battery; skipping the job` in the journal), suspending again if it woke for
  it.
- **The lid**: on the charger, closing it does not suspend the laptop
  (`/etc/systemd/logind.conf.d/50-lid-on-ac.conf`), so it can run lid shut. Without
  that, logind suspends it again about 30 s after the wake, inhibitor or not. On battery
  the lid still suspends it.
- **Wi-Fi only**, its Ethernet port unused. The connection is saved for all users, so it
  comes up at boot with nobody signed in; after a wake it has the wrapper's 60 s to
  reconnect.
- **GitHub's login is in a file**, `~/.config/gh/hosts.yml` (mode 600), as on gmktec,
  not in the desktop keyring, which is locked until someone signs in: git reaches the
  private barks-wiki over ssh and from the timer alike.
- **`setup-root.sh`**, in `~/nightly-job-setup/`, did the one-off root steps: the apt
  packages, the lid, the touch tests' udev rule, then `install.sh`. It is safe to run
  again.

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
- **`uv sync`, then `--offline`**: `uv run --offline` syncs from uv's cache only, so a
  pull that moves the Python pin or adds or bumps a package would stop the job before the
  runner starts (greg-dell, 2026-10-14: `.python-version`'s 3.13.12 and pyrefly 1.3.2).
  The job's online `uv sync` after the pull fetches them first; a sync that fails is
  logged and the run goes on with what is already synced. `uv run --no-sync` would leave
  the sync to the runner's `update` stage, which may download.
- **Execution policy**: the scripts run with `-ExecutionPolicy Bypass` for that one
  process; the laptop's own policy is left at Windows' default.
- **The wake** on Modern Standby is dark: the screen stays off, so it is easy to miss.
  Windows' wake record (`Power-Troubleshooter` event 1) names the task; Kernel-Power 507
  may give the reason as "Input Mouse" all the same.

## Windows: the desktop (greg-dell)

A Dell OptiPlex 7050 SFF with 8 GB, set up as the laptop is, with the same three
scripts in `~\nightly-job\` adapted to it. Its `nightly-job` task runs nightly (enabled
2026-10-13, staying on 8 GB); a second task, `nightly-job-now`, starts the same run by
hand. How it differs from the laptop:

- **Classic S3 sleep, not Modern Standby.** The wake is a full one, fans and all. The
  wrapper decides it woke for the run from Kernel-Power 107 ("resumed from sleep") or
  Power-Troubleshooter 1 in the last 5 minutes.
- **Limits**: 5 h in the wrapper, 5 h 15 min in Task Scheduler. The first run
  (2026-10-12, through `test.ps1`) passed in 2h02m: `gui` 48 min, `built-app` 39 min,
  `soak` 24 min.
- **Memory**: about 4 GB of the 8 is free at idle, which is the runner's own floor on a
  machine this size (half its memory), so a GUI stage might not start.
  `nightly-job.ps1` sets `BARKS_OVERNIGHT_MIN_FREE_MB=3072`, and so does a user
  environment variable, for runs started by hand. Both stay: the machine keeps its 8 GB.
  The one failure on it so far was memory pressure's kind: `built-app` (2026-10-13) over
  a timing budget, three images loaded at once in 7 s against 4.8 s, behind a 9 s start.
- **`nightly-job-now`** has the same action and account as `nightly-job` but no trigger
  and no wake, so it never starts by itself. It runs on the desktop like the
  nightly one, and by the same wrapper rule the machine stays awake afterwards, unless it
  resumed in the 5 minutes before (as `greg-dell run`, below, arranges).
- **`test.ps1`** turns its copy of the task on, so the wake test works whether or not
  `nightly-job` is. The laptop's copies the task's settings as they are.
- **Ping goes unanswered**: Windows' firewall drops it. Watch a wake with ssh, or
  afterwards in `powercfg /lastwake`, which names the task.
- **The ssh shell is PowerShell**, not bash: the commands go without the
  `powershell -Command` wrapper, and `~` and backslashes work as written.

| To | Run (from the main machine) |
|---|---|
| Wake it if need be, run, and sleep again after | `greg-dell run` (below) |
| Run it now (stays awake afterwards) | `ssh greg-dell Start-ScheduledTask nightly-job-now` |
| See whether it is running | `ssh greg-dell '(Get-ScheduledTask nightly-job-now).State'` |
| The newest run's results so far | `ssh greg-dell 'gc ((ls ~\source\repos\barks-compleat-reader\build\overnight -Dir \| sort Name)[-1].FullName + "\summary.txt")'` |
| Stop it | `ssh greg-dell Stop-ScheduledTask nightly-job-now` |
| Test the wake (the ssh session drops as it sleeps) | `ssh greg-dell 'powershell -ExecutionPolicy Bypass -File $HOME\nightly-job\test.ps1'` |
| Remove the test's task afterwards | `ssh greg-dell 'Unregister-ScheduledTask nightly-job-test -Confirm:$false'` |
| See the next scheduled run | `ssh greg-dell '(Get-ScheduledTaskInfo nightly-job).NextRunTime'` |
| Turn the schedule off | `ssh greg-dell Disable-ScheduledTask nightly-job` |
| Turn it back on | `ssh greg-dell Enable-ScheduledTask nightly-job` |

`summary.txt` is rewritten after each stage; `nightly-job.log` gets the run's output only
when it ends. As on the laptop, greg must be logged on with the screen unlocked; the
display may be off.

### Asleep, with no keyboard

greg-dell is meant to sleep between runs with no keyboard attached, woken for the 01:00
run by its task and for a manual one from the main machine. Set up on 2026-10-13, every
part tested there (the wake from off included):

- **`~/bin/greg-dell` on the main machine**: `greg-dell status` (awake or not; the run
  tasks and the newest `summary.txt`), `greg-dell wake` (a Wake-on-LAN magic packet, then
  waits for ssh), `greg-dell run` (wakes it if asleep or off, then starts
  `nightly-job-now`: woken for it, the machine sleeps again when the run ends),
  `greg-dell sleep` (refused while a run is going; `-f` forces it), and `greg-dell kill`
  (stops the run, then what it left running; the machine stays awake). It lives outside
  any repo; its header says what it assumes.
- **Wake-on-LAN**: the NIC (Intel I219-LM, MAC `54:BF:64:5C:CD:30`) wakes on a magic
  packet only. "Wake on Pattern Match" is off, or ordinary traffic wakes it. In the BIOS,
  Wake on LAN is "LAN Only" and Deep Sleep Control is Disabled, so a packet starts it from
  off as well as from sleep: from off it answered ssh 30 s after the packet.
- **Asleep by itself**: sleep on AC after 2 h idle (the host check accepts 2 h; a run
  holds the machine awake). An ssh session is not activity to Windows, and after a wake
  that nobody touched, Windows has its own shorter limit: the hidden "System unattended
  sleep timeout" (`powercfg` `UNATTENDSLEEP`), 120 s by default, which put it back to
  sleep 2-3 minutes after each `greg-dell wake`, ssh session and all. It is 2 h on AC
  (2026-10-14), the same as the idle sleep.
- **Signed in after any restart**: Sysinternals Autologon (`autologon`, from winget;
  the password is kept as an LSA secret, not in the registry in plain text) signs greg in
  at boot. The BIOS has AC Recovery On (it starts after a power cut), keyboard errors not
  reported, Continue on Warnings and no extended POST time, so it boots unattended.
- **BIOS from Windows**: Dell Command | Configure is installed, so the BIOS can be read
  and changed over ssh, without a keyboard: `cctk.exe -O <file>` writes every setting,
  `cctk.exe --DeepSleepCtrl=Disabled` sets one for the next boot (in `C:\Program Files
  (x86)\Dell\Command Configure\X86_64\`). There is no BIOS password, so any administrator
  can do the same. Secure Boot is off, as Windows was installed; turning it on needs
  Legacy Option ROMs off first.
- **No windows at sign-in**, which would take the focus from a GUI stage: Windows'
  welcome experience ("Get Started"), tips and "finish setting up" are off for greg, and
  OneDrive, Edge (startup boost and background mode, by policy) and the Logitech Download
  Assistant do not start.
- **Keep the monitor connected** (off is fine): the timing budgets were calibrated at its
  2560x1440. Without one, use a dummy HDMI plug and calibrate again.

## From the main machine: running, watching and collecting

Helpers in `~/bin` on the main machine start, watch and stop the runs from one place, and
collect their logs. They live outside any repo; each one's header says what it assumes.

| Helper | For | Subcommands |
|---|---|---|
| `greg-dell` | greg-dell ([above](#asleep-with-no-keyboard)) | `status`, `wake`, `run`, `sleep [-f]`, `kill` |
| `gmktec` | gmktec | `status`, `wake`, `run`, `sleep [-f]`, `kill` |
| `win-vm`, `mac-vm` | the Windows and macOS VMs on the main machine (`docs/setup.md`) | `status`, `start`, `run [--wait]`, `stop [-f]`, `kill` |
| `overnight-pair` | the two VMs, then the main machine, one after another | `[--no-pc] [--suspend]`, `status` |
| `overnight-logs` | five machines' run logs ([below](#the-logs-collected)), copied here | `[--wake] [machine...]` |

- **`gmktec run`** wakes it if need be and starts `~/bin/nightly-job` there in the tmux
  session `nightly-job-now`, sleep blocked; woken for it, gmktec suspends again when the
  run ends. `gmktec kill` stops a run, on demand or the 01:00 one, and everything under
  it; gmktec stays awake, except that the 01:00 run's wrapper (root, out of `kill`'s
  reach) still suspends it afterwards if it woke for the run. gmktec wakes on a magic
  packet on its wired port (tested from sleep, 2026-10-15).
- **`win-vm` and `mac-vm`** are one script, `overnight-vm`, under two names. They boot or
  resume the VM and wait for its desktop; `run` starts the run on that desktop (Windows:
  the Task Scheduler task "Barks Reader overnight now"; macOS: a Terminal window, which
  holds the permissions the GUI stages need), and `stop` shuts the VM's OS down, refused
  while a run is going.
- **`overnight-pair`** runs them one at a time, since run together they share the main
  machine's 16 threads and fail each other's timing budgets: win-vm (about 2 h), then
  mac-vm (about 1.5 h), each VM shut down after its run, then the main machine's own run
  (`~/bin/nightly-job`, about 3h50m). `--no-pc` leaves out the main machine's run;
  `--suspend` suspends the main machine when all are done. It runs in the tmux session
  `overnight-pair` (`tmux attach -t overnight-pair`) with sleep inhibited, and logs to
  `~/.local/state/overnight-pair/<stamp>.log`. At the end the session stays open, showing
  `finished: press Enter`, so the output can still be read. The next start closes a
  finished session by itself, and refuses only while a run is still going;
  `overnight-pair status` tells the two apart (`finished at 20:58:33; its session is
  still open`, against `going`).
- **`overnight-pair status`** then shows each machine (win-vm, mac-vm, the main machine)
  with one line for its run. A VM that is off has its newest run read from the copied
  logs ([below](#the-logs-collected)).

  | Label | The run |
  |---|---|
  | `this pair's run:` | started after the pair did, so it is this pair's |
  | `current run:` | going, with no pair session open (started by hand) |
  | `last run:` | an earlier one: the machine's turn in the pair has not come yet, or there is no pair |
  | `last run (not in this pair: --no-pc):` | the main machine's, when the pair skips it |
  | `last run (no run in this pair):` | a finished pair did not run the machine (a VM that failed to start, say) |

  A run still going is followed by a `last run:` line for the machine's newest earlier run
  that finished, as a guide to how long this one will take:

  ```
  win-vm (WinDev2202Eval): running
    desktop: up
    run: GOING (task 'Barks Reader overnight now' running)
    this pair's run: 20261015-225354 (880385c7): 3 of 9 stages done
    last run: 20261015-172236 (5b3b7a7f): finished in 2h02m
  ```

### The logs, collected

`overnight-logs` copies the runs' logs into this repo's
`assets/logs-overnight-runs/<machine>/<stamp>/` (gitignored), so that five machines' runs
sit side by side: `gregspc2`, `gmktec`, `greg-dell`, `win-vm` and `mac-vm`. The two
laptops (win_lg, hp-notebook) are not among them: their runs' logs stay on them.

- **What**: from each run folder, the files at its top level named `*.log`, `*.txt` or
  `*.jsonl`: `summary.txt`, the stages' logs and `gui-timings.jsonl`, about 1 MB a run.
  `coverage/` (about 40 MB) and `uv.lock.saved` stay behind.
- **Which runs**: those not copied yet, and the newest again while its copy's
  `summary.txt` header has no "finished in", since only the newest can still be going.
  Run again, it reports `up to date`, unless that newest run stopped part-way (`stopped
  during`, or `N of M stages done`): that one is copied again each time, until a later
  run finishes.
- **From where**: only the machines that are up. It wakes and starts nothing, and reports
  the rest as skipped. `overnight-logs gmktec win-vm` names the machines; no names means
  all five. With `--wake` first, it wakes gmktec or greg-dell if asleep and puts it back
  to sleep after the copy (only one it woke, and never while a run is going); the VMs
  are never started.
- **When**: `overnight-pair` copies each VM's logs before shutting it down, and the main
  machine's after its run. gmktec's and greg-dell's 01:00 runs end while the main machine
  may be asleep, so a user timer on the main machine, `overnight-logs.timer` (in
  `~/.config/systemd/user/`), runs `overnight-logs --wake gmktec greg-dell` at 07:00. It
  does not wake the main machine: a 07:00 missed while it slept runs when it next wakes
  or boots (`Persistent=true`). Its output: `journalctl --user -u overnight-logs`.
- **greg-dell**'s ssh shell is PowerShell, which is no pipe for binary output, so its logs
  go through a tar file in its home folder and `scp`; the others stream a tar over ssh.
