# Backlog — Future Improvements

Enhancement ideas grouped by area. Checkboxes track status. This is a living
document; add items as they surface and tick them off as they land.

Last updated: 2026-07-08.

---

## Wiki reader (OKF integration)

The wiki is integrated as a top-level app screen. Remaining polish:

- [ ] **In-wiki search** — find pages within the OKF bundle from the wiki screen.
- [ ] **Escape-back inside the wiki screen** — currently only mouse4 works while
      embedded; the app owns keyboard keys, so Escape doesn't navigate back.
- [ ] **Async panel textures** — load large panel-background images off the UI
      thread to avoid stalls.
- [ ] **Shared kv action-bar extraction** — the main screen, comic reader, and
      wiki screen each define near-identical action bars; extract one shared
      `.kv` bar.

Known limitation (intentional, not a reader fix): links under the bundle's
`source/web` tier (inducks) don't navigate — they are raw scraped `.html`, not
`.md`. That's bundle curation, owned by the read-only `../barks-wiki` repo.

## Data completeness (`barks_fantagraphics`)

- [ ] **Regenerate unauthored dates** — ~107 `_TODO = (0, 0, 0)` placeholder
      entries in `comic_book_info.py` mark stories with unknown authored dates.
      Regenerate from the bibliography source (`experiments/bibliography/`).
- [ ] **Reconcile date discrepancies** — ~24 dates flagged as differing from
      Barrier's bibliography when `barks_bibliography.py` was generated.
- [ ] **Tag data validation** — resolve the `TODO: NEED TO CHECK THESE` markers
      in `barks_tags_data.py` (incomplete data validation).

## Naming consistency (cross-repo — deferred)

> ⚠️ **Not low-risk.** These names are public API consumed by the sibling repos
> `../barks-ocr` and `../barks-comic-building` (~36 files). A rename is a
> coordinated, breaking, 3-repo change — do it deliberately, all at once, not
> piecemeal.

- [ ] **`srce` → `source`** — 462 in-repo occurrences, baked into public
      `ComicsDatabase` / file-path resolver method names.
- [ ] **Normalize `upscayl` spelling** — `upscayl` / `upscayled` / `upscaled`
      used inconsistently. Note: "Upscayl" is a real tool, so `upscayled`
      ("processed by Upscayl") may be a deliberate coinage — confirm intent
      before flattening to `upscaled`.

## Architecture / testability

- [ ] **Architecture deep-dive** — run the `improve-codebase-architecture`
      exploration to find shallow modules to deepen and untested seams to
      surface across the codebase.

---

## Done (recent)

- [x] **Strengthen weak generic type annotations** (2026-07-08, commit 430e04c) —
      all 37 bare `dict`/`list`/`tuple` annotations parameterized; also fixed 3
      latent type issues the stronger types exposed.
- [x] **Search consolidation RFC** — `comic_search.py` facade + `search_ports.py`
      protocols isolating Whoosh; screens migrated; `fake_search.py` test adapter.
- [x] **`barks_fantagraphics` high/medium-impact refactors** — god-module splits,
      panel geometry extraction, `ComicsDatabase` slimming, broad test coverage.
