# Plan: a two-page spread for landscape monitors

<!-- cspell:ignore recto verso colophon -->

> Status: **stages 1 to 3 done, 2026-10-29** (the window, the book layout and the
> bar; the title page and the fun page; the index and search pages; the commits are
> in the git log under this file's name). Designed on the mock at
> https://claude.ai/artifact/1oHXzdz9tEi1zLyCH4Jv8u (private: it carries Fantagraphics
> pages), twelve states, one per screen below. Implementing and testing on the main PC
> (27-inch 2560x1440). Tick a stage off here, with its commit, as it lands.
>
> - Stage 1 the window, the book layout and the bar: DONE 2026-10-29. Seen on this PC
>   on a nested 1920x1080 display: the spread at boot (1291x1005 windowed, the pair
>   1392 wide in fullscreen), the setting switched both ways live with the window
>   refit at its height. Found on the way: the options setting widget
>   (`ui/settings_fix.py`) overrode Kivy's value handler and never dispatched
>   on_config_change, so no options setting had ever reached the app live; fixed. An
>   ini from before the setting kept its saved window geometry only once the boot
>   reader took the missing key as its default; a test holds that. Found after, on the
>   real monitor: the comic reader's bar answered the keyboard but not the mouse. The
>   OS window-drag hit test stayed on the main bar's title area, which on the spread
>   covers the reader's centred page-wide bar, so SDL took its buttons' taps as window
>   drags; the comic and document readers and By the Numbers now take the hit test
>   over as the wiki reader did (`drag_region` on `ReaderScreen`, fixed 2026-10-29).
>   Also found after: switching the layout setting with the panel open refits the
>   window and re-centres the panel, but its close X stayed where the old panel edge
>   was, off the window. The X was placed from the panel's `right`, a cached Kivy
>   alias that reads stale inside a `pos` callback when the parent sets `center_x`;
>   it is placed from `x + width` now, and a test moves the panel (fixed 2026-10-29).
>   And a regression of the options-setting fix above: the panel's schema gave each
>   options row its default as a `value`, which the row's value handler now wrote to
>   the config as the panel was built, before the row read the real value and with
>   nothing told; opening the settings reset the layout, the theme and the log level
>   to their defaults. The schema carries no value now, and a GUI test holds the ini
>   across an open and close (fixed 2026-10-29).
>   And on the spread the settings' X could not be tapped: the main bar's title area,
>   the window-drag region, runs under the centred panel's corner, so SDL took the
>   tap as a drag (on a single page the X sits over the bar's buttons). The panel
>   takes the drag region over while it is up, its title bar short of the X, and
>   hands the bar's back on close, as the full-window screens do (fixed 2026-10-29).
>   And decision 14's half for the comic reader: its bar was a page wide whatever
>   the mode, so over the pair in the spread window its items sat in the middle; in
>   double-page mode the bar is now as wide as the pair, refitted at a comic's load
>   and on the Double Page toggle (done 2026-10-29).
>   A review of the six stages (2026-10-30): the reader's bar was pair-wide under a
>   solo unit too, the cover or an odd last page drawn as one page in double-page
>   mode; the reader now says what it drew (`showing_two_pages`) and the bar follows
>   it. And with the saved window position on a second monitor of another shape, the
>   geometry helper decided the boot layout for that monitor while main.py had sized
>   the window for the primary's, so the boot check saw no change and the window kept
>   the wrong shape; the helper now starts from main.py's decision and the boot check
>   refits (both fixed 2026-10-30).
> - Stage 2 the title page and the fun page: DONE 2026-10-29. Seen on this PC on a
>   nested 1920x1080 display: Lost in the Andes and Land of the Pygmy Indians as hero,
>   picture and colophon (the 841 characters whole, the three-row portal column with
>   room to spare), the fun page's two tiers at boot (seeded) and after Change Pics,
>   the collapsed tree over its wallpaper at full brightness. Found on the way: a
>   texture loader keeps one load in flight, so the lower tier's load through the fun
>   view's loader dropped the image on show (a white page); it has its own loader now.
>   And the single page's hidden title picture, given a size hint of 0, kept Kivy's
>   100 px default height (a box layout keeps a child's own height for a falsy hint)
>   and pushed the hero band up over the tree's last rows, where it swallowed their
>   taps (two GUI tap tests caught it); the picture's height is explicit now.
>   A title without notes (The Lemonade Fling) left the colophon's lower half empty,
>   and on the page's black that read as a layout gone wrong; a grey card where the
>   notes would sit was mocked and rejected (an empty box reads as a missing element).
>   Since 2026-10-30 such a title packs its colophon into a short foot lifted a little
>   clear of the page's bottom, and the picture takes the rest of the page
>   (`compact_colophon` on the title view screen). On the spread the portal's top is
>   level with the glyphs of the text beside it in both cases: the notes' first line,
>   or the info rows (`TEXT_LEADING`), its rows stacked in the gap above, but never
>   above the info rows' last line (three rows on a cued title with an override).
>   Also on the spread: the text's left margin is the portal's right one, the gap
>   under the info rows is halved (the notes read on from the rows, and show whole
>   at 1080p), and the compact page's picture is 88% wide, not 76% (a landscape
>   picture was bound by its width there). A strict grid, the text and portal on the
>   picture's edges, is not to be had: with notes the picture is bound by its 38%
>   height, so its width is each title's art's. Tying the
>   portal to the notes made the colophon's height rule a Kivy binding loop (a
>   thousand "too much iteration" warnings) until its other branch named the share
>   the box gives it instead of a dummy.
> - Stage 3 the index and search pages: DONE 2026-10-29. Seen on this PC on a nested
>   2560x1440 display: the title search's box over its results at the page's width
>   (decision 8), the tag and word searches in their columns with a query typed, the
>   Main Index's rail and two columns, the Speech Bubble Index's Words (the prefix
>   bar's twenty columns across the page), Names and Locations, the Statistics charts
>   centred on the page, and By the Numbers alone in its page-aspect box (decision 11).
>   Found on the way: a result row is one line high, and a long word or name in the
>   word list (Flintheart Glomgold) wrapped into the row beneath; every result row is
>   cut short now as the title rows were, except a row's + button.
> - Stage 4 the document reader and the wiki: DONE 2026-10-29. Seen on this PC on a
>   nested 2560x1440 display: Censorship Fixes opens at its first page alone in the
>   middle of the pair-wide box under a bar as wide as the pair, Right turns to pages 2
>   and 3, then 4 and 5, 6 and 7, Left back; a tap on the right half turns a pair on
>   and on the left half back (decision 10). The wiki fills the spread window; in
>   fullscreen its strip is 1876 wide at 1440p, the pair's shape (decision 9), and the
>   Contrast toggle now darkens the sidebar's scrim as it did the reading pane's. The
>   open point on a mode change under a full-window screen is settled the simple way:
>   the app hands the mode to the document and wiki readers at the same moment as the
>   main screen, and they lay out again with the window, which refits under them
>   anyway. The readers log the right-hand page on its own line
>   (`DOCUMENT_RIGHT_PAGE`), so the `DOCUMENT_PAGE` line keeps naming the first page
>   shown and the GUI tests hold on the spread.
>   And found after, on this PC: on the spread only the tree's top row answered a mouse
>   tap. The fun view's margin presses are bounded by height alone and its touch
>   handler never asked whether the touch was on it; with the tree beside it instead
>   of above, every row but the top one (in the band above the margins) was a "left
>   margin" press with a negative x. The view takes no touch off itself now; a GUI tap
>   test boots on the spread (the setting forced on the portrait test screen) and taps
>   a lower row (fixed 2026-10-29).
>   From the same review: a layout change under a closed document laid it out again
>   and moved the page it resumes at; closing drops the pages (fixed 2026-10-30).
> - Stage 5 tests, the matrix variant and the soak: DONE 2026-10-30. The settings
>   matrix has a `spread` variant (the setting forced) on its own 1920x1080 screen (a
>   variant line may now name a screen), and the harness fails any boot that did not
>   come up on the layout its ini names. The overnight GUI run has a `spread-soak`
>   stage. The unit tests listed were already in place from stages 1 to 4 (the rule
>   table in `test_main_layout.py`, the window's shape per mode, the marker, the fun
>   page's tiers, the document pairing). Seen on this PC: the whole suite on the spread
>   variant green once two tests were taught the spread (the illustrated history's Go
>   to Story tests turn a pair at a time and count both pages' links, from the data as
>   before; the settings test takes either explicit layout), and the random walk on the
>   spread from seed 1, 500 keys from each of its four starts: widgets steady within
>   each walk (at most 3479 after the start on a story), RSS at most 1178 MiB, no
>   climb. Found on the way, on this PC: only the tree's top row answered a mouse tap
>   on the spread (the fun view's margins, see stage 4's note; fixed 2026-10-29).
> - Stage 6 the how-to pages, the README and the demo videos: DONE 2026-10-30, ahead
>   of the release that carries the spread. `docs/how-to-use.md` describes both layouts
>   (the Concept, a paragraph under Main Screen Layout, a row in the Settings table) and
>   the text PDFs for the GIMP step (`docs/how-to-pdfs`, gitignored) were regenerated
>   from it on this PC: five pages now, where the data pack's composited how-to has
>   three and the markdown before this stage already made four, so the GIMP
>   compositing that makes the data pack's how-to pages needs two more background
>   pages. The README and the website name the spread in their feature lists, and the
>   main window and selecting-a-title screenshots were re-shot on the spread (this PC's
>   2560x1440 screen, the window 1775x1365, on the headless probe), with the title view
>   page cropped out of the second for the website's side panel. The demo videos were
>   re-recorded on the spread (`scripts/record_demo.py` films on a 1760x1300 nested
>   screen unless told otherwise, clips of 1586x1224, and refuses a boot that came up
>   on the single page) and uploaded to the website-assets release; the website's hero
>   and tour player take the landscape clip. The release note's paragraph is in the
>   stage 6 section below.

## Context

The reader was designed for a flip touchscreen laptop held in portrait: the main window
is locked to the comic page's proportion (`COMIC_PAGE_ASPECT_RATIO` in
`core/reader_utils.py`, 3200/2120, height over width), the tree sits above the
current bottom view, and on a landscape monitor fullscreen centres that portrait column
with black at either side. The comic reader grew a double-page mode that uses a wide
screen well; the main screen still uses about a third of it (36% of a 16:9 screen's
width, 27% of an ultra-wide screen's).

The design: on a landscape monitor the main screen becomes an open book. The tree is
the left page, the current bottom view is the right page, each page at the comic page's
proportion, the pair centred on black with a gutter between, the action bar across the
top of the pair. Every page is the same width the single column has on the same screen,
so nothing gets smaller and the fonts, keyed to window height, do not change.

## Decisions

Settled with the maintainer, 2026-10-29, in this order.

1. **A setting, not a detection only.** "Main screen layout" with three values: Match
   the screen (default), Single page, Two-page spread. It sits beside Double Page Mode
   in the Reading section. The two explicit values bypass the rule below; Two-page
   spread on a portrait screen is width-limited and the pages shrink, the same as
   Double Page Mode in the reader on the portrait laptop today.
2. **The rule behind Match the screen: the spread when two pages fit side by side at
   full height.** With a bar of 45 dp and a gutter of 3% of a page's width, a page's
   width is fixed by the screen's height, so the only question is whether two of them
   fit across. The pair fits down to a width-to-height of about 1.28; 4:3 qualifies
   (24 px to spare at 1440x1080, and the best-filled screen of all), 5:4 just misses.
   No fixed aspect threshold (arbitrary, and 1.4 would wrongly exclude 4:3) and no
   shrink tolerance (nothing in the fleet needs one; easy to add later).
3. **Decided from the monitor's full size, not the window.** The window is
   aspect-locked and sized by the app, so the user cannot drag it to the boundary.
   The input is the current monitor's full size, which `AppWindowGeometryHelper`
   already tracks across monitor moves and the rotation poll: the same size in
   windowed and fullscreen mode, so a monitor gets one answer (the usable area less
   the taskbar, as first written here, would let a 5:4 screen flip between the two).
   The rule is re-evaluated on boot, on a monitor move, on the rotation poll and on a
   change of the setting, and nowhere else, so it cannot flip during use. No
   hysteresis: the flip laptop moves between 0.62 and 1.6, far from the boundary, and
   no screen in the table sits near 1.28.
4. **Left page art is wallpaper, right page art is a picture.** The tree page keeps
   the image under the tree as today (cover, dimmed to the tree's opacity); the view
   page shows its image whole (contain). The image selector's cover band
   (`FIT_COVER_MIN_ASPECT_RATIO` and `FIT_COVER_MAX_ASPECT_RATIO` in
   `core/image_selector.py`, 0.95 to 1.60) was written for the 1.33 landscape bottom
   region and is decided per region once the region is a 0.66 portrait page.
5. **The fun page is two tiers.** Two fun panels stacked, the current one above the
   previous one from the image history; two 1.37 panels stacked make 0.69, the page's
   0.66 near enough. A cover or any tall image (the Covers pool's median is 0.73)
   sits in its tier fitted by height. Tapping the page's middle third zooms the tier
   under it.
6. **The title page budget: hero 12%, picture 38%, colophon 50%,** the colophon in the
   same 56/44 columns as today (title info left, portal image and the override
   checkboxes right). Sized to the longest texts: Land of the Pygmy Indians (841
   characters of extra info) and Lost in the Andes (three override checkboxes). The
   Source line may wrap; `ExtraInfoLabel` keeps its whole-line truncation.
7. **Index pages stay white paper,** the art underlay at its opacity, the A to Z rail
   at the left, two columns (three for the speech index), the prefix bar for the Words
   index. Nothing changes but the region's proportion.
8. **Search: the title search stacks the box over its results on the page; the tag
   and word searches keep their 40/60 side-by-side layout.** The era chips and the
   basket row are unchanged.
9. **The wiki takes the book's footprint:** contents on the left, article on the
   right, one background under both at the page art's opacity, the Contrast toggle
   darkening both. It already has the two-panel shape (`TREE_PANEL_WIDTH` and
   `BODY_MAX_WIDTH` in `okf_reader/core/theme.py`); the change is its width.
10. **The document viewers go two-up.** The documents are already comic-format pages
    (2120x3200), so the reader's pairing applies: `build_display_units` in
    `core/display_unit.py` gives the first page alone, then (2, 3), (4, 5) and so on
    (from 2026-10-30 the pairs run from the first page, (1, 2), (3, 4): a document
    has no cover, so a lone first page was half a spread for nothing);
    the bar widens to the pair; Go to Story merges both pages' links from
    `core/document_links.py`. Fantagraphics Extras articles already use the comic
    reader and need nothing.
11. **By the Numbers stands alone, centred,** in its page-aspect box as today. Its
    bar is the pair's width on the spread (from 2026-10-30), as the document reader's
    is over a one-page document such as the Compleat Barks Reader introduction.
12. **The comic reader is untouched.** Its two-page footprint is 1.325 times the
    screen height wide; the main-screen spread is about 5% narrower per page because
    it keeps the bar, and it has a gutter the reader lacks. The pages shift slightly
    between the two; accepted.
13. **Popups are centred on the spread,** to start with. The Menu dropdown still drops
    from its button, over the right page. The settings panel, today sized to the main
    screen (`ui/main_screen.py`, the settings `size`), keeps the single page's
    proportion and centres on the spread.
14. **One bar, as wide as the book.** Not screen-wide: today the bar is as wide as
    the page and the black margins run uninterrupted beside it; the spread keeps that
    rule, and so do the document reader two-up and the comic reader. Nothing inside it
    moves: icon and title at the left over the tree page, the button group at the
    right over the view page, Quit behind its fence; the extra width goes to the
    draggable stretch in the middle (about 300 px to about 1000 px at 1080p), which
    is the handle in windowed mode. The buttons are not split across the pages: Go
    Back and Change Pics change both pages, and the remote user never reaches for
    a button. The bar keeps its 45 dp.
15. **The window's shape follows the mode.** In windowed mode the window locks to the
    pair's proportion instead of the page's. The saved geometry is height, left and
    top with the width derived (`MAIN_WINDOW_HEIGHT` and its two neighbors in
    `core/reader_settings.py`), so a saved window survives a mode switch.
16. **The default changes what existing users see.** With Match the screen the
    default, every user on a landscape monitor sees the spread on the first run after
    updating. The release note says so and names the setting that puts the single
    column back.

## Geometry

Bar 45 dp, gutter 3% of a page's width (about 20 px at 1080p, 28 px at 1440p). A page's
width is (H - bar) / 1.509. The pair is 2.03 pages. Fullscreen:

| Screen | w/h | Page | Pair | Fits | Margin each side | Width used, single | Width used, spread |
|---|---|---|---|---|---|---|---|
| 4K TV 16:9 | 1.78 | 1402 | 2845 | yes | 497 | 36% | 74% |
| This PC 2560x1440 | 1.78 | 924 | 1877 | yes | 342 | 36% | 73% |
| 1920x1080 | 1.78 | 686 | 1392 | yes | 264 | 36% | 73% |
| Laptop 1920x1200 | 1.60 | 765 | 1554 | yes | 183 | 40% | 81% |
| 3:2 2160x1440 | 1.50 | 924 | 1877 | yes | 142 | 43% | 87% |
| 1366x768 | 1.78 | 479 | 973 | yes | 197 | 35% | 71% |
| 4:3 1440x1080 | 1.33 | 686 | 1392 | yes | 24 | 48% | 97% |
| 5:4 1280x1024 | 1.25 | 649 | 1317 | no, pages shrink 3% | 0 | 51% | 100% |
| Ultra-wide 3440x1440 | 2.39 | 924 | 1877 | yes | 782 | 27% | 55% |
| Flip laptop portrait 1200x1920 | 0.62 | 1243 | 2522 | no, pages shrink 52% | 0 | 100% | 100% |

The spread's content aspect (height over width) is a constant,
`COMIC_PAGE_ASPECT_RATIO / (2 + gutter fraction)` = 0.743, because the gutter is a
fraction of the page. That is what makes the window lock a constant per mode rather
than a function of the screen. This table is the parametrised unit test of the rule.

## Changes, by stage

The premise for each stage is a file read named here; state it again, with the record
count where there is one, before the first multi-file edit of the stage.

### Stage 1: the window, the book layout and the bar

- `core/main_layout.py`, new, Kivy-free: `MainLayoutMode` (single, spread), the
  setting's three values, `spread_fits`, `choose_main_layout`, the gutter fraction,
  `content_aspect_ratio(mode)`, `gutter_width` and `page_width`. Unit tests from the
  table above.
- `core/reader_settings.py`: `MAIN_SCREEN_LAYOUT` with a `FieldSpec` of the options
  kind beside `DOUBLE_PAGE_MODE`, default Match the screen.
- `core/reader_utils.py`: `get_win_dimensions` and `get_win_width_from_height` take the
  content aspect instead of reading the page constant; every caller passes the mode's.
- `ui/app_window_geometry.py` and `core/window_minimum.py`: `WindowSizeConstraints`
  carries the mode's aspect; the helper evaluates the rule at the three moments above,
  logs the result, and when the mode flips runs the same correction the rotation path
  runs. The supported minimum (1920x1080 in `core/window_minimum.py`) stays the floor
  for both modes; in the spread the floor's width is the pair's.
- `core/log_markers.py`: `MAIN_LAYOUT_MODE`, "Main screen layout: {mode} ({reason}).",
  logged on every evaluation, with a `loguru_sink` unit test; the GUI tests wait on it.
- `ui/main_screen.kv` and `ui/main_screen.py`: the tree and the bottom base view
  (added in `_wire_screens`) go into a book layout under the bar, horizontal with the
  gutter as spacing in the spread, vertical as today in single mode, switched by a
  `layout_mode` property on `MainScreen`. The bar's `FloatLayout` is already as wide
  as the window, so the bar widens on its own; check the drag region on Windows
  (`ui/main_screen_window.py`) still covers the whole middle stretch.
- Popups and the settings panel: centred on the window, the settings panel at the
  page's proportion.
- The GUI harness pins the setting to Single page (`INI_DEFAULTS`), so the suite
  stays on the layout it was written on until stage 5 adds the variant.
- Done when: the app boots on this PC into the spread with the old screens in the two
  pages, the single column on the flip laptop in portrait, and the setting forces
  either; windowed mode drags and resizes at the pair's proportion.
- Not seen yet: fullscreen on a real desktop (the nested display has no window manager,
  so SDL's fullscreen leaves the X window at its windowed size and crops the render;
  the host box was 1392x1080 and centred in the log), the flip laptop in portrait, a
  monitor move and a rotation (unit-tested only). The fun view's tap regions are still
  worked out from the main layout's size, not the view's (`on_main_layout_size_changed`
  in `ui/main_screen_window.py`): wrong on the right page, and stage 2's to fix.

### Stage 2: the title page and the fun page

- `ui/bottom_title_view_screen.kv`: the 18/82 hero split becomes 12/38/50 in the
  spread (hero, picture, colophon), the colophon keeping its 0.56/0.44 columns; the
  portal image and the checkbox column fit the 44% column at the page's width; verify
  on Lost in the Andes and Land of the Pygmy Indians.
- `ui/fun_image_view_screen.kv` and `core/image_history.py`: two tiers in the spread,
  the lower from the history; the middle third zooms a tier.
- `core/image_selector.py` and `core/view_pipeline.py`: the fit rule takes the region's
  aspect; the tree page is wallpaper (cover, the tree's opacity), the view page a
  picture (contain); the selector picks two fun panels on boot in the spread.
- `ui/tree_view_screen.kv`: the idle (collapsed) state shows the wallpaper alone on
  the left page; nothing else changes.
- As built: the three page screens carry a `layout_mode` property that `MainScreen`
  sets with its own. The title view's background art shows only while the eye hides
  the panel; the panel's picture is the same art, contain, 76% wide. The fun view
  stacks when its image is landscape and the history has one before it (`previous`
  in `core/image_history.py`), at 0.49 of the page each, the lower dimmed with its
  title; a tall image stood alone, contain (until the zoom, below); the tap margins are the view's own
  (`on_size`), the upper tier's halves when stacked, and the lower tier is a target of
  its own (superseded the same day: the page in thirds, below). The title and goto arrow of the image on show sit at its top right, as the
  tree's wallpaper has them, in both layouts, and stacked the lower tier's title sits
  at its own top right with a goto button of its own (they were both at the bottom of
  the lower tier, 2026-10-30). The goto buttons are one glyph everywhere, the wiki's
  open book on the arrows' disc (`Various/goto-title-button.png`): the up and down
  arrows said where the title lay, which on the spread is beside the image. The lower
  button is a keyboard stop below the upper one; its goto names its image
  (`on_goto_lower_title`); `FUN_VIEW_STACKED` logs the tiers. A tap on the lower tier
  right after boot collapsed the tiers: the step back landed on the seeded image,
  which had nothing below it. A step back onto the oldest image on the spread now
  picks one more and puts it behind (the view holds the pipeline's picker), so the
  lower tier never runs dry; a full history drops its newest image for it, as it drops
  the oldest for a new one at the front (the cap refused the seed after three taps on
  this PC, 2026-10-30; both fixed that day). A press on the lower tier promoted its
  image, a step back, and a tall one then stood alone with the pair a step *forward*:
  the next press, a step back, lost it. The page's presses are now thirds
  (`_press_on_the_page`): the outer thirds step back and forward, both tiers moving
  with the history as the keys move them, and the middle third zooms the tier under
  it to fill the page, view-only, a second middle press bringing the pair back
  (`zoomed`, `tiered`; `MIDDLE_PRESSED` and `FUN_VIEW_ZOOM`; the tap targets "upper
  middle", "lower middle" and, zoomed, "middle"). The history never moves on a zoom,
  so a step back is always the pair the zoom came from; any step, a new image or a
  layout change ends it. Zoomed in on the lower tier, the upper overlay carries that
  image's title and goto. The single page keeps its halves (2026-10-30). With the
  zoom there, a tall image stands alone no more: a step onto one changed the layout
  as if it were a zoom. The tiers stack whatever the shape of the image on show, a
  tall one fitted by its height, and only a middle press fills the page.
  The two tiers once held the photo and the watercolor of one panel: the selector
  skipped recently used *files*, and a panel comes in up to ten treatments (the AI
  folder's and the favourite). Recently used is now the panel in any treatment
  (`_panel_key` in `core/image_selector.py`: folder and page-panel number).
  The view feeds its own history's oldest end whenever the lower tier has nothing
  to show (`_feed_the_oldest_end`, on every refresh of the tier: the first image, a
  switch to the spread, a step back onto the oldest; `pick_fun_view_image` on the
  pipeline, `add_oldest` on the history; the renderer's own seed on a layout switch
  was folded in, 2026-10-30). The image selector is untouched: a tier of the spread page has the
  single page's bottom view's shape (the book's two children split it evenly), so the
  cover band already fits a tier. The collapsed tree (view state INITIAL) is a
  `tree_collapsed` property the tree view's wallpaper reads.
- Not seen yet (at stage 2): a tall fun image on the page (the fun pool gave none in
  twenty Change Pics), a press on the lower tier (unit-tested; the GUI suite runs
  single page until stage 5), the title view's eye in the spread.

### Stage 3: the index and search pages

- `ui/index_screen.kv`: nothing but verification at the new proportion (rail, columns,
  the prefix bar's twenty columns at the page's width).
- `ui/search_screen.kv`: the title search's 35/65 columns become box over results in
  the spread; the tag and word searches keep 40/60.
- `ui/corpus_stats_screen.kv`: verification only; By the Numbers centres alone.

### Stage 4: the document reader and the wiki

- `ui/document_reader.kv` and `ui/document_reader.py`: pairs from
  `build_display_units`, first page alone; the bar as wide as the pair; Go to Story over
  both pages' links; single-page as today in single mode.
- Afterwards (2026-10-30), the two document readers brought level: the pairs run
  from the first page (a document has no cover); the comic reader's bar names an
  article as its tree node does (`ARTICLE_TITLE_TEXTS` in
  `core/reader_consts_and_types.py`) rather than "Extras (Non-Barks) #1"; Go to Story
  carries the goto-title glyph, the comic reader's curved arrow being its Goto Page;
  and the document reader's bar has the comic reader's Fullscreen, hiding the bar in
  fullscreen (a top-margin tap or Escape brings it back), closing into the mode the
  document opened in once laid out for it. A document never goes fullscreen on its
  own: the goto-fullscreen-on-read setting is the comic reader's. Removing the
  document reader for packaged `.cbz` documents was weighed and kept: a document's
  pages link to stories (Go to Story) and resume per chapter, which a comic cannot.
- `ui/wiki_reader.py` and `okf_reader/ui/viewer.py`: the viewer takes the book's
  footprint; one background under both panels; Contrast darkens both.
- As seen (2026-10-30): on the spread the article, capped at `BODY_MAX_WIDTH`,
  floated centred between two bands of art, away from the contents beside it. It
  is now anchored against the sidebar, the spare width all on the right, and on
  the spread its cap is `BODY_MAX_WIDTH_SPREAD` in `ui/wiki_reader.py` (880 dp,
  through the viewer's `set_body_max_width`; 760 on the single page), and it opens
  with Contrast on (`_apply_layout_contrast`, through the viewer's `set_contrast`;
  the single page opens with it off). The reading pane's scrim was the body's
  height, so a short page showed the art below it: it is now drawn on the pane,
  the article's width and the pane's full height (`_add_reading_pane_scrim`).
  Still open: the gutter between the sidebar and the article is narrow.

### Stage 5: tests, the matrix variant and the soak

- GUI tests: a `spread` variant in `scripts/run_gui_matrix.sh` (the setting forced,
  `--screen 1920x1080`), waiting on `MAIN_LAYOUT_MODE`; one sample title per screen
  as the suite does today; the memory census under the soak with two art images
  loaded at once (the plateau is in the app memory profile note).
- `scripts/check_gui_keys.py` unchanged: the spread adds no key. Focus moves tree to
  portal by the explicit hand-off as today, never by Left or Right.
- Unit tests: the rule table, the window aspect per mode, the log marker, the fun
  page's two-tier choice, `build_display_units` on a document's page count.

### Stage 6: the how-to pages, the README and the demo videos

- `docs/how-to-use.md` and its screenshots, the how-to document in the data pack, the
  README's screenshots and the demo videos (`scripts/record_demo.py`) show the single
  column; re-render once the spread is in a release. Not before: the data pack's
  how-to pages are a data-pack version.
- The release note names the setting (decision 16). The paragraph for the draft
  release, which GitHub writes when the app tag is pushed and the maintainer publishes
  by hand:

  > **A two-page spread on wide monitors.** On a landscape monitor the main screen now
  > opens like a book: the story tree on the left page and the current view (a story's
  > title view, the fun view, an index or a search) on the right, each page as wide as
  > the single column was, so nothing gets smaller. The default, *Match the screen*,
  > picks the spread on a landscape monitor and the single column on a portrait one,
  > so a monitor user sees the spread on the first run after updating. To keep the
  > single column there, set *Main Screen Layout* to *Single page* in Settings. The
  > document reader pairs its pages on the spread too, and the Carl Barks Wiki takes
  > the wider window.

## Open points carried into implementation

- The gutter's exact fraction, once seen on this PC (3% is the mock's).
- Whether the tree page's wallpaper dims further behind the idle screen.
- Where the playlist note sits on the title page in the spread.
- Mode change while a full-window screen is up (comic reader, wiki, document):
  evaluate on return to the main screen, never under the open screen. Settled at
  stage 4 the other way: the window refits under the open screen already, so the
  document and wiki readers take the mode at once and lay out with it.
- The focus ring: one per page, the tree's and the portal's, drawn as today.
