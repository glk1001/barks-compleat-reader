---
name: verify
description: Build, launch, and drive the Barks Reader GUI on this machine (GNOME Wayland) to verify changes end-to-end — nested-display launch recipe, screenshot capture, and mouse/keyboard injection.
---

# Verifying the Barks Reader app end-to-end

**Always drive the app on a nested Xephyr display via `scripts/gui-probe.sh`.**
Do not launch it onto the real desktop unless the thing under test *is*
window-manager behaviour — see "Running on the real desktop" at the bottom, and
read the warnings first, because that path will waste your time.

All X-touching commands need `dangerouslyDisableSandbox: true`.

## Why nested

On the real desktop the app is an XWayland client under Mutter, and both capture
and input are mediated:

- `import -window <id>` returns a **frozen pixmap**. Repeat captures come back
  byte-identical while the app has demonstrably moved on. This is the big one —
  it silently shows a stale UI and you conclude the app is not responding.
- `import -window root` is refused outright, as is `grim`.
- `xte` needs a per-session screen-share portal approval; until it is granted,
  XTEST events are dropped with no error and no visible dialog.
- `xwininfo` and `wmctrl -lG` disagree on coordinates by the 2× HiDPI factor.

A nested Xephyr server has no compositor and no window manager, so none of that
applies: root captures are always fresh, `xte` injects with no portal, and pixel
coordinates read straight off a screenshot are the coordinates to click.

## Setting this up on another machine

Run `scripts/gui-probe.sh doctor` first — it checks every tool, the repo
secrets, and each data directory, then prints exactly what is missing and the
install command. It exits non-zero when the machine is not ready.

On Debian/Ubuntu the tools are four packages:

```bash
sudo apt install xserver-xephyr xautomation x11-utils imagemagick
```

Three things do not arrive with `git clone` and have to be brought across:

- `.env.runtime` — gitignored (it holds `BARKS_ZIPS_KEY`), so copy it by hand.
- `~/opt/barks-reader/` — the Reader Files and config, per `BARKS_READER_DATA_DIR`.
- The Fantagraphics `.cbz` archives.

`barks-reader.ini` stores **absolute** paths (`fanta_dir`, `png_barks_panels_dir`,
`prebuilt_dir`, `wiki_bundle_dir`), baked in on whichever machine wrote it, so
copying the config across always means editing those. `doctor` flags each one
that does not resolve.

On a laptop panel also drop the nested screen height — the 900x1300 default is
taller than a 1080p display:

```bash
export BARKS_PROBE_SCREEN=900x1000
```

Nothing here depends on GNOME, Mutter, Wayland, ydotool, or the screen-share
portal, so the nested path is the portable one. macOS is the exception: no
Xephyr, and Kivy runs on Cocoa rather than X11, so none of this transfers.

## The loop

```bash
scripts/gui-probe.sh doctor                 # is this machine ready?
scripts/gui-probe.sh start                  # Xephyr + app; returns when interactive (~4s warm)
scripts/gui-probe.sh shot /tmp/x/s1.png     # fresh full-screen capture
scripts/gui-probe.sh click 823 74           # click at screenshot coordinates, 1:1
scripts/gui-probe.sh key Down Down Return   # keysym names, not scancodes
scripts/gui-probe.sh type "pirate gold"
scripts/gui-probe.sh wait 'Goto title' 10   # block on a log regex; non-zero on timeout
scripts/gui-probe.sh tail 30                # last N app log lines
scripts/gui-probe.sh log                    # print the log path for your own grep
scripts/gui-probe.sh stop                   # kills both, restores the user's config
```

`start` backs up `barks-reader.json` and `stop` restores it, so navigating around
during a check never leaves the user's saved node changed. **Always `stop`**,
even when the check failed.

Screen size defaults to 900x1300; override with `BARKS_PROBE_SCREEN=1200x1300`.
Display defaults to `:2` (`BARKS_PROBE_DISPLAY`).

## Read the log, not just the pixels

The app's loguru output is a more precise oracle than a screenshot, and it is
never stale. Lines carry `module:function`, so grep for the behaviour you
changed. Focus-state transitions in particular are all logged:

