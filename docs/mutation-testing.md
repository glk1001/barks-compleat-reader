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

## Three traps that produce fake numbers

The first two follow from mutmut calling `pytest.main()` **many times in one process**;
the third from how it decides which mutant is live.

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

3. **`patch.dict(os.environ, ..., clear=True)` disarms mutmut entirely.** mutmut
   picks the live mutant by reading `os.environ["MUTANT_UNDER_TEST"]` in a trampoline
   on **every call** to a mutated function. Clearing the environment removes that
   variable, so the trampoline falls back to the *original* body and every mutant in
   the function is a **false survivor**. That is the whole of `platform_info`'s 45:
   with the clear removed it went to 3. Worse, the same clear defeats mutmut's
   pre-flight "force the tests to fail" check, so a run scoped to only that module
   dies with `FAILED: Unable to force test failures` and produces no results at all.
   Isolate by copying the real environment minus the keys under test (see
   `platform_env` in `test_platform_info.py`), never by clearing it.

When triaging, prefer `uv run mutmut results` over the wrapper's summary if you need
raw mutant names; the summary collapses them to module counts.

**mutmut only mutates function bodies.** Module-level constants, class attributes and
enum members are copied through untouched — `PLATFORM = _get_platform()`,
`IS_MACOS = ...` and all seven `Platform` values generate zero mutants. A module whose
risk lives in a literal table therefore scores well without that table being tested at
all; a mutation score is evidence about the *code paths*, not the data.

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

## Big-cluster pass (2026-07-26)

The five heaviest remaining clusters after the pure-logic pass, swept together:
**1851 mutants, 598 → 117 survivors (1232 → 1721 killed, 93.6% of checked mutants).**

| Module (`barks_reader.core.*`) | Before | After |
|---|---:|---:|
| `navigation.tree_spec` | 184 | **1** |
| `system_file_paths` | 131 | 41 |
| `comic_book_loader_platform_settings` | 110 | 26 |
| `image_selector` | 104 | 35 |
| `fantagraphics_volumes` | 69 | 14 |
| **total** | **598** | **117** |

Of the 117 left: **40** are the `system_file_paths.__init__` equivalents below, **23** are
log wording, and the rest are the equivalents listed in the triage table. These modules are
at their practical floor.

### What worked (and generalises to the modules still on the backlog)

1. **Snapshot the whole built structure, not one field at a time.** `tree_spec` was 184
   survivors of exactly one shape: a `NodeSpec` field or a helper argument that no test
   ever read. Rendering each subtree to one line per node — kind, text, destination,
   press action, registration, `start_closed`, laziness — and comparing against a literal
   killed 112 of them in five tests. The renderer prints enums by **name**, never `repr`,
   so `auto()` renumbering doesn't churn the snapshot. Where a subtree is too big to
   snapshot (Categories: ~350 nodes), the same effect comes from asserting the *relation*
   instead: every node's text must equal what its own destination implies.
2. **A table of literals deserves a table of assertions.** `system_file_paths` is ~50
   hand-typed path fragments; its tests only asserted `isinstance(path, Path)`. One
   parametrised getter → exact-relative-path table killed all 88 path mutants, and
   building a real asset tree *from that same table* pinned the required-files check to
   it. A `test_every_getter_is_covered` set-comparison keeps the table honest.
3. **Script the clock to make a benchmark deterministic.** `autotune_worker_count` had 71
   survivors because the only test stubbed the whole benchmark and asserted
   `result in {1,2,3,4}`. Feeding `perf_counter` a fixed sequence makes the chosen worker
   count exactly predictable, so the `min`, the 8% smoothing band and its tie-break
   direction all become assertable. Two details did the work: a **non-zero start time**
   (otherwise `end - t0` and `end + t0` agree) and one candidate sitting **exactly** on
   `best * 1.08` (otherwise `<` and `<=` agree). Recording `ThreadPoolExecutor`'s
   `max_workers` pinned the candidate list and the CPU cap for free.
