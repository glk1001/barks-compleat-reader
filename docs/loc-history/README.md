# LOC history

A one-off visualization of this repo's **hand-authored Python** growth over its first
year, split by workspace package. Kept because the shape turned out to be interesting.

## Files

- **`generate_loc_by_package.py`** — walks git history and prints, as JSON, the
  per-day newline count of every tracked `*.py` file bucketed by package (plus `tests`
  and `scripts`). Excludes generated data modules (`barks_bibliography.py`,
  `barks_covers.py`) and the `experiments/` & `scraps/` scratch dirs.
- **`loc-growth.html`** — a self-contained stacked-area chart (no external assets) that
  embeds a snapshot of that JSON. Open it in a browser. The three smallest packages are
  folded into an **Other** band; `tests` and `scripts / entry` are their own bands.

## What the numbers meant on 2026-07-21

Authored total **79,506** lines (all `.py` incl. generated data was 113,638):

| Band | Lines | Share |
|---|---:|---:|
| `barks_reader` | 27,277 | 34.3% |
| tests | 26,784 | 33.7% |
| `barks_fantagraphics` | 14,176 | 17.8% |
| scripts / entry | 5,291 | 6.7% |
| `okf_reader` | 3,583 | 4.5% |
| Other (`comic_utils` + `barks_build_comic_images` + `barks_kivy_ui`) | 2,395 | 3.0% |

## Refreshing the snapshot

```bash
uv run python docs/loc-history/generate_loc_by_package.py > /tmp/loc.json
```

Then replace the `OBJ = {...}` literal near the top of the `<script>` block in
`loc-growth.html` with the new JSON. (The chart is a static snapshot by design — it
carries its own data so it stays viewable without the repo.)

## Method notes

- One data point per calendar day, taken at that day's **last** commit; days with no
  commit carry the previous value forward.
- Counts raw newlines — no blank- or comment-line filtering.
- "First appeared" dates reflect the **git layout**, not first authorship. The
  workspace was reshuffled into `src/<package>/src` on 2025-09-29, so several bands
  spring up together that day.
