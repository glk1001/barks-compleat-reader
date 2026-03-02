# How to Use the Barks Reader

The Barks Reader is designed to be intuitive, but this guide covers the details for those who want them.

---

## Concept

The Barks Reader gives you full access to Carl Barks's complete published output as presented
in the Fantagraphics *"The Complete Carl Barks Disney Library".* It knows exactly which
stories appear in which volumes and on which pages, and presents them through several
complementary navigation systems. And if you have a touchscreen 2-in-1 or hybrid 16-inch laptop
you will get a great Barks reading experience.

**No censorship.** Where Fantagraphics made alterations to Barks's original artwork — replacing
or modifying panels for editorial reasons — the Reader includes override image files that
restore the original artwork. These are applied automatically. You can turn specific controversial fixes
(like 'Larkies' to 'Harpies') off individually in Settings if you prefer the Fantagraphics versions.

---

## Main Screen Layout

### Top Menu Bar

The bar across the top of the main screen contains:

- **App icon** — clickable; navigates to the story associated with whichever image is
  currently showing as the icon.
- **Quit** — closes the application.
- **Fullscreen** — toggles between windowed and fullscreen mode.
- **Back** — returns to the previously selected navigation node.
- **Collapse** — collapses all expanded nodes in the navigation tree.
- **Refresh** — randomly refreshes the background and panel images.
- **⋯ Menu** — opens a dropdown containing **Settings**, **How To**, and **About**.

### Navigation Tree (left panel)

The tree on the left is the primary way to find stories. Its top-level sections are:

- **Intro** — the introductory articles for the *Compleat Barks Reader* project.
- **The Stories** — all Barks stories, browsable in four ways:
  - *Chronological* — organised by publication year.
  - *Series* — grouped by the comic series they appeared in (Comics & Stories, Donald Duck Adventures, 
    Uncle Scrooge Adventures, etc.).
  - *Categories* — thematic groupings.
- **Search** — find stories by title text or by tag.
- **Index** — two indexes: *alphabetic* and *speech bubbles*.
- **Appendix** — supplementary articles and extra info.

### Top Image Area

A large background image sits behind the navigation tree. It is decorative but also interactive:

- A **down-arrow button** at the bottom of the image navigates to the story associated with
  that image.
- Click **Refresh** in the menu bar to pick a new random image.

### Bottom Panel

The bottom half below the main tree content switches between two modes:

**Comic View** — shown when a story is selected in the tree. Displays the story's title,
publication info, and a sample panel. Contains:

- A **title portal button** (bottom right) that opens the comic reader directly.
- A **last page read** indicator — the Reader remembers where you left off, and the portal
  button takes you back there.
- An **override toggle** — lets you turn off the censorship fix for this specific story.
- A **partially transparent collapse button** (top right of the bottom view) that hides the
  title info to show just the panel image. The portal button remains clickable even when
  collapsed.

**Fun View** — shown when no specific story is selected. Displays a random comic panel.

- A **category filter button** (top left) lets you control which panel categories are shown.
- **Left/right arrows** step through the panel history.
- An **up-arrow button** navigates to the story associated with the currently displayed panel.

---

## Reading Comics

Open a comic by clicking its **title portal button** in the bottom panel.

### Navigation

- **Click the left half** of the page to go back one page.
- **Click the right half** to go forward one page.

### Top Menu Bar (in the Reader)

The reader's menu bar is hidden by default in fullscreen mode. **Click near the top of the
screen** to make it appear. It contains:

- **Close** — return to the main screen.
- **Fullscreen** — toggle fullscreen mode.
- **Double Page** — display two pages side by side.
- **Go to Start / Go to End** — jump to the first or last page.
- **Go to Page** — opens a page selector showing all pages in the comic

---

<br>

## Settings

Open Settings from the **⋯ menu** on the main screen. Key options are:

| Setting                                       | What it does                                                   |
|-----------------------------------------------|----------------------------------------------------------------|
| *Fantagraphics Directory*                     | Path to the folder containing your Fantagraphics ZIP files     |
| *Double Page Mode*                            | Opens every comic in two-page view                             |
| *Goto Last Selection on App Start*            | Resumes where you left off when the app starts                 |
| *Go Straight to Fullscreen on App start*      | Launches the app in fullscreen                                 |
| *Go Straight to Fullscreen for Comic Reading* | Auto-fullscreen when opening a comic                           |
| *Show Title Info in Top View*                 | Toggles story title display above the tree                     |
| *Show Title Info in Bottom View*              | Toggles story title display in the bottom panel                |
| *First Use of Reader*                         | Reset this to re-run the first-launch setup (requires restart) |
| *Log Level*                                   | Controls how much is written to the log file                   |
| *Controversial Censorship Fixes*              | Individual toggles for some censorship fixes                   |

Settings are saved to `"barks-reader.ini"` and `"barks-reader.json"` in the app's config directory.

---

## Logging

Log files are written to the `"logs"` subfolder of the app's config directory. The level of detail
is controlled by the **Log level** setting (TRACE / DEBUG / INFO / WARNING / ERROR / CRITICAL).
For normal use, INFO is appropriate. If you are reporting a problem, set it to DEBUG before
reproducing the issue, then include the log file with your report.
