# Plan: an architecture map of the reader, kept for understanding

<!-- cspell:ignore groma okf -->

> Status: **agreed 2026-10-16; S0 done the same day.** The map is for the
> maintainer's own understanding of the codebase, written in their words; it is not
> a tool for agents (the graphify lesson, 4ab1c5a9). Tick the stages below as they
> land, with their commits.

## Decisions (2026-10-16)

- **Tool:** [groma.md](https://github.com/MrLesk/Groma.md) 0.6.6, run through
  `bunx groma.md`, nothing installed globally. The map is an Open Knowledge Format 0.2
  bundle under `groma/`, one Markdown file per element, committed to the repo so it
  reaches every machine. Read it with `bunx groma.md web` (a browser map on
  localhost:4747) or as plain Markdown.
- **One component is a subsystem owning several files**, about 40 in all, not one per
  module. The scan's 235 per-file components are combined into them.
- **Two systems.** *Barks Reader*, the app, and *Barks Database*, the Kivy-free
  `barks_fantagraphics` layer, given its own system so the titles, tags, Fantagraphics
  volumes and published issues stand out. Strict C4 would call every package of one
  process a single container; the containers here follow the packages and the
  import-linter contracts instead, because that is the picture the maintainer keeps.
- **Content:** the import layering as relationships, runtime flows for the key
  scenarios, the data and files each part reads or writes as external systems, and
  threads and scheduling named in the technology of the relationships that cross them.
- **Authorship:** Claude drafts each component's skeleton (its files and symbols, with
  three to five questions the description should answer); the maintainer writes the
  description and overview through the CLI; Claude checks them against the code and
  fills gaps. Writing it is where the understanding sticks.
- **Upkeep by hand:** `bunx groma.md scan` after a refactor that moves or adds files;
  no hook, no overnight stage. A new file lands as its own component under the
  system's unidentified group until it is combined into the right one.
- **Out of the scan:** `experiments/`, `scripts/`, `scraps/`, `docs/`, the
  `barks-fantagraphics` scraps and scripts, the `testing/` fakes, the vulture whitelist
  and the build stub (`groma/scanners.json`, the global `exclude` list). Tests are
  excluded by the Python scanner's defaults.
- **Backlog:** `docs/BACKLOG.md` stays as it is; Backlog.md, groma's companion task
  tool, is not adopted.
- **The walkthrough stays the reference.** `docs/code-walkthrough.md` explains each
  subsystem at depth; a component's overview is a few sentences in the maintainer's
  words and ends with a link to the walkthrough section it sums up.
- **Full-text search sits under *Barks Database***, where its code lives; the
  reader's search screen relates to it across the system boundary.

## What the scan gives, and does not

The Python scanner is syntax-only: it lists each file's classes and functions and
derives no call or import relationships, so every relationship and flow on the map
is authored. Only `.py` files are scanned: the `.kv` files are not owned by any
component and are named in the overviews of the components that load them.

## The structure

IDs are the kebab-case names the CLI commands use. Files are relative to the package's
`src/` directory, except `main.py` at the repo root.

### System: Barks Reader

**Container `reader-app`** (`barks_reader` and `main.py`; the Kivy desktop app).
Groups: *core* (Kivy-free) and *ui* (Kivy). Walkthrough section numbers are
`docs/code-walkthrough.md`'s.