4. **Assert call arguments whenever the return value is a mock.** Same lesson as round 2,
   and it accounts for most of the `image_selector` and `fantagraphics_volumes` kills:
   `_get_fallback_image_info`, `get_search_image_for_title` and friends are just a few
   positional arguments threaded into a frozen dataclass, so they need the whole
   `ImageInfo` compared plus `assert_called_once_with` on the resolver.
5. **Test boundaries *on* the boundary.** Nearly every comparison survivor died to a case
   sitting exactly on the threshold: aspect ratio exactly `0.95`/`1.60`, memory exactly at
   the watermark, `cpu_count` exactly 2/4, RAM exactly 4/8 GiB, override count exactly
   `NUM_VOLUMES`, page number exactly 0, volume number exactly `LAST_VOLUME_NUMBER`.

### Real gaps this found (not just weak assertions)

- `tree_spec`'s `include_one_pagers_in_chrono=True` path had **no test at all** — only the
  default was ever exercised.
- `_check_image_names` accepts a zero-based first page, but nothing covered it, so the
  `first < 0` guard was free to become `first <= 0` and reject valid archives.
- Year-range groups' lazy title rows were never invoked for CS/US, so the `partial` could
  have closed over the wrong list unnoticed.

## Plumbing pass (2026-07-26) — partially done

The remaining backlog clusters, swept together: **1700 mutants, 535 → 332 survivors**
(1042 → 1245 killed, 78.9% of checked mutants). The 123 🫥 no-covering-test mutants in
these modules were left alone, as before.

| Module (`barks_reader.core.*`) | Before | After | State |
|---|---:|---:|---|
| `reader_settings` | 41 | **6** | done |
| `archive_page_image_source` | 59 | **11** | done |
| `screen_metrics` | 27 | **8** | done |
| `comic_reader_manager` | 22 | **9** | done |
| `reading_history` | 17 | **10** | done |
| `reader_file_paths` | 37 | **21** | done |
| `comic_book_loader` | 184 | 155 | **partial** |
| `view_pipeline` | 148 | 112 | **partial** |
| **total** | **535** | **332** | |

**The six "done" modules went 203 → 65**, and that 65 is the usual floor: `__init__`
`None` → `""` equivalents, log wording, and the `encoding`/`mode`-default equivalences
already recorded from earlier rounds.

**`comic_book_loader` and `view_pipeline` are not finished.** Together they hold 267 of
the 332, of which only ~77 are log/message wording — the rest are real, killable gaps.
This is what the backlog predicted for IO/threading plumbing, and the reason is
structural rather than a lack of effort:

- `comic_book_loader`'s two biggest clusters (`_load_pages` 31, `_load_comic_in_thread`
  28, non-log) are a prefetch loop and its error handling running on a worker thread.
  Killing those mutants means driving the executor deterministically — scripting the
  `ThreadPoolExecutor`, the stop flag, and the future-completion order — which is a
  test-harness build, not an assertion tweak.
- `view_pipeline`'s remainder is spread thin across ~20 small image-selection methods
  (`_set_next_top_view_image` 16 is the largest), each needing its own per-view-state
  case. There is no single lever like the `__init__` snapshot that took 148 → 112.

What *did* work here was the same four patterns as the previous round, plus one new one:

**Assert the whole constructed initial state.** `ViewPipeline.__init__` had 38 survivors —
every colour, opacity and context field set once and never asserted. One
`_compute_snapshot()` comparison against a literal `ViewSnapshot` on a freshly built
pipeline killed 36 of them. Same shape as the round-3 tree snapshot: a wrong initial
value is a one-frame flash of the wrong background at startup, which no per-state render
test can see.

