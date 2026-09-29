# Plan: advanced Tag and Word search

<!-- cspell:ignore scroge -->

> Status: **planned 2026-09-29; phase 0 done.** Saved here so the plan survives across
> machines and sessions. To resume, ask for "the next phase of
> docs/plans/advanced-search.md". Tick a phase off here (with its commit) as it lands.
>
> - Phase 0 tag bug fixes: DONE 2026-09-29 ("fix(search): tag search no longer recurses on one letter...")
> - Phase 1 result types + set operations: TODO
> - Phase 2 substring word list: TODO
> - Phase 3 tag substring + counts: TODO
> - Phase 4 query parser: TODO
> - Phase 5 lexicon expansion: TODO
> - Phase 6 engine leaves + evaluator: TODO
> - Phase 7 multi-term highlighting: TODO
> - Phase 8 typed queries in the word box: TODO
> - Phase 8a extract ChipRow: TODO
> - Phase 9 word chip list: TODO
> - Phase 10 tag chip list: TODO
> - Phase 11 era filter: TODO
> - Phase 12 word search limited to tagged stories: TODO

## Context

Word search never runs what the user types. Typing only prefix-filters the cleaned term list
(`search_screen.py:480`). Picking a word then calls `find_words`, which quotes it into a literal
Whoosh phrase (`whoosh_search_engine.py:279-315`). So the app has no multi-word query, no
operators, no wildcards and no word forms. Tag search matches only the start of a name, returns
tags in random order (`list(set(...))`), and recurses forever on a one-character query
(`title_search.py:133-150`, hidden by the UI's two-character minimum). Title search is out of
scope.

Goal: all eight features chosen, typed syntax for keyboard users, and a chip list that
can be driven with the six remote keys. Nothing needs the shipped Whoosh index rebuilt (it is
built in ../barks-ocr): `unstemmed` keeps positions, so phrases and span-NEAR already work.

### Decisions (confirmed 2026-09-29)
- AND = **same story**; NOT = **story level**; phrase and NEAR stay **within one bubble**.
- Word forms apply **automatically to bare typed words**, only when that form exists in the
  index. Quotes force an exact match; words picked from the list stay exact.
- Tag chips: **per chip include → exclude → removed**, plus a global ALL/ANY switch.
- Era filter: **submitted year**, fixed chips from `CHRONO_YEAR_RANGES`
  (`core/reader_consts_and_types.py:69`), passed in by the reader. `year:` and `vol:` typed
  qualifiers give exact ranges.
- Input: **both** typed syntax and chips.

### Defaults assumed (change on review if wanted)
- NEAR distance 5, words in any order; `NEAR/n` overrides it.
- Lowercase `and/or/not` also work as operators. They are stop words, so they can never be
  searched for anyway. `&`, `|`, `+` and a leading `-` are accepted too.
- Volume filter is typed only (`vol:7`, `vol:5-8`); 30 chips is too many for a remote.
- Result order stays alphabetical; combined queries show a hit count per story.
- Enter on a word's text still searches that word alone; the `+` beside it adds it to the chip
  list.

## Design

**Our own small query AST and parser, not Whoosh's QueryParser.** Whoosh's `And` works per
document (one bubble), so "same story" has to be evaluated in Python anyway. The fake port can
implement an AST, and the parser never raises: bad syntax falls back to a literal search with a
notice. Whoosh builds only the leaves: `Or([Term])`, `_parse_literal` for phrases, and
`SpanNear2`/`SpanOr` for NEAR (Whoosh 2.7.4).

Grammar: `or_expr := and_expr (OR and_expr)*`;
`and_expr := unary (AND? unary)*` (a bare space means AND);
`unary := (NOT|-) unary | + unary | primary`;
`primary := ( … ) | "phrase" | WORD [NEAR[/n] WORD] | qualifier` (`tag:"x"`, `year:1950-55`,
`vol:7`). `*` and `?` inside a word make it a wildcard, which needs at least 2 literal letters and
expands to at most 200 terms. A leading `-` counts as NOT only at the start of a token, so
`indo-china`, `500,000,000...` and `G.I.` stay single words.

### New Kivy-free modules (`src/barks-fantagraphics/src/barks_fantagraphics/`)
- `search_results.py`: `SpeechInfo/PageInfo/TitleInfo/TitleDict` move here and are re-exported
  from `whoosh_search_engine`, because ../barks-ocr `tools/whoosh_find.py` imports them. It adds
  `merge_title_dicts`, `intersect_titles`, `subtract_titles`, `restrict_titles` and
  `hit_counts`.
- `search_query.py`: AST nodes; `parse_query(text) -> ParsedQuery` (never raises; carries a
  `ParseError(message, position)`); `has_query_syntax(text)`; `Combine(ALL|ANY)`;
  `query_from_words(words, combine)`; the leaf types sent to the engine
  (`AnyTerm | Phrase | Near`).
- `search_terms.py`: `TermLexicon(cleaned_terms)` with `matching` (exact, then prefix, then
  substring), `expand_wildcard`, `variants` (-s/-es/-ed/-ing/-'s, y→ies, the Barks dropped-g
  `-in'`, and the reverse; only forms present in the index), `suggest` (difflib, cutoff 0.75)
  and `is_multi_word`. One cached instance per index directory, like `_ALPHA_SPLIT_CACHE`
  (`comic_search.py:74`).
- `search_filters.py`: `SearchFilter(year_range, volumes, tag_titles)` with `allows()`;
  `parse_qualifiers`.
- `search_evaluate.py`: `evaluate_query(node, port, lexicon, *, speaker, search_filter)` returns
  a `WordQueryResult` (`title_dict`, `hit_counts`, `highlight_terms`, `notices`, `suggestions`,
  `used_literal_fallback`, `error`). The rarest AND leaf runs first, and its story set is passed
  down as a title filter.
- `tag_query.py`: `TagSelection(included, excluded, combine)`, `TagMatch(item, label,
  title_count)`, `parse_tag_query(text)` and `titles_for_selection(sel, ts)`. Groups expand
  through the existing `get_all_tags_in_tag_group`.

### Changes to existing files
- `search_ports.py`: add
  `find_bubbles(query, speaker=None, titles: frozenset[str] | None = None) -> TitleDict` to
  `FullTextSearchPort`. The sibling repos have no other implementers; say so in the commit
  message. `find_words` keeps its literal meaning.
- `whoosh_search_engine.py`: implement `find_bubbles`. The title restriction becomes
  `searcher.search(q, filter=Or([Term("title", t)…]))`.
- `testing/fake_search.py`: add an optional `bubbles: list[FakeBubble]` corpus with a regex
  tokenizer. The existing canned path stays.
- `title_search.py`: fix the recursion; sort results; add `get_tags_matching(text) ->
  list[TagMatch]` (prefix, then substring, with counts).
- `comic_search.py`: thin facade methods `get_words_matching`, `run_word_query`,
  `find_word_set`, `suggest_words`, `get_tags_matching`, `titles_for_tag_selection` and
  `parse_tag_query`.
- `barks_reader/core/reader_formatter.py`: add `mark_terms_in_text(terms, …)`, one alternation
  regex with the longest term first so tags never nest. `mark_phrase_in_text` wraps it.
- `barks_reader/core/search_state.py` (new): `WordBasket`, `TagBasket` (include → exclude →
  removed) and `EraChoice`.
- `barks_reader/ui/index_screen.py`: the popup takes `highlight_terms=None`, so the speech index
  screen is unaffected.
- `barks_reader/ui/search_chip_row.py` (new): the speaker-row logic generalized into `ChipRow`,
  used for speakers, era and "Only in tagged stories".
- `barks_reader/ui/search_screen.py` and `.kv`: the UI, phase by phase below.
- `barks_reader/core/log_markers.py`: new markers, each with a `loguru_sink` unit test.

## Phases (each its own commit, full gate green at each)

0. **Tag bug fixes.** Remove the recursion and make the order deterministic. Tests in
   `test_title_search.py`.
1. **`search_results.py` split and set operations.** Pure refactor plus re-export. Test that the
   re-exported names are the same objects.
2. **Substring word list.** `TermLexicon.matching`. The screen delegates to it; substring from
   3 characters; capped at 300 rows plus a "…N more" row. Exact match first, so the `airline`
   GUI test is unaffected. New GUI test `test_word_search_matches_inside_a_word`, and a
   benchmark (under 10 ms over 23k terms).
3. **Tag substring and counts.** `get_tags_matching`. The chip gets a separate `count_text`
   property; `.text` stays the tag name, because focus markers and the GUI tests match on it.
   A chip is auto-picked when it is the only one **or an exact alias match** (keeps the
   `africa` GUI test valid). Recheck `MULTI_GROUP_STEPS` in the GUI tag tests against the new
   order.
4. **Parser** `search_query.py`: table-driven tests plus a Hypothesis "never raises" property.
5. **Lexicon expansion**: wildcard, variants, suggest. Tests and a suggest benchmark.
6. **Engine leaves and evaluator**: `find_bubbles` (Whoosh and fake), `evaluate_query`, facade.
   Extend the temp-index builder in `test_whoosh_search_engine.py` (~:680); new
   `test_search_evaluate.py` covers story-level AND/NOT, OR, bubble-level phrase and NEAR,
   literal fallback, suggestions and pushing the title restriction down.
7. **Multi-term highlighting** in the formatter and the popup.
8. **Typed queries in the word box.** Enter runs `run_word_query` when `has_query_syntax(text)`
   is true or no word matches; otherwise the existing chip path. Notice row, suggestion rows,
   hit counts, and the speaker filter re-runs the active query. Markers `WORD_QUERY_RUN`,
   `WORD_QUERY_FALLBACK`, `WORD_SUGGESTIONS`. GUI tests: AND query → bubble popup; `(gold` falls
   back; `scroge` → suggestion → query.
8a. **Extract `ChipRow`** from the speaker row (no behaviour change; `search_screen.py` is 1,283
   lines).
9. **Word chip list, ALL/ANY.** A `[word][+]` row pattern, like the existing title/speech
   sub-focus. The chip row `[ALL|ANY] [gold ×] [mine ×]` takes no height while empty. Keys:
   Right → `+`, Enter to toggle; Down from the input goes to the chip row. Markers
   `WORD_BASKET_CHANGED`, `WORD_BASKET_MODE`. GUI test combining two words by keyboard.
10. **Tag chip list.** Same pattern, with include/exclude cycling and ALL/ANY. Typed
    `a + b | c -d` fills the chips. Markers `TAG_BASKET_CHANGED`, `TAG_BASKET_MODE`,
    `TAG_COMBINED_RESULTS`. GUI test.
11. **Era filter.** A single-choice ChipRow in the right panel for both Tag and Word modes;
    `year:`/`vol:` qualifiers. Marker `ERA_FILTER_SET`. GUI test that the era filter narrows tag
    results.
12. **Word search limited to tagged stories.** An "Only in: …" chip in the Word panel, shown when
    tags are selected; `tag:"…"` qualifier. Marker `WORD_TAG_FILTER_SET`. GUI test. Final docs
    pass.

Docs, updated along the way: `docs/how-to-use.md` (a new "Search tips" syntax table; AND means
same story; the speaker filter applies to each word), `docs/code-walkthrough.md` §7.4 (the
pipeline; fix the stale `search_screen.py:121` → :143), `cspell-words.txt`, and a
`docs/BACKLOG.md` entry.

## GUI tests (`src/barks-reader/tests/gui/`)

Existing tests: only one breaks, and only because of a rule the plan sets.
- `test_a_tag_groups_members_are_walked_and_picked_by_keyboard` relies on `africa` producing a
  single chip that is picked as it is typed. With substring matching (phase 3) it also matches
  `central africa` and `south africa` (checked against `BARKS_TAG_ALIASES`). Fix it in the app,
  not the test: auto-pick when there is exactly one chip **or an exact alias match**. Africa then
  still comes first and gets picked, and its members are still inserted directly under it, so
  the test's Down/Up walk is unchanged.
- `south` has no matches beyond the prefix ones, so `MULTI_GROUP_STEPS = 2` still lands on
  South America. Re-check it in phase 3 anyway.
- `airline` (word) and `scrooge` (tag): exact and prefix matches sort first, and Return on a
  plain word still picks the first chip. Unchanged.
- Title tests (`vacation`, `vac`, `zzzz`): title search is out of scope. Unchanged.

Helper changes in `barks_gui/search.py`:
- `_results_line` waits on each keystroke's results line. Typed syntax (spaces, quotes, `(`, `-`,
  `+`, `|`, `tag:`) must still log `WORD_SEARCH_MATCHED` / `SEARCH_TAG_RESULTS` on every
  keystroke, even when nothing matches. Otherwise `type_slowly` waits until it times out. Add a
  unit test that the tag path logs for operator text, and confirm that `pattern()` escapes
  quotes and parentheses.
