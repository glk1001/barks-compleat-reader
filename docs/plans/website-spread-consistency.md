# Plan: one layout story on the website

> Status: **review done 2026-10-30, nothing changed yet.** The review is of
> `website/app.html` as it stood at commit 618a5c39, after the two-page spread landed
> (`docs/plans/two-page-spread.md`). Work starts 2026-10-31. Tick the stages off here, with
> their commits, as they land.

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
| `website/screenshot-reading-history-bg.jpg` | portrait window, tree stacked over the history |
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

- [ ] **Stage 1, the captures.** Re-shoot four spread captures on this PC: searching
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
- [ ] **Stage 2, the pictures in the page.** The Screenshots grid: six spread captures.
  The comic reader section shows the double page as a wide figure under its paragraph,
  not in the 340 px side column. A new layout section gets the one paired figure on
  the page: a title view as a spread beside the same view as a single page, each
  captioned. Every other Features close-up is a cropped page.
- [ ] **Stage 3, the text.**
  - Merge the Introduction's two layout bullets into one, in the setting's own words:
    a two-page spread on a landscape screen, the tree on the left page and the story on
    the right, a single page on a portrait screen.
  - Drop "on a Wide Monitor" from the first caption, and say once under the
    Screenshots heading that all of them are the spread.
  - Add a Features section for the layout, drawn from the how-to's Layout paragraph,
    placed first because it frames every section after it.
  - Rename "Fullscreen Reader" to "The comic reader": on the spread a comic opens two
    pages at a time, as printed, one on the single page, and the Double Page button
    switches the comic at hand. The 2-in-1 and 4K TV sentence stays.
  - Sweep the vocabulary to the two pairs above.
- [ ] **Stage 4, the checks.** `uv run scripts/check_docs_refs.py`, `bunx cspell`, the
  page rendered headless at 1400 wide and at phone width, then the README's shared
  screenshots looked at once.

## The cheaper alternative

Keep the existing pictures and only caption each with the layout it shows. That fixes
the confusion but not the look. The route above costs about five spread captures and an
afternoon of HTML.