| Log line | Meaning |
|---|---|
| `Entered bottom focus region.` | keyboard focus moved into the bottom panel |
| `Entered bottom focus region at the title portal.` | a goto-title handed focus to the read action |
| `Exited bottom focus region.` | back to the tree / mouse mode |
| `Mouse-initiated goto-title: staying in mouse mode.` | a click did **not** enter keyboard nav |
| `Keyboard-initiated goto-title: handing focus to the title portal.` | Enter did |
| `Entered/Exited top-view goto arrow focus.` | the top-view arrow's focus ring |
| `Goto title: "<TITLE_ENUM>"` | a goto-title navigation actually fired |
| `New selected node: "X". Previous node: "Y".` | tree selection moved |

Prefer `wait '<regex>'` over `sleep`: it fails loudly when the state never
arrived, instead of capturing whatever happened to be on screen.

## Ad-hoc driving with xdotool

`xdotool` also works unmediated on the nested display and is pixel-accurate
there, which the probe's `xte` calls cannot report back on. Use it directly when
you need something the probe does not wrap — a chord, or confirmation that the
pointer actually landed:

```bash
DISPLAY=:2 xdotool mousemove 400 600
DISPLAY=:2 xdotool getmouselocation      # x:400 y:600 ...
DISPLAY=:2 xdotool key ctrl+a
```

It is optional; `doctor` reports it but never fails on it.

## Navigating without hunting for pixels

The app is fully keyboard-navigable (10-foot UX), so keys reach almost
everything. On the main screen:

- Up/Down move the tree selection; Up on the *first* node lands on the top-view
  goto arrow (only when it has a title).
- Left collapses to the parent — three Lefts from any title reaches the root
  level, which beats dozens of Ups.
- Right moves focus into the visible bottom screen. **Careful:** when the fun
  view's image-type options panel is open it owns the keyboard, and Up/Down move
  within the menu rather than between the arrow and filter buttons.
- Enter activates; Escape opens action-bar menu mode (focus on Go Back).
- The quit X asks for confirmation (Quit focused, Escape = Stay) unless
  `confirm_quit` is off.

To boot straight onto a specific node, set `AAA_Settings.last_selected_node` in
the config (leaf-to-root, e.g. `["Reading History", "root"]`) with
`goto_saved_node_on_start` on. `start` has already backed the file up.

## Running on the real desktop

Only when the thing under test *is* window-manager behaviour (fullscreen, window
sizing, multi-monitor placement). Expect every problem listed above.

```bash
uv run main.py   # run_in_background; loads .env.runtime itself
until wmctrl -l | grep -qi "compleat barks disney reader"; do sleep 1; done
WID=$(wmctrl -l | grep -i "compleat barks disney reader" | head -1 | awk '{print $1}')
```

Match the window *title*, not "barks-reader" — that hits editor windows. Then:

- Capture with `xwd -id "$WID" -out t.xwd && convert t.xwd out.png`. **Never
  `import -window`** — it returns stale frames.
- Keys via `ydotool` (kernel uinput, no portal): `export
  YDOTOOL_SOCKET=/run/user/1000/.ydotool_socket`, then `ydotool key 108:1 108:0`
  (press:1, release:0). Codes: Esc=1, Enter=28, Up=103, Down=108, Left=105,
  Right=106. `systemctl --user start ydotool` if the socket is gone.
- Clicks via `xte 'mousemove <absX> <absY>'` then `xte 'mouseclick 1'`, using
  `xwininfo -id "$WID"` absolute upper-left plus the screenshot pixel offset.
  Needs the portal approval; if clicks do nothing, that is why. `xdotool click`
  is no help — it goes through XTEST too, so it is gated identically. `ydotool
  mousemove -a` bypasses the portal in principle, but its absolute positioning
  could not be confirmed from a session here (moves were not reflected in
  `xdotool getmouselocation`), so do not rely on it for targeting.
- `xdotool` is still worth having on this path for *queries* rather than
  injection: `xdotool getmouselocation`, and `xdotool search --name` as an
  alternative to parsing `wmctrl -l`.
- `wmctrl -ia "$WID"` before every injection burst; close with `wmctrl -ic`, and
  back up/restore `~/opt/barks-reader/config/barks-reader.json` yourself.
