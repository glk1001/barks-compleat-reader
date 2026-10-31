# Plan: one look for every popup, and a gallery to check them

> Status: **stages 1 (the gallery: 1ebd9347, 81bbb5dd) and 2 (the frame) done
> 2026-10-31**; stage 3 begun: the `MessagePopup` and standalone families are on the
> frame; speech bubbles and the settings popups are still to move. Decided with the user that day: every
> popup the app owns is in scope; the shared look starts from the standalone family's
> (About, the installers); the popups are viewed both live and as a screenshot sheet;
> the gallery comes first, so today's inconsistencies are seen side by side before any
> of them changes. Tick a stage off here, with its commit, as it lands.

## Why

The popups were written one at a time, five ways, and it shows: two kinds of title bar
(Kivy's own, its title in red, and the standalone family's warm-dark bar), five window
sizes, three background treatments, a button row placed by hints a `BoxLayout` ignores,
and one popup (speech bubbles) pinned to the bottom-left rather than centred.

## What there is (2026-10-31)

| Family | Popups | Title bar | Size (window fraction) | Background |
|---|---|---|---|---|
| `MessagePopup` (`ui/reader_popups.kv`, `ui/popup_widgets.py`) | Quit, Delete From History, Clear Reading History, Small screen, the data pack offer and its "no update", the user errors (`ui/user_error_handler.py`: close only, go to settings, fatal config) | Kivy's, red title | 0.9 x 0.5 | Kivy's, tinted blue; Quit and the data pack offer add art, bold outlined text at 1.35x |
| `show_standalone_popup` (`ui/kivy_standalone_show_message.py`) | About (in the app); the first-run installer, the error popup, the data pack success (each its own window) | warm-dark, 56 px, a close X | 0.85 x 0.54, 0.9 x 0.85, 0.9 x 0.9, 1 x 1 | rounded card, art under a scrim set per popup |
| `SpeechBubblesPopup` (`ui/index_screen.py`) | the index screen's speech bubbles | Kivy's, themed gold | 0.7 x 0.4, at x 0.06, y 0.06 | its own colour |
| settings (`ui/settings_fix.py`, `ui/alt_escape_capture_popup.py`) | Select Directory, Alternate Escape Key, Kivy's options list | Kivy's, white | 0.8 x 0.8, 0.6 x 0.4, Kivy's | Kivy's |
| the wiki (`okf_reader`) | a footnote bubble | none | 0.75 x 100 px | `ModalView` |

`LoadingDataPopup` (`ui/popup_widgets.py`) is never built: delete it.

The gallery's first sheets showed two more things to set right: the standalone
family's icon glyphs (the banners' and the Start and Show Details buttons') draw as
boxes, Roboto having no such characters; and the first-run installer and the error
popup draw their card smaller than their own window, inside a black margin.

## Stage 1: the gallery

Two ways to look, from one list of popups.

- **In the app**, a gallery service (`ui/popup_gallery.py`, its names and requests in
  the Kivy-free `core/popup_gallery.py`), on only when `BARKS_READER_POPUP_GALLERY` is
  set (the way the GUI probe's frame, census and tap-target requests are): `live`
  steps through the popups with Page Up and Page Down, a corner label naming each
  ("3/18 quit"); a file path is a request file, each request (`<id> <name>`) opening
  that popup and logging `POPUP_GALLERY_SHOWN` for the driver to wait on. A popup's
  own keys are left alone: the remote's six drive its buttons as ever.
- **One function per popup.** Each call site's arguments move into a named function
  (`confirm_quit_popup(...)` and the like) that the call site and the gallery both
  call, so the gallery shows what the app shows and cannot drift from it. The gallery
  never calls `request_quit`, which quits outright when confirm-quit is off.
- **`scripts/popup_gallery.py`**, the driver: boots the app through `gui-probe.sh` from
  a scratch copy of the profile (`BARKS_READER_CONFIG_DIR`; the real one is never
  touched), at three sizes (the single page, the spread, a 1080p screen), capturing
  each popup with the probe's frame request; runs each own-window popup (first-run
  installer, error popup, data pack success) by its module's own preview, imported
  after `config_info` as `main.py` would, on a private Xvfb and captured from it; and
  lays every PNG out on one contact sheet per size and one for the own-window popups
  (ImageMagick `montage`). `--list`, `--only`, `--sizes`, `--no-own-window`, `--live`,
  `--out`.

