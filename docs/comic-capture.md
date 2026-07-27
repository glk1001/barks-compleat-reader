# comic-capture.sh — porting and troubleshooting notes

The script lives at `scripts/comic-capture.sh`.

Screenshots a comic reader page by page from a fullscreen Firefox window on
**GNOME / Wayland**, turning pages with a mouse click. Written against Kindle
Cloud Reader; nothing in it is Kindle-specific except the default click targets.

The script's own header explains *how* it works. This file is for getting it
running on a **different machine** — what is machine-specific, what was tried
and does not work, and what has never been verified.

## First run on a new machine

```bash
sudo apt install ydotool imagemagick x11-utils      # plus firefox
systemctl --user start ydotool                       # needs /dev/uinput access

scripts/comic-capture.sh --calibrate   # measure the pointer -> CLICK_DIV_X/Y
scripts/comic-capture.sh --probe       # check framing and click targets
scripts/comic-capture.sh --out ~/comics/vol11 --pages 40 --split-spreads
```

`--calibrate` is not optional on new hardware. See "pointer" below.

Output is `001.png`, `002.png`, … numbered by **page**: a split spread takes two
numbers, so the sequence stays continuous and in reading order (a cover then two
spreads gives 001, 002+003, 004+005). `--pages` counts **screens** to capture,
which with spreads is roughly half the page count. `--prefix` puts a name in
front if you want one.

Prerequisites the script checks at startup, failing with a specific message:
ydotool socket, ImageMagick 7 (`magick` **and** `compare`), firefox, and the
GNOME keybinding `org.gnome.shell.keybindings screenshot-window` still being
`<Alt>Print`. The fiddly one is `/dev/uinput`: ydotoold needs the udev rule and
your user in the `input` group.

## Machine-specific values

| Knob | Meaning | Measured on the 2× 2560x1440 desktop (scale 1) |
|---|---|---|
| `CLICK_DIV_X` / `CLICK_DIV_Y` | pointer acceleration divisor | **2.0** |
| display scale | logical vs capture pixels | 1.0 (auto-detected) |
| `SHOT_DIR` | where GNOME writes shots | `xdg-user-dir PICTURES`/Screenshots |

## The pointer, and why calibration is mandatory

ydotool's virtual device has **no absolute axes** — `/proc/bus/input/devices`
shows `EV=7` (SYN\|KEY\|REL). `ydotool mousemove -a` is therefore a corner-pin
plus a *relative* move, and GNOME's pointer acceleration scales that delta. A
request of N pixels lands `CLICK_DIV × N` away. The factor belongs to the
machine's pointer settings, **not** to its resolution, so it does not follow
from knowing the monitor size.

Getting it wrong is silent: the pointer pins to a screen edge and every page
turn misses, with no error. `--calibrate` measures it by clicking at two known
values and locating a magenta marker the test page drops at the click point —
two points give the divisor and cancel any offset. No OCR, no reading numbers
off a screen.

Related: absolute clicks reach the **primary monitor only**, so the comic window
must be on it. On a single-monitor machine this is automatic. The script detects
which monitor the window is on (see below) and refuses with an explanation
rather than clicking into the void. Mutter opens a new window on the monitor of
the currently *focused* window — not the one under the pointer — so on a
multi-monitor box, click something on the primary monitor before starting.

The same corner-pin is why the script turns GNOME's **hot corner** off for the
duration (`DISABLE_HOT_CORNER`, restored on exit). Pinning to the top-left
corner triggers the Activities overview, which steals focus; a window-scoped
screenshot then has nothing to grab and silently produces no file, which looks
for all the world like ydotool being broken.

## Display scaling (the 4K trap)

`xrandr` reports **logical** geometry while GNOME screenshots arrive in
**physical** pixels. On a 4K panel at 200% those differ by 2×, and every size
test in the script would fail — the fullscreen check would never match and a
run would stall waiting for a window that is already fullscreen. The script
measures the ratio once from a full-desktop capture and restates the monitor
table in capture pixels. Verified only in its no-op form (scale 1.0); the
scaled path is reasoned, not tested.

## Capture resolution — a bigger screen buys almost nothing

**Kindle Cloud Reader does not fit the page to the viewport.** It renders at a
capped size and pads the rest with white, so handing it more screen does not
hand you more page. This was measured, not assumed — rotating a 2560×1440 panel
to portrait and re-probing:

| Viewport | Rendered page | Gain |
|---|---|---|
| 2560×1440 landscape | 1024 × 1414 | — |
| 1440×2560 portrait | 1110 × 1528 | +8% linear, +17% pixels |

In the portrait case the page used only 77% of the window's width and 60% of its
height. Geometry would have predicted a page about twice that size; the reader
simply does not scale up.

So **do not expect a 4K panel, rotated or not, to be worth much here.** The
earlier version of this section predicted a near-native ~2070×2855 from portrait
4K by assuming fit-to-viewport behaviour. That prediction was wrong and has been
removed rather than left to mislead.

