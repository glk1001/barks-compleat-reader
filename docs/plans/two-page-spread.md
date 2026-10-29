# Plan: a two-page spread for landscape monitors

<!-- cspell:ignore recto verso colophon -->

> Status: **design settled, no code yet** (2026-10-29). Designed on the mock at
> https://claude.ai/artifact/1oHXzdz9tEi1zLyCH4Jv8u (private: it carries Fantagraphics
> pages), twelve states, one per screen below. Implementing and testing on the main PC
> (27-inch 2560x1440). Tick a stage off here, with its commit, as it lands.
>
> - Stage 1 the window, the book layout and the bar: TODO
> - Stage 2 the title page and the fun page: TODO
> - Stage 3 the index and search pages: TODO
> - Stage 4 the document reader and the wiki: TODO
> - Stage 5 tests, the matrix variant and the soak: TODO
> - Stage 6 the how-to pages, the README and the demo videos: TODO

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
3. **Decided from the monitor's usable area, not the window.** The window is
   aspect-locked and sized by the app, so the user cannot drag it to the boundary.
   The input is the current monitor's usable area, which `AppWindowGeometryHelper`
   already tracks across monitor moves and the rotation poll, less the taskbar in
   windowed mode as `core/screen_metrics.py` already subtracts. The rule is
   re-evaluated on boot, on a monitor move and on the rotation poll, and nowhere
   else, so it cannot flip during use. No hysteresis: the flip laptop moves between
   0.62 and 1.6, far from the boundary, and no screen in the table sits near 1.28.
4. **Left page art is wallpaper, right page art is a picture.** The tree page keeps
   the image under the tree as today (cover, dimmed to the tree's opacity); the view
   page shows its image whole (contain). The image selector's cover band
   (`FIT_COVER_MIN_ASPECT_RATIO` and `FIT_COVER_MAX_ASPECT_RATIO` in
   `core/image_selector.py`, 0.95 to 1.60) was written for the 1.33 landscape bottom
   region and is decided per region once the region is a 0.66 portrait page.
5. **The fun page is two tiers.** Two fun panels stacked, the current one above the
   previous one from the image history; two 1.37 panels stacked make 0.69, the page's
   0.66 near enough. A cover or any tall image (the Covers pool's median is 0.73)
   stands alone. Tapping the lower tier promotes it.
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
    `core/display_unit.py` gives the first page alone, then (2, 3), (4, 5) and so on;
    the bar widens to the pair; Go to Story merges both pages' links from
    `core/document_links.py`. Fantagraphics Extras articles already use the comic
    reader and need nothing.
11. **By the Numbers stands alone, centred,** in its page-aspect box as today.
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
  setting's three values, `spread_fits(usable_width, usable_height, bar_height)`,
  `choose_main_layout(setting, usable_width, usable_height, bar_height)`, the gutter
  fraction and `content_aspect_ratio(mode)`. Unit tests from the table above.
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
- Done when: the app boots on this PC into the spread with the old screens in the two
  pages, the single column on the flip laptop in portrait, and the setting forces
  either; windowed mode drags and resizes at the pair's proportion.

### Stage 2: the title page and the fun page

- `ui/bottom_title_view_screen.kv`: the 18/82 hero split becomes 12/38/50 in the
  spread (hero, picture, colophon), the colophon keeping its 0.56/0.44 columns; the
  portal image and the checkbox column fit the 44% column at the page's width; verify
  on Lost in the Andes and Land of the Pygmy Indians.
- `ui/fun_image_view_screen.kv` and `core/image_history.py`: two tiers in the spread,
  the lower from the history; tall images alone; tapping the lower tier promotes it.
- `core/image_selector.py` and `core/view_pipeline.py`: the fit rule takes the region's
  aspect; the tree page is wallpaper (cover, the tree's opacity), the view page a
  picture (contain); the selector picks two fun panels on boot in the spread.
- `ui/tree_view_screen.kv`: the idle (collapsed) state shows the wallpaper alone on
  the left page; nothing else changes.

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
- `ui/wiki_reader.py` and `okf_reader/ui/viewer.py`: the viewer takes the book's
  footprint; one background under both panels; Contrast darkens both.

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
- The release note names the setting (decision 16).

## Open points carried into implementation

- The gutter's exact fraction, once seen on this PC (3% is the mock's).
- Whether the tree page's wallpaper dims further behind the idle screen.
- Where the playlist note sits on the title page in the spread.
- Mode change while a full-window screen is up (comic reader, wiki, document):
  evaluate on return to the main screen, never under the open screen.
- The focus ring: one per page, the tree's and the portal's, drawn as today.