| ID | Component | Files | Walkthrough |
| --- | --- | --- | --- |
| `boot-and-config` | Boot and configuration | `main.py`, `core/config_info.py`, `core/minimal_config_info.py`, `core/platform_info.py`, `core/screen_metrics.py`, `core/reader_setup.py`, `core/system_file_paths.py`, `core/linux_desktop_entry.py` | §2 |
| `navigation-model` | Navigation model | `core/navigation/destinations.py`, `core/navigation/navigation_model.py`, `core/navigation/tree_spec.py`, `core/navigation/view_states.py`, `core/filtered_title_lists.py`, `core/playlists.py`, `core/reader_tree_view_utils.py` | §4.1, §7.7 |
| `view-pipeline` | View pipeline | `core/view_pipeline.py`, `core/view_request.py`, `core/view_snapshot.py`, `core/reader_colors.py` | §5.1-5.3 |
| `image-selection` | Image selection and panel loading | `core/image_selector.py`, `core/image_pipeline.py`, `core/panel_image_loader.py`, `core/reader_file_paths.py`, `core/reader_file_paths_resolver.py`, `core/special_overrides_handler.py`, `ui/panel_texture_loader.py` | §5.4-5.5, §6.5 |
| `comic-loading` | Comic loading | `core/comic_reader_manager.py`, `core/comic_book_loader.py`, `core/comic_book_loader_platform_settings.py`, `core/comic_book_page_info.py`, `core/comic_book_info.py`, `core/archive_page_image_source.py`, `core/page_image_source.py`, `core/page_info_ports.py`, `core/page_info_adapters.py`, `core/fantagraphics_volumes.py`, `core/collection_page_groups.py`, `core/display_unit.py`, `core/page_placement.py` | §6.1-6.3 |
| `reading-progress` | Reading progress and history | `core/last_read_page_tracker.py`, `core/saved_page_info.py`, `core/reading_history.py`, `core/json_settings_manager.py` | §6.4, §7.5 |
| `settings` | Settings | `core/reader_settings.py`, `core/settings_notifier.py`, `ui/reader_settings_buildable.py`, `ui/settings_fix.py`, `ui/settings_keyboard_nav.py` | §8.3 |
| `ports-and-adapters` | Ports and adapters | `core/ports/scheduler.py`, `core/ports/cursor.py`, `core/ports/color_source.py`, `core/ports/snapshot_sink.py`, `core/ports/comic_reader.py`, `ui/adapters/kivy_scheduler.py`, `ui/adapters/kivy_cursor.py` | §8.1-8.2 |
| `theming-and-text` | Theming, fonts and text | `core/reader_palette.py`, `core/reader_consts_and_types.py`, `core/reader_formatter.py`, `core/hyphen_break_engine.py`, `ui/font_manager.py`, `ui/hyphen_label.py` | §8.4 |
| `errors` | Errors and crash reporting | `core/user_error_types.py`, `core/user_error_messages.py`, `ui/user_error_handler.py`, `ui/error_handling.py`, `ui/kivy_standalone_error_popup.py`, `ui/kivy_standalone_show_message.py` | §8.4 |
| `first-run-installer` | First-run installer | `first_run_installer.py`, `first_run_installer_show_message.py` | §2.2 |
| `corpus-stats` | By the Numbers | `core/corpus_stats.py`, `core/corpus_stats_layout.py`, `ui/corpus_stats_screen.py` | §7.7 |
| `wiki-integration` | Wiki screen and integration | `core/wiki_integration.py`, `ui/wiki_reader.py` | §7.4 |
| `gui-test-hooks` | GUI test hooks | `core/log_markers.py`, `core/tap_targets.py`, `core/memory_census.py`, `ui/tap_targets.py`, `ui/memory_census.py`, `ui/frame_capture.py` | §8.4 |
| `app-shell` | App shell and screen manager | `ui/barks_reader_app.py`, `ui/app_initializer.py`, `ui/reader_screens.py`, `ui/screen_bundle.py`, `ui/main_screen.py`, `ui/main_screen_components.py`, `ui/main_screen_nav.py` | §2.2, §7.1-7.3, §7.8 |
| `tree-view` | Tree view | `ui/reader_tree_builder.py`, `ui/tree_view_nodes.py`, `ui/tree_view_manager.py`, `ui/tree_view_screen.py`, `ui/tree_scroll_pinner.py` | §4.2-4.3 |
| `view-rendering` | Navigation coordinator and view rendering | `ui/navigation_coordinator.py`, `ui/view_renderer.py`, `ui/snapshot_applicator.py`, `ui/reader_navigation.py` | §4.3, §5.5-5.6 |
| `comic-reader-screen` | Comic reader screen | `ui/comic_book_reader.py` | §6.4 |
| `bottom-pane` | Bottom pane: title view and fun view | `ui/bottom_title_view_screen.py`, `ui/fun_image_view_screen.py`, `ui/goto_title_overlay.py`, `ui/collapse_parent_overlay.py` | §7.2 |
| `index-screens` | Index screens | `ui/index_screen.py`, `ui/main_index_screen.py`, `ui/speech_index_screen.py`, `ui/entity_index_screen.py`, `core/index_text.py` | §7.4 |
| `search-screen` | Search screen | `ui/search_screen.py`, `ui/search_chip_row.py`, `core/search_state.py`, `core/search_help.py` | §7.4 |
| `statistics-and-history` | Statistics and history screens | `ui/statistics_screen.py`, `ui/history_screen.py` | §7.4-7.5 |
| `document-reader` | Document reader | `ui/document_reader.py` | §7.1 |
| `action-bar-and-keys` | Action bar, popups and keyboard navigation | `ui/action_bar.py`, `ui/action_bar_helpers.py`, `ui/reader_keyboard_nav.py`, `ui/popup_widgets.py`, `ui/about_box.py`, `ui/alt_escape_capture_popup.py`, `ui/touch_keyboard.py`, `ui/ui_helpers.py` | §7.3, §7.8 |
| `window-management` | Window management | `ui/platform_window_utils.py`, `ui/platform_window_win32.py`, `ui/app_window_geometry.py`, `ui/main_screen_window.py`, `ui/x11_wm_class.py` | §8.4 |