`ArchivePageImageSource` (59 → 11) was the clearest win: 35 of its survivors were in
`_read_image`, whose entire job is choosing *which* loader to call and with what flags
(`encrypted_zip`, `use_ext_hint`, the extension hint for placeholder pages). Patching
`load_pil`/`decode_pil` and asserting the call arguments killed the cluster outright —
the round-3 "assert what the collaborator was called with" pattern, again.

### Real gaps this found

- `ReaderSettings._is_valid_wiki_bundle_dir` matches the bundle's root `index.md`
  case-sensitively, but nothing covered the name at all — the gate was free to accept
  `INDEX.MD` and then silently never show the wiki node.
- `read_setting_from_config` dispatches per field kind to `getboolean`/`getint`/`get`;
  no test checked that the section and key actually reached the accessor.
- `ReaderFilePaths.get_comic_cover_file` hardcodes `.jpg` for the plain cover but uses the
  *configured* extension for the edited one. That asymmetry was undocumented and untested;
  it is now pinned. **It is correct, not a bug** — checked against the real panel set,
  where `Covers/` holds 82 `.jpg` and 0 `.png`, while `Covers/edited/` holds 14 `.png` and
  0 `.jpg`. That is what `MOSTLY_PNG` means: the scanned covers stay JPEG, only
  hand-edited replacements are PNG.
- `_page_needs_real_archive` — the gate deciding whether a comic is still readable with
  its volume archive missing — had no direct test.

## Never-swept pass (2026-07-26) — `platform_info` + `wiki_integration`

The two largest modules no earlier round had touched: **286 mutants, 89 → 13
survivors**, and every one of the 13 is triaged as equivalent (listed below). Both
modules are **done**.

| Module (`barks_reader.core.*`) | Before | After |
|---|---:|---:|
| `platform_info` | 45 | **3** |
| `wiki_integration` | 44 | **10** |
| **total** | **89** | **13** |

