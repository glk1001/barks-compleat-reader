# Cover CCBDL locations bootstrap

`locate_covers.py` bootstrap-generates the `COVER_LOCATIONS` table in
`barks_fantagraphics/barks_covers.py`: for each front cover in `BARKS_COVERS` it finds
the CCBDL cover-gallery reprint row (INDUCKS code `W <pub> <issue>-00`) in the
barks-wiki index `../barks-wiki/okf/reference/data/ccbdl-contents.md` (**read-only**,
maintained by the barks-wiki repo) and converts the printed book page to the zip body
page using the index's per-volume delta segments.

Run:

```bash
uv run python experiments/covers/locate_covers.py
```

The output is a review report: the paste-ready dict, unmatched covers in both
directions, duplicate-code resolutions, hand-assignment candidates for the
INSIDE_FRONT/BACK covers, and matches skipped for lack of delta data (vol 30).
`COVER_LOCATIONS` is hand-maintained after the initial paste — rerunning the script
only helps review, it does not write to any repo file.
