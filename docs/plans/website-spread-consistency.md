# Plan: one layout story on the website

> Status: **done 2026-11-01 (review 2026-10-30).** The
> review is of `website/app.html` as it stood at commit 618a5c39, after the two-page spread
> landed (`docs/plans/two-page-spread.md`). Tick the stages off here, with their commits,
> as they land. The site is GitHub Pages served from `main`, so stages 1 to 3 went out in
> one push: stage 1 alone put spreads in the 340 px Features column, and stage 2 alone a
> layout section with no text.

## The problem

The page mixes two kinds of capture without saying so. Every video and the first two
screenshots show the two-page spread. The other six screenshots are the old portrait
window, four of them with the tree stacked over the view, which is the single-page layout.
The text never names that layout as a mode, so a reader sees two different apps.

The layouts make it worse. In the Screenshots grid the landscape spread shots are short
and the portrait shots are tall. In the Features side column a portrait capture shows a
stacked tree that the copy beside it never mentions.

The words wobble the same way:

- The Introduction has two overlapping bullets about layout ("optional fullscreen and
  double page modes" and "opens like a book on a wide monitor ... a single column on a
  portrait screen").
- The page uses "double page", "two-page spread", "opens like a book", "single column",
  "wide monitor" and "portrait screen" for two settings. The app has fixed names: the
  Layout setting is *Single page*, *Two-page spread* or *Match the screen*
  (`docs/how-to-use.md`, Layout), and the comic reader's button is *Double Page*.
- The Features tab has a section for every other headline feature and none for the
  spread, although the README lists it second.

What is which, today:

| File                                      | Shows                                            |
|-------------------------------------------|--------------------------------------------------|
| `website/demo.mp4`, `website/demo-poster.jpg`         | spread (1586x1224)                   |
| `website/walkthrough.mp4`, `website/walkthrough-poster.jpg` | spread (1586x1224)             |
| `website/screenshot-main-window.jpg`      | spread, 1775x1365                                |
| `website/screenshot-selecting-a-title.jpg` | spread, 1775x1365                               |
| `website/screenshot-title-view.jpg`       | the right page cropped out of the one above      |
| `website/screenshot-reading-a-story.jpg`  | portrait window, comic single page               |
| `website/screenshot-search-titles.jpg`    | portrait window, tree stacked over the search    |
| `website/screenshot-speech-bubble-index.jpg` | portrait window, tree stacked over the index  |
| `website/screenshot-reading-history-bg.jpg` | portrait window, tree stacked over the history (deleted in stage 3) <!-- docs-refs: ok --> |
| `website/screenshot-carl-barks-wiki.jpg`, `website/screenshot-carl-barks-wiki-2.jpg` | portrait wiki window |

The share card (`website/og-card.jpg`) and the banner art are drawings, not screenshots,
and need nothing. The videos need nothing.

## The rule

One sentence governs every picture: **a whole-window picture is the spread, and a
feature's close-up is one page of it.** Each page of the spread is exactly as wide as
the single page would be, so a page cropped out of a spread capture is the natural detail
shot, and it lands at the same shape as today's portrait files. The Screenshots grid
becomes six landscape panels of equal height; the Features side column gets portrait
pages of equal shape, as the title-view picture already is. The single-page layout then
appears in exactly one place, a new Features section that shows the same view both ways.

Two vocabularies only: *single page* and *two-page spread* for the main screen, *single*
and *double page* for the comic. "Landscape" and "portrait" name the screen, never the
layout.

## Stages

- [x] **Stage 1, the captures.** Re-shoot four spread captures on this PC: searching
  titles, the speech bubble index, the wiki, and a comic open double page. With the two
  existing spread shots that is the whole grid. The existing ones were shot on the
  headless probe (`scripts/gui-probe.sh`) on this PC's 2560x1440 screen, the window
  1775x1365, booted onto the wanted tree node by the saved-node trick; the recorder
  (`scripts/record_demo.py`) films the same spread at 1760x1300 and is the other
  source. Then crop the right page out of the spread captures for the Features
  close-ups (search, index, history; the title view is already done this way). One
  capture serves both uses. Keep the wiki's portrait capture as its close-up: the wiki
  is a full-window screen, and a page of it is just a narrower window. The three
  stacked single-page captures retire from everywhere else. The README shares these
  files, so it inherits the new shots.

  *Done 2026-11-01.* All six grid shots were re-shot, not four: the spread lost its
  gutter that morning (954f6e1e), and the two older spread shots still showed it. The
  window is now 1749x1365 and its right page is the 874x1320 strip at x 875, y 45 (under
  the menu bar). A spread keeps the file's old name, and its page crop adds `-page`:
  `screenshot-search-titles-page.jpg`, `screenshot-speech-bubble-index-page.jpg`,
  `screenshot-reading-history-bg-page.jpg`; `screenshot-title-view.jpg` is the crop of
  `screenshot-selecting-a-title.jpg`. History was a fifth capture, of
  `record_demo.py`'s canned history rather than the profile's own.
  `screenshot-carl-barks-wiki-2.jpg` is unchanged. Same content as before: Chronological;
  The Seven Cities of Cibola (Uncle Scrooge #7), whose pages 1 and 2 are also the comic's
  double page; "lost" (six titles now); the Speech Bubble Index's ah–aj words with
  airline open; Voodoo Hoodoo. They were shot headless (`BARKS_PROBE_SCREEN=2560x1440`) from a
  scratch copy of the profile with `log_level = DEBUG` and the layout set to
  *Two-page spread*. The fun view and backgrounds are random: the menu bar's refresh
  button and a reboot re-roll them.
- [x] **Stage 2, the pictures in the page.** The Screenshots grid: six spread captures.
  The comic reader section shows the double page as a wide figure under its paragraph,
  not in the 340 px side column. A new layout section gets the one paired figure on
  the page: a title view as a spread beside the same view as a single page, each
  captioned. Every other Features close-up is a cropped page. Every screenshot `<img>`
  states its file's size, and all of them have changed in stage 1: a spread is
  `width="1749" height="1365"`, a page crop `width="874" height="1320"`.

  *Done 2026-11-01.* The layout section, "Two-Page Spread or Single Page", is first in
  Features with a heading and the pair only; its text is stage 3's. The pair is
  `screenshot-selecting-a-title.jpg` beside `screenshot-title-view-single-page.jpg`
  (874x1365, a new capture of the same title on *Single page*), captioned with the
  setting's name and the screen it suits; `.layout-pair` gives the grid tracks the two
  widths, so the pictures come out one height. The comic reader's double page is an
  `art-panel--wide` figure, at most 900 px, under the section's buttons. The index
  section stacks the index crop over the search crop in its side column. The wiki's
  close-up lost its 45 px title bar to match the other crops' shape (873x1320). The
  history spread `screenshot-reading-history-bg.jpg` was then on no page, and stage 3
  deleted it: only its crop is shown.
- [x] **Stage 3, the text.**
  - Merge the Introduction's two layout bullets into one, in the setting's own words:
    a two-page spread on a landscape screen, the tree on the left page and the story on
    the right, a single page on a portrait screen.
  - Tie each layout to the devices it suits, in that bullet and in the new Layout
    section: a single page on a portrait screen, such as a 2-in-1 held upright; a
    two-page spread on a landscape screen, such as a large monitor or a 4K TV. Say "a
    2-in-1 held upright", not that a 2-in-1 is portrait: it turns either way, and
    *Match the screen* follows how it is held. The Introduction's separate devices
    bullet (laptops, 2-in-1 touchscreens, 4K TVs) then folds into this one or keeps
    only the platforms.
  - Drop "on a Wide Monitor" from the first caption, and say once under the
    Screenshots heading that all of them are the spread.
  - Add a Features section for the layout, drawn from the how-to's Layout paragraph,
    placed first because it frames every section after it.
  - Rename "Fullscreen Reader" to "The comic reader": on the spread a comic opens two
    pages at a time, as printed, one on the single page, and the Double Page button
    switches the comic at hand. The 2-in-1 and 4K TV sentence stays.
  - Sweep the vocabulary to the two pairs above.

  *Done 2026-11-01.* The Introduction's reader bullet keeps only the fullscreen mode,
  and its layout bullet carries the double page as well as the devices; the devices
  bullet keeps only the platforms. The Layout section's two paragraphs follow the
  how-to's, and say that *Match the screen* changes over when a 2-in-1 is turned (the
  app re-decides on a rotation, `AppWindowGeometry.evaluate_layout`). "The Comic Reader"
  is in title case like the other headings, and no longer says the comic opens in a
  new window: it opens in the reader, in the same window.
- [x] **Stage 4, the checks.** `uv run scripts/check_docs_refs.py`, `bunx cspell`, the
  page rendered headless at 1400 wide and at phone width, then the README's shared
  screenshots looked at once.

  *Done 2026-11-01.* Both checks pass; the Introduction and Features tabs were rendered
  at 1400 and 390 wide with no sideways scroll. The README's pictures were all spreads by
  then, so its side-by-side row became one column of four under a line saying they are
  all on a landscape screen, and its text took the same sweep as the page: the layout
  bullet names the two layouts, the screens each suits and the setting's three values,
  and the comic reader bullet says how a comic opens on each and what *Double Page*
  does.

## The cheaper alternative

Keep the existing pictures and only caption each with the layout it shows. That fixes
the confusion but not the look. The route above costs about five spread captures and an
afternoon of HTML.