`platform_info`'s 45 were **all fake** — trap 3 above, `patch.dict(os.environ, ...,
clear=True)` stripping mutmut's own `MUTANT_UNDER_TEST`. The existing tests already
covered every branch; they simply could not be seen. Fixing the isolation dropped it to
3 without any new branch coverage, and the module then aborted no more runs. **Any
survivor count for a module whose tests touch `os.environ` is suspect until the clear is
ruled out.** The new cases added on top (exact matching of `"ios"`/`"android"`/`"win32"`/
`"darwin"` rather than prefixes, environment-beats-`sys.platform` precedence) are worth
having but killed nothing extra.

`wiki_integration`'s 44 were real, and three patterns took 34 of them:

1. **Same-shaped adjacent fields need one assertion each.** `wiki_top_bar_spec` passes
   five `Path | None` icon slots straight through to `TopBarSpec`; 17 of the module's
   survivors were in that one call. Asserting each field `is` the matching
   `sys_paths.get_*` mock's `return_value` kills the whole cluster and is exactly the
   transposition guard the shape calls for.
2. **`assert_called_once_with`, again.** `background_for`'s panel is just the selector
   mock's return value, so the arguments — the *canonical string* title (not the enum)
   and `ALL_TYPES` — were unobservable until asserted directly. Same for the whole-
   collection branch and `self._all_titles`.
3. **Construct the object the other way too.** `BarksPanelsImageProvider.__init__`'s
   default-selector branch (`image_selector or ImageSelector(...)`) was never taken by a
   test: every case passed a selector. Patching `ImageSelector`/`ReaderFilePathsResolver`
   and asserting the construction arguments killed 6.

Also worth keeping in mind for future rounds: **a mutant can survive because the test
data cannot distinguish it.** `story_slug`'s curly-apostrophe mutants lived through a
`"Ten Cents’ Worth"` test because the following space collapses the hyphen either way —
only a word-internal apostrophe (`"Don’t"`) tells "dropped" from "hyphenated" apart.
When a mutant looks obviously covered, check whether the *example* can see it.

### Real gap this found

- `story_page_title`'s `title_enum is None or title_enum not in ALL_FANTA_COMIC_BOOK_INFO`
  had no case for the second half: 192 of the `Titles` members have no Fantagraphics
  entry, and nothing stopped the `or` becoming `and`, which would hand the wiki a title
  with no comic to open and no panels to draw backgrounds from.

## Small-module tail pass (2026-07-26) — the last 17 backlog modules

Everything below `reading_history` in the backlog table, swept together: **1129 mutants,
99 → 28 survivors** (935 killed, **97.1%** of checked mutants). This finishes the backlog
table — no module on it is unswept now.

| Module (`barks_reader.core.*`) | Before | After |
|---|---:|---:|
| `user_error_messages` | 12 | **0** |
| `comic_book_page_info` | 12 | 2 |
| `reader_file_paths_resolver` | 10 | **0** |
| `image_pipeline` | 10 | **0** |
| `last_read_page_tracker` | 9 | 6 |
| `special_overrides_handler` | 8 | **0** |
| `json_settings_manager` | 8 | 7 |
| `reader_tree_view_utils` | 5 | 5 |
| `panel_image_loader` | 5 | 1 |
| `testing.fakes` | 4 | 2 |
| `page_info_adapters` | 4 | 2 |
| `minimal_config_info` | 4 | 3 |
| `reader_palette` | 2 | **0** |
| `config_info` | 2 | **0** |
| `comic_book_info` | 2 | **0** |
| `settings_notifier` | 1 | **0** |
| `navigation.navigation_model` | 1 | **0** |
| **total** | **99** | **28** |

**Nine modules went to zero, and all 28 remaining are triaged** (table below): 11 log
wording, 5 `encoding=` codec equivalents, 5 unobservable `__init__` defaults, 4 inert
`typing.cast` type strings, 2 falsy `strict=` equivalents, and 1 that is genuinely
killable but deliberately deferred. This is the resting state for these modules.

`reader_palette` had **no test file at all** — `color_to_markup_hex` was only exercised by
`test_wiki_integration`, which computed its expectation by calling the same function, so
the assertion was a tautology. A direct scale-to-byte table plus the theme-selection
fallback took it to 0.

### What worked

1. **`pytest.raises(match=...)` is a *search*, so `XX…XX` mutants walk straight through
   it.** Three separate error-message mutants survived tests that looked like they
   covered them exactly — `match="RequiredDimensionsPort was not wired"` happily matches
   `"XXRequiredDimensionsPort was not wiredXX"`. Anchoring with `^…$` kills them for free.
   The same trap applies to `assert "..." in text`: `_build_volume_not_available`'s
   `"Cannot show this title."` survived an `in` check for exactly that string. **Worth
   sweeping other test files for.**
2. **A collaborator's return value can hide a flag that never reached it.** Every
   `special_overrides_handler` survivor of the form `_get_special_inset_file(std, None)`
   lived because the fixture never created the `-no-overrides` variant on disk — with the
   file absent, both branches fall back to the same path. Creating the *other* file is
   what makes the forwarded flag observable. Same shape as the round-4 "check whether the
   example can see it" note.
3. **Keyword defaults need a call that passes no keywords.** `image_pipeline.load_pil`'s
   `encrypted_zip=False` / `use_ext_hint=False` and `encode_png_stream`'s
   `compress_level=0` all survived because every existing test passed them explicitly. One
   call with no keywords, patching the collaborator, kills the lot.
4. **Assert the whole `PageInfo`, not a field.** `_build_page_map`'s four
   positional-argument mutants died to one whole-dataclass comparison — and only because
   the srce and dest pages in the fixture differ in *both* filename and type. Identical
   stand-ins cannot catch a transposition.
5. **A monotonic counter's step size is observable even when its values are not.**
   `PanelImageLoader._generation += 1` mutating to `-= 1` is not cosmetic: `cancel()` still
   adds 1, so load→cancel→load lands back on a generation a worker already captured and
   that stale worker delivers its superseded image. Asserting the step is exactly +1 (as
   the existing `cancel` test already does) covers it.

### Real gaps this found

- **`user_error_messages` dialogs were mis-indented for long directory paths.**
  `_build_fanta_root_not_found` and `_build_duplicate_archive_files` interpolated a
  `textwrap.fill`-wrapped path into a `dedent(f"""…""")`. The wrapped continuation line has
  no indentation of its own, which drops the common prefix `dedent` computes to `""` — so
  **`dedent` silently did nothing** and every line of the dialog rendered with its source
  indentation in the Kivy label. It only bites above 50 columns, which is why no test saw
  it. Both now dedent the template *before* substituting.
- `SettingsNotifier._on_change` was a **dead field** — assigned in `__init__` and never
  read anywhere in the app. Deleted.
- `ComicLayout.resolve_last_read`'s three-way `and` had no case where all three conjuncts
  mattered: every double-page test sat on an edge page, where left and right resolve to the
  same saved position, so both the display unit and the mode could have been dropped
  unnoticed. Mid-body with a full pair is the only shape that sees it.
- `comic_book_page_info` had no test for a **front-matter-only** comic (`last_body_page`
  keeping its initial `""`), and `_format_volume_list` none for an empty list or a run of
  exactly three — the boundary that distinguishes `>=` from `>`.

### Known-equivalent survivors from the small-module tail pass (2026-07-26)

| Mutant | Count | Why it is not worth killing |
|---|---:|---|
| Log wording and `logger.x(None)` across seven modules | 11 | Same as every previous round. |
| `read_text`/`write_text` `encoding="utf-8"` → `"UTF-8"` / `None` / dropped | 5 | Codec alias, or the platform default which is UTF-8 everywhere the app runs. Already recorded twice. |
| `__init__` `None` → `""` (`page_info_adapters` ×2, `last_read_page_tracker` ×2) and `False` → `None` ×1 | 5 | All five are read only through a falsy test or an identity comparison against a real object, and every one is overwritten before any code path can distinguish them. `_cached is None` is unreachable on its own: `_cached_for` and `_cached` are assigned together, so the first disjunct always decides. |
| `cast("list[TitleTreeViewNodeProtocol]", …)` → `None` / case-changed / `XX…XX` | 4 | `typing.cast` returns its second argument untouched; the type string is inert at runtime. No test can observe it — it is not even read. |
| `zip(..., strict=False)` → `strict=None` / dropped | 2 | Both are falsy, and `False` is `zip`'s own default. Only `strict=True` differs, and that mutant dies. |
| `FakeScheduler.schedule_once`'s `timeout_secs: float = 0` → `1` | 1 | The parameter is unused (`# noqa: ARG002`) — the fake runs the callback inline. |