## Stage 2: the shared frame

One popup frame (`ui/popup_frame.py`'s `PopupFrame`), from the standalone family's
look in the theme's colours, for every popup to be built on. Decided with the user
2026-10-31:

- one title bar: the warm-dark bar, the title in the theme's title colour; a close X
  only on a popup with no buttons (About, the data pack success), since Cancel and
  Escape close the rest;
- one body text style (`message_body`): cream, prose left-aligned, a short question
  centred;
- one button row along the bottom, right-aligned, one height, one focus ring; Left and
  Right move it, Return presses, Escape presses the last button (the cancel);
- one card: dark, as About's, with any art beneath one scrim (`CARD_SCRIM`), the art
  filling the card;
- centred, always: the speech bubbles popup too, now pinned 6% in from the window's
  bottom-left corner (its placement may be looked at again later);
- three size classes (`core/popup_frame.py`), measured in comic pages across (the
  window's height over the page aspect, as the spread lays out its pages) and in the
  window's height down, so a popup is the same size on the single page and on the
  spread at one height, as the fonts are, rather than stretching across two pages:
  small (a question: Quit, Delete, Clear), medium (a message, an error, a setting),
  large (a long list, About, the speech bubbles, the installers, the folder chooser).

The gallery shows the frame's three samples (`frame-small`, `frame-medium`,
`frame-large`) at every screen size until the real popups are on it; drop them once
stage 3 is done.

## Stage 3 onward: one family at a time

Move each family onto the frame, each its own commit, each checked in the gallery
before and after: `MessagePopup` (the most used; done 2026-10-31), then the standalone family (done 2026-10-31), then
speech bubbles, then the settings popups, restyling Kivy's options list and the
wiki's footnote bubble only where it is cheap (the bubble is `okf_reader`'s, shared
with the standalone viewer).

The `MessagePopup` family's move: `open_confirm_popup` and `open_message_popup`
(`ui/popup_widgets.py`) keep their callers and their log lines and build a
`PopupFrame`; the class, its keyboard driver and its `.kv` rule are gone. The five
questions are small, with their art and their text at 1.35x, centred; the two notices
and the seven user errors are medium. The frame now takes the keys on `on_pre_open`,
as the old driver did on opening: a key pressed during the fade-in reached no one.

The standalone family's move, decided with the user: `show_standalone_popup`
(`ui/kivy_standalone_show_message.py`) builds a `PopupFrame` and still runs a loop of
its own when no app is running. About is large, with its art and its close X; the
three popups that are their own window (the first-run installer, the error popup, the
data pack success) fill that window, so the black margin round their card is gone.
The installer's and the error popup's light cards are dark, their green and red
banners kept; their buttons are the frame's row (the error popup's OK first, so it
starts focused, then Save to File and Copy to Clipboard, which leave it up and show
their news in the title bar); the glyphs Roboto lacks are dropped. For it the frame
learnt to fill its window, to keep a button's popup up, and to land Escape on the X
of a popup with no buttons first, as everywhere in the app (47d61baf).

## Open questions

- The own-window popups (installer, error, data pack success) size their window in
  pixels before Kivy starts; `popup_size` gives the pixels, but the frame's module
  imports Kivy, so they must import it after `config_info`, as their previews now do.
- The size classes scale with the window's height, the fonts by two height groups;
  check the frame on the 4K television before stage 3 is done.
- The GUI tests wait on the popups' log lines (`CONFIRM_POPUP_OPENED` and the rest);
  the frame keeps every one.
