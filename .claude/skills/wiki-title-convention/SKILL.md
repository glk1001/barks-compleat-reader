---
name: wiki-title-convention
description: How to join Barks Reader stories to barks-wiki pages and how to display story titles. Use when mapping a story to a wiki page or slug, rendering a story title in the UI, working on okf-reader integration, or reading anything under okf/ in the sibling barks-wiki repo.
---

# Wiki title convention — how to join and display

The barks-wiki bundle and this app share one rule: **identity is the plain canonical title;
parentheses are presentation**, applied at render time from `is_barks_title`. Concretely:

1. **Joining to wiki pages:** map a story via `cbi.get_title_str()` → the wiki story page's
   frontmatter `title` (exact match), or its filename slug at
   `okf/concept/stories/<series>/<slug>.md`. The slug convention: lowercase, apostrophes
   dropped (not hyphenated), every other run of non-alphanumerics becomes a single hyphen,
   leading/trailing hyphens stripped — e.g. You Can't Guess! → `you-cant-guess`,
   Ten-Dollar Dither → `ten-dollar-dither`. Frontmatter titles, slugs, and H1s are always
   plain — never parenthesised.
2. **Displaying titles:** when the Barks Reader UI shows a story title, apply the parentheses
   convention from our own data: `f"({title})" if not cbi.is_barks_title else title`. Never
   scrape parentheses (or their absence) out of wiki markdown — the wiki's `chronology.md`
   shows parenthesised assigned titles, but that is the same rule applied by its generator at
   generation time, not data to parse back.
3. **Keep okf-reader generic:** it must not grow a `barks_fantagraphics` dependency or any
   parens logic. If the viewer needs to show a decorated title, the app's integration layer
   computes the display string (per #2) and passes it in; okf-reader keeps joining on
   frontmatter `title` as-is (e.g. its backgrounds matching).
4. **Never parse wiki data tables for facts we own.** `okf/reference/data/*.md` (chronology,
   payments, tags…) are generated from this repo's `barks_fantagraphics` — for
   `is_barks_title`, issue, dates, etc., import `BARKS_TITLE_INFO` directly; the wiki tables
   are downstream of us and their display format can change.

Reminder: `../barks-wiki` is **read-only** from this repo — never edit, regenerate, or commit
there. Raise the need instead.