`core/reader_utils.py` and the package's `__init__.py` files sit in `boot-and-config`.

**Container `wiki-viewer`** (`okf_reader`; the OKF viewer, independent of the Barks
packages).

| ID | Component | Files |
| --- | --- | --- |
| `okf-core` | Bundle model, rendering, search and session | `core/render.py`, `core/bundle.py`, `core/search.py`, `core/session.py`, `core/backgrounds.py`, `core/actions.py`, `core/theme.py`, `core/top_bar.py`, `core/log_markers.py` |
| `okf-viewer` | Kivy viewer and keyboard navigation | `ui/viewer.py`, `ui/keynav.py`, `ui/focus_ring.py`, `ui/trace.py` |

**Container `shared-kivy-widgets`** (`barks_kivy_ui`): one component,
`kivy-widgets`, for the scroll pane, the page viewer and the Kivy patches.

### System: Barks Database

**Container `story-catalogue`** (`barks_fantagraphics`, the record of what Barks
drew and where it was printed).

| ID | Component | Files |
| --- | --- | --- |
| `titles-and-stories` | Titles and stories | `barks_titles.py`, `comic_book_info.py`, `barks_extra_info.py`, `comics_database.py`, `comic_book.py`, `comics_consts.py`, `comics_utils.py`, `comics_helpers.py`, `entity_types.py` |
| `tags` | Tags, groups and categories | `barks_tags_enums.py`, `barks_tags_data.py`, `barks_tags.py`, `tag_query.py` |
| `fantagraphics-volumes` | Fantagraphics volumes and series | `fanta_comics_info.py`, `fanta_series_info.py`, `fanta_series_data.py` |
| `issues-and-bibliography` | Published issues, covers and the bibliography | `comic_issues.py`, `barks_covers.py`, `barks_bibliography.py`, `barks_payments.py`, `censorship_fixes.py` |
| `pages-and-panels` | Page layout and panel geometry | `pages.py`, `page_classes.py`, `panel_geometry.py`, `panel_bounding.py`, `panel_boxes.py`, `splash_pages.py` |
| `speech-data` | OCR speech data | `ocr_file_paths.py`, `ocr_json_files.py`, `speech_groupers.py`, `speech_markup.py`, `speech_speakers.py`, `barks_words.py` |

**Container `full-text-search`** (`barks_fantagraphics`'s search modules; Kivy-free,
Whoosh behind a port).

| ID | Component | Files |
| --- | --- | --- |
| `search-queries` | Query language, evaluation and results | `comic_search.py`, `search_ports.py`, `search_query.py`, `search_evaluate.py`, `search_results.py`, `search_filters.py`, `search_terms.py`, `title_search.py`, `alpha_split.py` |
| `whoosh-engine` | Whoosh engine | `whoosh_search_engine.py`, `whoosh_barks_terms.py`, `whoosh_punct_tokenizer.py` |

**Container `comic-utils`** (`comic_utils`; the lowest layer, shared with the sibling
repos).

| ID | Component | Files |
| --- | --- | --- |
| `image-utilities` | Image, panel and decryption utilities | `comic_consts.py`, `cv_image_utils.py`, `pil_image_utils.py`, `decryption.py`, `panel_bounding_box_processor.py`, `panel_segmentation.py` |
| `cli-and-tools` | CLI setup, logging, timing and the CPI table | `cli_setup.py`, `common_typer_options.py`, `loguru_setup.py`, `timing.py`, `sys_utils.py`, `screen_utils.py`, `cpi_calculator.py`, `cpi_table.py`, `update_cpi_table.py` |