### Killable but deferred: `FakeScheduler.advance`'s `//` (1)

`advance__mutmut_6` turns `int(secs // interval.period_secs)` into `int(secs / …)`. **This
is not an equivalent mutant** — the two disagree for fractional periods, where binary
floating point bites: `1.0 // 0.1` is `9.0`, so `advance(1.0)` on a `0.1`s interval fires
**nine** times, one short of the `floor(secs / period)` its own docstring promises.

Nothing is broken today: every caller uses an integral period, where the two agree. Killing
it means deciding the fake's rounding contract rather than adding an assertion, so it is
left alone deliberately — **not** because it cannot be killed. Worth revisiting if a test
ever needs a sub-second interval.

## Survivors by module (backlog, most-survivors first)

"Before" counts are from the 2026-07-25 full run and are inflated wherever a module
memoises (see trap 2). **Every module on this list has now been swept**, so the arrows are
the whole story; the two `comic_book_loader` / `view_pipeline` entries are the only ones
still carrying real, killable gaps (see the plumbing pass above). Everything else is at its
triaged floor.

| Module (`barks_reader.core.*`) | Survivors |
|---|---:|
| `comic_book_loader` | 185 → 155 |
| `navigation.tree_spec` | 184 → 1 |
| `view_pipeline` | 148 → 112 |
| `system_file_paths` | 131 → 41 |
| `comic_book_loader_platform_settings` | 110 → 26 |
| `image_selector` | 104 → 35 |
| `fantagraphics_volumes` | 69 → 14 |
| `archive_page_image_source` | 59 → 11 |
| `reader_formatter` | 56 → 9 |
| `collection_page_groups` | 53 → 0 |
| `reader_utils` | 50 → 4 |
| `platform_info` | 45 → 3 |
| `wiki_integration` | 44 → 10 |
| `reader_settings` | 41 → 6 |
| `reader_file_paths` | 37 → 21 |
| `screen_metrics` | 27 → 8 |
| `filtered_title_lists` | 22 → 1 |
| `comic_reader_manager` | 22 → 9 |
| `hyphen_break_engine` | 19 → 6 |
| `reading_history` | 17 → 10 |
| `user_error_messages` | 12 → 0 |
| `comic_book_page_info` | 12 → 2 |
| `reader_file_paths_resolver` | 10 → 0 |
| `image_pipeline` | 10 → 0 |
| `last_read_page_tracker` | 9 → 6 |
| `special_overrides_handler` | 8 → 0 |
| `json_settings_manager` | 8 → 7 |
| `reader_tree_view_utils` | 5 → 5 |
| `panel_image_loader` | 5 → 1 |
| `testing.fakes` | 4 → 2 |
| `page_info_adapters` | 4 → 2 |
| `minimal_config_info` | 4 → 3 |
| `reader_palette` | 2 → 0 |
| `navigation.navigation_model` | 2 → 0 |
| `config_info` | 2 → 0 |
| `comic_book_info` | 2 → 0 |
| `settings_notifier` | 1 → 0 |

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

