# Mutation testing (mutmut) — status & backlog

Mutation testing flips small pieces of source (`>` → `>=`, `and` → `or`, a
constant to a sentinel, …) and checks whether any test fails. A **survivor** is a
mutation no test caught — a line that is executed but not actually *asserted*.
Line coverage can't see these; that's the whole point of running mutmut.

## How to run

```bash
bash scripts/mutmut.sh --changed                  # only core/ modules you have touched
bash scripts/mutmut.sh --changed HEAD~3           # ...plus everything since a ref
bash scripts/mutmut.sh '*/core/reader_utils.py'   # one module
bash scripts/mutmut.sh '*/core/navigation/*'      # a subpackage
bash scripts/mutmut.sh                            # all of core/ (~6000 mutants, slow)
```

`--changed` is the everyday mode and the one to reach for by default. With no ref it
scopes to your working tree (staged, unstaged and untracked); pass a ref to also
include commits since then. One module is a minute or two — fast enough to run while
the code is still fresh — against many minutes for a full sweep.

The wrapper runs mutmut from `src/barks-reader/` (the layout mutmut's import
shadowing expects) and selects only the **Kivy-free** unit tests as the baseline —
the Kivy UI tests don't run in mutmut's `mutants/` sandbox and would abort the run.
See the header of `scripts/mutmut.sh` for the full rationale. Inspect afterwards:

```bash
cd src/barks-reader
uv run mutmut results | grep survived
uv run mutmut show <mutant-name>
```

It is **not** a CI/pre-commit gate — it reruns the test suite per mutant and takes
minutes. Treat it as an on-demand test-quality probe.

## Working practice

The survivor table below is a **snapshot, not a live scoreboard** — mutant numbering
shifts as soon as code moves, so don't try to keep it current. Going forward:

- **Run `--changed` when you write or rework pure-logic `core` code.** That is where
  the value is: catching a decorative test while you still remember the function.
- **Sweep the whole of `core/` occasionally** (a couple of times a year, or after a
  big refactor) to see whether anything drifted. Read the per-module counts, act on
  the one or two that look wrong, ignore the rest.
- **Leave settled modules alone.** `collection_page_groups` is at 0; it needs nothing
  until someone touches it.
- **Stop around ~90%+ on a pure-logic module.** Equivalent mutants make 100%
  unreachable, and the last stretch is where tests turn brittle — pinning log wording
  and defensive branches costs more in false failures than it buys.
- **Record equivalents** (see the table further down) so the next round skips them.
  Triage is the expensive part of mutation testing; fixing usually isn't.

The 436 🫥 *no covering test* mutants are a **separate problem** and won't move no
matter how many survivors get killed — they are code the Kivy-free suite never
reaches. That is the GUI acceptance-harness item in `docs/BACKLOG.md`, not this one.

## Two traps that produce fake numbers

mutmut calls `pytest.main()` **many times in one process**. Two consequences bite:

1. **`@given` property tests must be module-level, never test-class methods.** A
   class-scoped `@given` sees a fresh test-class instance on each in-process run and
   trips Hypothesis's `HealthCheck.differing_executors` from the second run onwards.
   That fails the baseline "clean test" step and **aborts the whole mutation run** —
   which is exactly what happened between commits `2fc4fee` and this one, leaving
   mutmut unrunnable. Module-level `@given` has no `self`, so the check cannot fire.

2. **`functools.cache` hides mutants.** A memoised result computed under mutant *N*
   is still cached when mutant *N+1* runs, so the mutated body never executes and the
   mutant is reported as a **false survivor**. This is what made all 53
   `collection_page_groups` survivors bogus: `_assert_tiling__mutmut_5` inverts an
   assert that a passing test *does* cover, yet "survived". Any test covering a
   `@cache`d entry point needs a `cache_clear()` autouse fixture (see
   `test_collection_page_groups.py`) — otherwise the survivor counts for that module
   are meaningless.

When triaging, prefer `uv run mutmut results` over the wrapper's summary if you need
raw mutant names; the summary collapses them to module counts.

## Latest full run — `core/` (2026-07-25)