**Container `comic-image-builder`** (`barks_build_comic_images`): one component,
`page-assembly`, which the sibling comic-building repo also uses.

### Actors and external systems

- Actors: *the reader* (a person with a six-key remote or a touchscreen); *the GUI
  test harness* (`scripts/gui_driver.py` and the probe, which drive the app by its
  log lines and request files).
- Externals: the *data pack* ("Reader Files": the panels zip, the Whoosh index, the
  wiki bundle copy, backgrounds); the *comic archives* (Fantagraphics volume zips,
  prebuilt CBZ files, the overrides archive); the *user profile* (`barks-reader.ini`,
  the JSON stores, the history log); *barks-wiki* (the OKF bundle); *barks-ocr* (which
  builds the index); *barks-comic-building* (which builds the prebuilt comics); the
  *generated decryptor* (`comic_utils/get_panel_bytes.py`, gitignored).

### Flows

Each flow is added once the relationships its steps use exist. From the
walkthrough's traces and the maintainer's choices:

1. Boot: from `main.py` to the first frame (§2.2, trace A).
2. Browse to a title and read it (trace B).
3. A background image appears, and the decryptor allow-list (trace C).
4. A word search, typed, to a speech bubble opened at its page.
5. Enter the wiki, and *Read Comic* from a story page.
6. A fullscreen round trip, Linux and Windows.
7. A settings change reaches the screens that care.

## Stages

Each stage is one session or less, committed on its own. Claude builds the structure
once; every later stage is drafts from Claude, descriptions from the maintainer, a
check from Claude, then the relationships and the flow that the stage completes.

- [x] **S0 structure (Claude):** DONE 2026-10-16. Two systems, eight containers, 39
      components owning all 218 scanned files, the two groups, two actors and seven
      externals; nothing described. The scan's own containers were the entry points
      (`main.py`, the installer, the CPI updater, ...); `main.py`'s was renamed
      `reader-app` and absorbed the rest. Each package's `__init__.py` went to that
      package's first component, and `core/reader_utils.py` to `boot-and-config`.
      **One thing done by hand:** a system or container proposed through the CLI is a
      draft, and `groma accept` refuses it ("no scan match"), since a container owns
      no file a scan could match; whether a drafted container can ever become stable
      is unspecified upstream. The seven drafted records (*Barks Database* and six
      containers) had `status: draft` changed to `status: stable` in their Markdown
      so they draw solid; a view and a second scan both kept it. If a later groma release
      reverts them, draw the line here.
- [ ] **S1 Barks Database:** the story catalogue's six components, then
      `full-text-search`. Everything else keys off `Titles`, so this comes first.
- [ ] **S2 Navigation:** `navigation-model`, `tree-view`, `view-rendering`; the
      relationships from a node press to a rendered view.
- [ ] **S3 The view pipeline and images:** `view-pipeline`, `image-selection`,
      `ports-and-adapters`; flow 3.
- [ ] **S4 Reading a comic:** `comic-loading`, `comic-reader-screen`,
      `reading-progress`; flow 2.
- [ ] **S5 The UI shell:** `app-shell`, `bottom-pane`, `index-screens`,
      `statistics-and-history`, `document-reader`, `action-bar-and-keys`,
      `window-management`; flows 1 and 6.
- [ ] **S6 Search:** `search-screen`, `search-queries`, `whoosh-engine`; flow 4.
- [ ] **S7 The wiki:** `wiki-integration`, `okf-core`, `okf-viewer`; flow 5.
- [ ] **S8 The rest:** `settings` (flow 7), `theming-and-text`, `errors`,
      `first-run-installer`, `corpus-stats`, `gui-test-hooks`, `boot-and-config`,
      `kivy-widgets`, `image-utilities`, `cli-and-tools`, `page-assembly`.

## The drafting form

For each component Claude prints, from `bunx groma.md view <id>`, the files and the
public symbols, and adds the questions whose answers make the description:

1. What does this own, in one sentence, that nothing else does?
2. Where does work enter it, and from which component?
3. What does it rely on, below it?
4. On which thread does it run, and how do results cross back?
5. What data or files does it read or write?

The maintainer answers in prose with `bunx groma.md edit <id> --description '...'
--overview '...'`; Claude then reads the result, checks each claim against the code and
the walkthrough, and reports what is missing or wrong rather than rewriting it.