- New helpers: `run_typed_query(d, text)` (type, Return, wait for `WORD_QUERY_RUN`);
  `add_to_basket(d)` (Right to `+`, Return, wait for `*_BASKET_CHANGED`); `choose_era(d, label)`.
- `barks_gui/expected.py`: per-query expected counts read from the real index or tag data, like
  `title_search_count`, so tests assert real numbers rather than just "at least 1".

New tests in `test_search.py`, one or two per UI phase, using only the six keys plus typed
text:
- Phase 2: `test_word_search_matches_inside_a_word`
- Phase 3: `test_tag_chips_match_inside_a_name_and_show_counts`
- Phase 8: `test_a_typed_and_query_lists_stories_with_both_words` (then opening the bubble
  popup), `test_bad_syntax_falls_back_to_plain_text` (`(gold`),
  `test_a_misspelling_offers_suggestions` (`scroge` → Return on the suggestion)
- Phase 9: `test_two_words_are_combined_by_keyboard` (ALL → ANY flip)
- Phase 10: `test_tags_are_combined_and_excluded_by_keyboard`
- Phase 11: `test_the_era_filter_narrows_tag_results`
- Phase 12: `test_a_word_search_is_restricted_to_a_tag`

Other suites the change affects:
- `test_taps.py`: new tappable widgets (`+` buttons, chip rows, era chips) need
  `core/tap_targets` entries and one tap test that picks a chip by what it shows.
