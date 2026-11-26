# Reader icon sources

The SVG source of every icon the app loads, and of the pictures of them in the how-to.
These are the source of truth: the PNGs the app reads are in the Reader Files folder,
which is data and not version-controlled here, and are rendered from these.

A glyph is drawn white on a transparent ground, 512x512, with rounded strokes 44 wide
(the six icons of the July 2026 design pass are drawn smaller, at 34 to 36), and the app
tints it. A few are pictures in their own colours: the two contrast icons, the speech
bubble (traced from the hand-drawn original) and the goto-title button.

To render them all, into Reader Files and into `docs/` for the how-to (which shows the
white glyphs in black), with Inkscape:

    uv run scripts/render_reader_icons.py
    uv run scripts/generated_files.py --record icons

`scripts/render_reader_icons.py` holds the table of where each one goes
(`--list` prints it), matching where the app loads them (`core/system_file_paths.py`):

    <reader_files_dir>/Reader Icons/ActionBar Icons/   # the action bars' icons
    <reader_files_dir>/Various/                        # the eyes, the speech bubble, the goto-title button

A new icon is a new SVG here and a line in that table; a test fails while the app needs
an icon the table lacks. The three `how-to-*.svg` files are pictures of things the app
draws itself (the filter button and the read dots), which only the how-to needs.

After a change, regenerate the how-to's pages too: they show the icons
(`scripts/generate_how_to_pages.py`).
