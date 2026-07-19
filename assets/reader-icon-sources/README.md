# Reader chrome icon sources

Clean monochrome (white-on-transparent) replacements for the on-brand chrome
icon set (July 2026 design pass). Drawn as SVG, rasterised to 512x512 PNG via:

    inkscape <name>.svg --export-type=png --export-filename=<name>.png -w 512 -h 512

The rendered PNGs are installed into the external Reader Files bundle (which is
data, not version-controlled here — these SVGs are the source of truth for
regeneration). Install locations differ by icon, matching where the app loads
them (see `core/system_file_paths.py`):

    <reader_files_dir>/Reader Icons/ActionBar Icons/   # single/double-page, goto-title
    <reader_files_dir>/Various/                        # menu-hamburger-icon, eye icons

- `icon-single-page` / `icon-double-page` — comic-reader page-mode toggle
  (replaced the old white-on-black boxed versions).
- `icon-goto-title` — wiki reader "go to the comic" action
  (replaced the full-colour "COMIC" book clip-art).
- `menu-hamburger-icon` — fun-image options toggle. Now a transparent
  white glyph (was white-on-black boxed) so the app can colour it dark over
  the accent-filled circle.
- `icon-eye-open` / `icon-eye-off` — the bottom title panel's peek toggle
  (open = info panel showing, slashed = hidden). Tinted to the theme accent.