| Outcome | Count |
|---|---:|
| 🎉 killed | 4112 |
| 🙁 survived | 1523 |
| 🫥 no covering test | 436 |
| ⏰ timeout | 3 |
| **total mutants** | **6074** |

Mutation score ≈ **73%** of checked mutants killed. For contrast, the deliberately
pure-and-well-tested `navigation.navigation_model` scores 60/61 (its one survivor is
a cosmetic error-message string, not worth a test).

Many survivors are expected low value — log/error-message strings, defensive
branches, `__repr__`-ish formatting. The number to act on is far smaller than 1523;
use the per-module counts below to pick where thin **assertions** cluster, then
`mutmut show` each candidate and decide.

## Pure-logic pass (2026-07-26)

Five Kivy-free modules burned down over two rounds. Round 1 swept all five; round 2
went back for the two clusters it had deferred (`get_title_info` and `observe`).

| Module (`barks_reader.core.*`) | Before | Round 1 | Round 2 |
|---|---:|---:|---:|
| `collection_page_groups` | 53 | **0** | 0 |
| `reader_utils` | 50 | **4** | 4 |
| `filtered_title_lists` | 22 | **1** | 1 |
| `hyphen_break_engine` | 19 | 12 | **6** |
| `reader_formatter` | 56 | 36 | **9** |
| **total** | **200** | **53** | **20** |

Round 2 re-ran only the two modules it targeted (487 mutants, 472 killed — **48 → 15**
for that pair); the other three carry forward untouched.

**Every one of the 20 remaining survivors is triaged as unkillable** — 14 equivalent
mutants and 6 dead-code artefacts, both listed below. There is no known real gap left
in these five modules, so this is the resting state, not a paused burn-down.

Round 1 covered all five modules: 967 mutants, 914 killed (**94.5%**). Note the
`collection_page_groups` "before" of 53 was entirely the `@cache` artefact above, so
that module's real starting point was better than the table ever showed; it now has
direct tests for `_group_ranges` / `_assert_tiling`, which previously had none.

## Survivors by module (backlog, most-survivors first)

Counts below are from the 2026-07-25 full run and are **stale for the five modules in
the table above**. They are also inflated wherever a module memoises (see trap 2).

| Module (`barks_reader.core.*`) | Survivors |
|---|---:|
| `comic_book_loader` | 185 |
| `navigation.tree_spec` | 184 |
| `view_pipeline` | 148 |
| `system_file_paths` | 131 |
| `comic_book_loader_platform_settings` | 110 |
| `image_selector` | 104 |
| `fantagraphics_volumes` | 69 |
| `archive_page_image_source` | 59 |
| `reader_formatter` | 56 → 9 |
| `collection_page_groups` | 53 → 0 |
| `reader_utils` | 50 → 4 |
| `platform_info` | 45 |
| `wiki_integration` | 44 |
| `reader_settings` | 41 |
| `reader_file_paths` | 37 |
| `screen_metrics` | 27 |
| `filtered_title_lists` | 22 → 1 |
| `comic_reader_manager` | 22 |
| `hyphen_break_engine` | 19 → 6 |
| `reading_history` | 17 |
| `user_error_messages` | 12 |
| `comic_book_page_info` | 12 |
| `reader_file_paths_resolver` | 10 |
| `image_pipeline` | 10 |
| `last_read_page_tracker` | 9 |
| `special_overrides_handler` | 8 |
| `json_settings_manager` | 8 |
| `reader_tree_view_utils` | 5 |
| `panel_image_loader` | 5 |
| `testing.fakes` | 4 |
| `page_info_adapters` | 4 |
| `minimal_config_info` | 4 |
| `reader_palette` | 2 |
| `navigation.navigation_model` | 2 |
| `config_info` | 2 |
| `comic_book_info` | 2 |
| `settings_notifier` | 1 |

## Known-equivalent survivors (triaged — do not re-triage)

Deliberately left alive in the five modules above. Each was checked; none is a missing
assertion, so writing a test for it would only add brittleness.