A corollary worth noting: Cloud Reader appears to serve **smaller page assets
than the Android Kindle app**. The ~2175×3000 "hi-def" figure describes what the
app downloads to external storage, not what the web reader delivers — the web
reader tops out near 1100 px wide in every configuration tried.

**Zooming does not help, but a bigger viewport probably does.** Two different
things, easily conflated. Measured by halving each image and re-enlarging it —
a round trip that costs an upscaled image almost nothing and a genuinely
detailed one a great deal:

| Render | half-then-double RMSE | reading |
|---|---|---|
| landscape, 1024 px wide | 0.075 | genuine detail |
| portrait, 1110 px wide | 0.060 | genuine detail, not an upscale of the 1024 |
| zoomed with no reload | 0.018 | interpolated |
| control: known 2× upscale | 0.009 | pure upscale |

So CSS zoom merely stretches the asset already fetched — but the *wider* layout
in portrait produced a genuinely sharper render. The reader lays the page out at
roughly 77–80% of viewport width (77% for one page in portrait, 80% for two in
landscape), and the asset kept up at 1110 px.

That means **1100 px is not a ceiling, it is just what a 1440-px viewport asks
for**, and a 4K panel would plausibly render ~1536 px per page in landscape or
~1660 in portrait. Whether Amazon's asset actually supplies that detail is
**untested** — the honest answer needs one of:

1. Firefox devtools, Network tab, filter to images, reload a page and read off
   the dimensions of the page image actually downloaded. That is definitive: if
   it fetches ~1200 px wide whatever the window size, that is the ceiling; if it
   scales with the viewport, a bigger display pays.
2. Zoom in **and reload**, so the reader re-requests assets at the new device
   pixel ratio, then re-probe and re-run the sharpness test above.

An earlier version of this file asserted a measured ceiling of ~1100 px and that
no display would beat it. That was an overreach from the zoom test alone.

Portrait does still force **single-page** rather than spread view, which is a
layout convenience — but note the reader needs a reload or an F11 toggle after
rotating, or it keeps its old landscape layout and renders the page clipped.

## Things that do not work — do not retry these

| Approach | Why it fails here |
|---|---|
| `gnome-screenshot -f` | Ubuntu ships 41.0 against GNOME Shell 50. Shell D-Bus path refused, X11 fallback finds nothing; it hangs and writes no file. |
| `grim` | needs wlr-screencopy; Mutter does not implement it. |
| `import -window <id>` | Firefox is a snap Wayland client, absent from `wmctrl -l` entirely. Also returns frozen pixmaps for XWayland apps. |
| Alt+Tab to restore focus | GNOME's Alt+Tab switches **applications**. With several Firefox windows it raises the wrong one. The script polls for a settled fullscreen window instead. |
| `xdotool getmouselocation` | returns a frozen value on Wayland; no pointer feedback loop is possible. |
| md5 to compare frames | GNOME stamps `png:tIME` into every PNG, so pixel-identical frames have different checksums. Compare **pixel signatures** (`magick -format '%#'`). |

## Cropping — why `ui` is the default

`CROP=auto` trims to *ink*. Where a book's page margin is the same colour as the
reader's background (Fantagraphics cream on Kindle's cream) there is no edge to
find, so it cuts flush to the outermost panel and margins are lost — by
differing amounts per page. `CROP=ui` removes only uniform edge bands, i.e. the
reader's white gutter, and leaves the page as displayed.

Two ordering facts that took a while to find:

- The gutter must be trimmed **before** the background. The gutter runs the full
  window height, so a background trim first yields a box stretched to full
  height, after which the gutter pass can only remove columns.
- Spread detection judges the **ink** box, never the frame. Under `CROP=ui`
  every capture is the whole landscape viewport, so a frame-aspect test would
  call the portrait cover a spread and cut it in half. Splitting likewise cuts
  at the ink centre, because removing a one-sided gutter leaves the frame
  asymmetric.

## The reader's toolbar

Clicking the page drops Kindle's toolbar over it, and leaving the pointer on the
forward-click zone keeps the `›` chevron drawn — which lands in every capture
*and* blocks the gutter trim, since the band stops being uniform. Handled by
parking the pointer mid-page after each click (`PARK`), and by capturing only
once two consecutive frames come back identical.

## Verified vs not

Verified end-to-end on the 2× 2560x1440 desktop: capture, fullscreen behaviour, click page
turns with auto-target fallback, toolbar settling, gutter trim, spread splitting,
calibration.

**Not verified:** any display scale other than 1.0; any resolution other than
2560x1440; Kindle Cloud Reader itself for the click targets and page-turn
behaviour — testing used a synthetic reader built to imitate it, to avoid
driving a live session. If the default targets miss, use `--probe` then
`--click X,Y`.