### Known-equivalent survivors from the big-cluster pass (2026-07-26)

The 117 left after that pass, all triaged. Nothing here is a missing assertion.

| Mutant | Count | Why it is not worth killing |
|---|---:|---|
| `system_file_paths.__init__` (`None` → `""`) | 40 | Every field is overwritten by `set_barks_reader_files_dir` before any getter runs, and each getter guards with a bare `assert`, which `""` fails exactly as `None` does. No test can tell them apart. |
| Log wording and `logger.x(None)` across all five modules | 23 | Pinning log strings buys nothing and breaks on every reword. Includes all 11 in `_get_system_profile`, whose entire body below the cache check is one `logger.debug`. |
| `dict.get(k, )` / `.get(k, None)` where `""` was the default | 8 | The value compared against is always a `PanelPath`/`Path`, so it can never equal `""`, `None` **or** mutmut's `"XX"` sentinel. The default is unobservable. |
| `zipfile.ZipFile(p, "r")` → `ZipFile(p)` | 3 | `"r"` **is** the default. Same equivalence already recorded for `reader_utils.get_paths_from_zip`. |
| `os.cpu_count() or 1` → `or 2` | 2 | Only reachable when `cpu_count()` returns `None`; both 1 and 2 satisfy the `<= 2` branch that immediately follows, which returns 1 either way. |
| `get_new_dynamic_window`'s `if new_window != dynamic_window` guard | 4 | Guards a `logger.debug` only; the returned window is computed before it. |
| `line.split("#", 1)` → `split("#")` / `split("#", 2)` | 2 | Only `[0]` is used, and the text before the *first* `#` is identical at any `maxsplit >= 1` (or none). |
| `read_text(encoding="utf-8")` → `"UTF-8"` / `None` | 2 | `"UTF-8"` is the same codec by alias; `None` picks the platform default, which is UTF-8 everywhere the app runs. |
| `PrefetchTuning.__init__`'s `self._worker_count = None` | 1 | `_worker_count` is stored and never read — `base_max_window` uses the local parameter. Dead field. |
| `ImageSelector.__init__`'s `self._never_crop_images = None` | 1 | `_is_never_crop` short-circuits on any falsy value, so `None` and `frozenset()` behave identically. |
| `get_random_image_for_title`'s empty-filename assert | 2 | A tripwire that cannot fire: the mutations leave it passing (`str(None)` is `"None"`, not `""`). |
| `_tag_or_group_specs`'s `assert_never(None)` | 1 | Defensive branch for malformed tag data; unreachable while `BARKS_TAG_CATEGORIES` holds only `Tags`/`TagGroups`. |
| `get_all_volume_override_archives`'s `continue` → `break` | 1 | Needs an unparseable filename to be iterated *before* a valid one, but `Path.iterdir()` order is filesystem-defined — a test that relies on it would be flaky, not durable. |
| Remainder (`load`'s page-count log arithmetic, error-message-only `archive_root=None`, misc) | 27 | Message/log-only text, or arguments whose only effect is on a string nobody asserts. |

### Known-equivalent survivors from the never-swept pass (2026-07-26)

The 13 left in `platform_info` and `wiki_integration`, all triaged.

| Mutant | Count | Why it is not worth killing |
|---|---:|---|
| `_get_platform`'s `os.environ.get("KIVY_BUILD", "")` default | 3 | The value is only ever compared against `"ios"` and `"android"`, so `""`, `None`, a missing default and mutmut's `"XXXX"` are all the same non-match. |
| `wiki_top_bar_spec`'s `bg_color`/`separator_color`/`icon_width`/`quit_fence_width` kwargs removed | 4 | `TopBarSpec`'s own defaults **are** those four Barks constants, value for value (checked: `(0.12,0.12,0.12,1)`, `(0.3,0.3,0.3,1)`, `70`, `17`) — okf\_reader's bar was written to mirror the kv idiom. Passing them explicitly is the anti-drift guard: it keeps the app's look pinned to *our* constants if either side ever changes. Not removable, not killable. (`height` differs — 45 vs 40 — and that mutant does die.) |
| `.lstrip("#")` → `.lstrip("XX#XX")` ×3 | 3 | The strip set becomes `{X, #}`; `color_to_markup_hex` emits lowercase hex, so `X` can never match. Same for `story_slug`'s `.strip("-")` → `.strip("XX-XX")`. |
| `encode("utf-8")` → `"UTF-8"` | 1 | Codec alias. Already recorded from the big-cluster pass. |
| `canonical_title`'s first `STR_TITLE_TO_ENUM.get(text)` → `None` / `.get(None)` | 2 | The quote-stripping fallback repeats the lookup, and **no canonical title contains a double quote** (checked against `STR_TITLE_TO_ENUM`), so for every real input the fallback returns exactly what the first lookup would have. Skipping it costs a dict lookup and changes nothing observable. |

### Dead code, not a test gap: the override extension check (2)

`_get_override_and_extra_images_page_maps` does `assert ext in [JPG_FILE_EXT, PNG_FILE_EXT]`
and *then* `if ext not in _VALID_IMAGE_EXTENSION: raise PageExtError(...)`. Since
`_VALID_IMAGE_EXTENSION` is `[PNG_FILE_EXT, JPG_FILE_EXT]` — the same two members — the
assert already guarantees the `if` is False. The `msg = ...` and `raise` inside it are
unreachable; **don't try to kill these two.**

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
- With the backlog table swept, the only remaining killable clusters are
  `comic_book_loader` (155) and `view_pipeline` (112). Both need a test-harness build
  rather than assertion tweaks — see the plumbing pass for why.
- Already addressed: the `None`-category branch in `navigation_model.view_state_for`
  (one real gap this run surfaced) now has an assertion; that survivor is killed.