| Mutant | Why it is not worth killing |
|---|---|
| `reader_utils.get_paths_from_directory` ×2 | `.replace("\\", "/")` is a Windows-only path; unreachable on Linux/macOS. |
| `reader_utils.get_paths_from_zip` (mode arg) | `ZipFile(p, "r")` → `ZipFile(p)`; `"r"` **is** the default. Truly equivalent. |
| `reader_utils.read_text_paragraphs` (`rstrip(" ")` charset) | Distinguishing it needs a line ending in the literal `X` mutmut injects. |
| `reader_formatter.mark_phrase_in_text` ×2 | `\xad` → `\xAD` in a regex — same character, same pattern. |
| `reader_formatter.get_formatted_payment_info` | `datetime.now(UTC)` → `datetime.now(None)`; only the `.year` is used. |
| `reader_formatter.escape_editorial_brackets` (`last = None`) | `text[None:n]` slices identically to `text[0:n]`. |
| `reader_formatter.get_fitted_title_with_page_nums` ×5 | The `len_combined` bookkeeping after an `"A "`/`"The "` trim is unobservable: that branch only runs when the trim alone makes it fit, so every later `>` test is False regardless of the value. The second `>` → `>=` is likewise unreachable, since at equality `max_title_len == len(title_str)` and `textwrap.shorten` is a no-op. |

### Dead code, not a test gap: `BreakRefinement`'s cycle backstop (6)

`observe__mutmut_27..31` and `_33` all mutate the `if (hyphens, disabled) in
self._seen:` branch (or the `_seen.add` that only matters if that branch fires). **The
branch is unreachable.** Closing a cycle requires some gap to flip membership twice,
but the second flip takes its toggle count to `TOGGLE_LIMIT` and disables the gap,
which changes `disabled` — so the state pair can never actually repeat. The toggle
limit always fires first.

Verified by exhaustive search: for one-, two- and three-gap texts, every possible
adversarial ref-box oracle was explored to `MAX_ITERS` depth (the adversary may report
*any* subset of still-enabled gaps as breaking, which is strictly more freedom than a
real text renderer has) and the branch never executed. The block is kept as
belt-and-braces and commented as such in the source; **don't try to kill these six.**

### Killed in round 2 (2026-07-26)

`get_title_info` (24) and the toggle-counting half of `observe` (5), plus
`fallback_broken_words`, `get_issue_info`, `get_formatted_submitted_str` and
`get_title_extra_info` (1 each). Two patterns did nearly all the work, and both
generalise to the modules still on the backlog:

1. **Compare the whole output, not a fragment.** `get_title_info` is built entirely
   from mocked collaborators, so `assert "Payslip:" in res` could not see line order,
   labels, spacing, or the `+=` that appends the footnote marker rather than replacing
   the issue info. One full-string comparison killed most of the cluster.
2. **Assert what the collaborator was *called with*.** When a function's output is a
   mock's return value, the only way to pin which arguments it received is
   `assert_called_once_with` — every `f(None)` mutant survives otherwise. Relatedly,
   patch a **real dict** rather than a `MagicMock` when the code does a lookup: a
   mock's `__contains__`/`__getitem__` answer identically for any key, so they cannot
   distinguish "looked up the title" from "looked up anything".

**Latent rough edge found on the way:** `get_fitted_title_with_page_nums` raises
`ValueError` from `textwrap.shorten` when only 1-2 characters are left for the title
(the placeholder `"..."` doesn't fit). Not reachable from real window geometry, and now
pinned by a test, but it is a genuine unguarded edge if a caller ever shrinks that far.

## Notes

- `436` mutants had **no covering test** at all (🫥) — these live in code paths the
  Kivy-free unit tests never reach (often only exercised via UI-touching tests).
- The top clusters — `comic_book_loader`, `navigation.tree_spec`, `view_pipeline`,
  `system_file_paths`, `comic_book_loader_platform_settings`, `image_selector` — are
  the highest-leverage places to harden assertions.
- Already addressed: the `None`-category branch in `navigation_model.view_state_for`
  (one real gap this run surfaced) now has an assertion; that survivor is killed.