- The leak tests (`-k leave_no`): add a search round trip that fills and clears the chip lists,
  so the new chip widgets are counted.
- The random walk (`--soak`): it enters search screens; the new focus rows need no special
  handling, but run a soak once after phase 10.
- Timing budgets: add the new markers to `TIMED`/`BUDGETS` in `barks_gui/timings.py` only if they
  carry `{elapsed}`. The plan gives none an `{elapsed}` field.
- `scripts/run_gui_matrix.sh`: run the search tests under the virtual-keyboard and theme variants
  once the chip rows exist (colours, and the docked keyboard covering the box).

## Risks to watch
- Widget count per keystroke (hence the 3-character substring minimum and the 300-row cap).
- Broad wildcards or ORs near the 100k hit limit: term cap, notice on reaching the limit, rarest
  leaf first.
- Wildcards and forms can't reach words the term cleaning removed; exact and quoted typing still
  reach them.
- The 35% left column gets crowded: chip rows take no height while empty, and filters go in the
  right panel. Check with screenshots (`verify` skill) at the pinned window size.
- New widgets may need `core/tap_targets` entries for `test_taps.py`.

## Verification (per phase)
- `uv run pytest`, `bash scripts/full-lint.sh` (ruff, ty, pyrefly, import-linter, cspell,
  benchmarks) and `uv run lint-imports`.
- UI phases: `bash scripts/run_gui_tests.sh --headless -k search` and then the full headless
  suite; `scripts/check_gui_keys.py` (six keys only); screenshots through the `verify` skill.
- `graphify update .` after code changes.
- After pushing phases that touch Windows-sensitive code, watch CI's Windows leg.
