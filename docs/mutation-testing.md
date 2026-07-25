# Mutation testing (mutmut) — status & backlog

Mutation testing flips small pieces of source (`>` → `>=`, `and` → `or`, a
constant to a sentinel, …) and checks whether any test fails. A **survivor** is a
mutation no test caught — a line that is executed but not actually *asserted*.
Line coverage can't see these; that's the whole point of running mutmut.

## How to run

```bash
bash scripts/mutmut.sh                            # mutate all of core/
bash scripts/mutmut.sh '*/core/navigation/*'      # scope to a subpackage
bash scripts/mutmut.sh '*/core/reader_utils.py'   # one module
```

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

## Survivors by module (backlog, most-survivors first)

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
| `reader_formatter` | 56 |
| `collection_page_groups` | 53 |
| `reader_utils` | 50 |
| `platform_info` | 45 |
| `wiki_integration` | 44 |
| `reader_settings` | 41 |
| `reader_file_paths` | 37 |
| `screen_metrics` | 27 |
| `filtered_title_lists` | 22 |
| `comic_reader_manager` | 22 |
| `hyphen_break_engine` | 19 |
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

## Notes

- `436` mutants had **no covering test** at all (🫥) — these live in code paths the
  Kivy-free unit tests never reach (often only exercised via UI-touching tests).
- The top clusters — `comic_book_loader`, `navigation.tree_spec`, `view_pipeline`,
  `system_file_paths`, `comic_book_loader_platform_settings`, `image_selector` — are
  the highest-leverage places to harden assertions.
- Already addressed: the `None`-category branch in `navigation_model.view_state_for`
  (one real gap this run surfaced) now has an assertion; that survivor is killed.
