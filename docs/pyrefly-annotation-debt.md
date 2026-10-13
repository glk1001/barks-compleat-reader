# pyrefly annotation-debt checklist

The "union-type / nullability" findings pyrefly surfaced that are **grandfathered** in
`pyrefly-baseline.json` (see `pyrefly.toml`): 24 when this list was written (2026-07-20), 8
still open on 2026-10-13 (one of them now fires twice). None block anything — work through
them **opportunistically** when you're already in the file. After fixing one:

```bash
bash scripts/pyrefly.sh --update-baseline   # regenerates the baseline minus what you fixed
```

These are *real* type imprecision (unlike the 44 Kivy-boundary entries also baselined, and
7 Win32 `ctypes` ones that exist only because `pyrefly.toml` checks as Linux). Kivy ships
no stubs; generating them is the only fix for those. Fix notes below are a **starting point
derived from the type errors** — verify at the call site; some may reveal a real
`None`/wrong-variant bug, which is the point.

> Cross-repo caution: `reader_setup.py:37` involves the `ConfigParser` Protocol in
> `core/reader_settings.py`, which four scripts also work around. Change it carefully.

## How the baseline matches (read before trusting a green gate)

Checked 2026-10-13 against pyrefly 1.2.0: a baseline entry matches on **path, error kind and
column**. The line and the message are ignored, and one entry covers every error of that
kind at that column in that file. Two consequences:

- **Line drift never fails the gate**, so nothing forces `--update-baseline`, and a fixed
  finding's entry stays until someone runs it. Not run from 2026-07-20 to 2026-10-13, the
  file had grown 12 entries that matched nothing (9 from this list, `comics_utils.py`'s
  `stat`/`lstat` fixed by `66e6c657`, and a Kivy one in `ui/ui_helpers.py` whose code is
  gone). Regenerated on 2026-10-13: 84 entries, then 77 after the P1 and P2 fixes. Run it
  after any fix here.
- **A new finding can hide** behind an entry in the same file at the same column. Two did:
  `okf_reader/ui/viewer.py`'s `trigger_action`, which has had its own entry since the
  regeneration, and the second `populated` site in `ui/tree_view_manager.py`, which shares
  its kind, column and message with the first (both below).

Line numbers below are those of 2026-10-13; find an item by its names if they have moved.

---

## P1 — possible real `None` bugs (verify first: is `None` actually reachable?)

Each is a spot where a possibly-`None` value flows into a parameter/return declared non-`None`.
If `None` can occur at runtime → real bug, add a guard. If it genuinely can't → tighten the source
type or `assert x is not None`.

- [x] `ui/barks_reader_app.py` — `Unknown | None` passed as `parser` (ConfigParser) to
      `bootstrap_reader_environment` (`self.config`). Not reachable: Kivy's `load_config()`
      sets it before `build()`; asserted (2026-10-13).
- [x] `ui/navigation_coordinator.py` — `Titles | None` passed as `article_title` to
      `read_article`. Not reachable: `None` is never `in NON_COMIC_TITLES`, but pyrefly does
      not narrow on `in`; an explicit `is not None` now does (2026-10-13).
- [x] `ui/search_screen.py` — `Unknown | None` passed as `tag_group` to
      `ComicSearch.get_tag_group_members`. Gone with the call: `5006d5bf` (tag groups open and
      close in place) passes a `TagGroups`.
- [x] `ui/comic_book_reader.py` — the `_page_map` property returned
      `OrderedDict[str, PageInfo] | None`. Not reachable: only the goto-page dropdown reads
      it, after `set_page_map`; asserted, as `_ComicPageManager` already does (2026-10-13).
- [x] `core/comic_book_loader.py` — `get_image_ready_for_reading` unpacked a
      `self._images` entry that is `None` until its page loads. Callers show a page only once
      its load event is set; asserted, and the `# ty: ignore` dropped (2026-10-13).

## P2 — `PanelTextureLoader.load_texture`'s callers (all 7 fixed)

`570bb9aa` hoisted the index screens' shared machinery into `ui/index_screen.py`, whose call
guards `filename is None` and takes `err: Exception | None`; that cleared the
`main_index_screen` and `speech_index_screen` sites. The other two, 2026-10-13:

- [x] **`panel_path` nullability** — `ui/snapshot_applicator.py` asserted
      `image_info.filename` but passed the local `image_filename`; it asserts the local now,
      and its `# ty: ignore` is gone.
- [x] **`callback` err param** — `load_texture` calls back with `Exception | None`; both
      callbacks (`ui/bottom_title_view_screen.py`, `ui/snapshot_applicator.py`) take that.

## P3 — union too wide for a narrower declared type

A `TagGroups | Tags | Titles | str` (or similar) value flows into a narrower slot. Narrow with an
`isinstance`/guard, or widen the declared type to match reality.

- [ ] `ui/main_index_screen.py:214` — `...| str` passed as `item_id` (`TagGroups | Tags | Titles`).
- [ ] `ui/main_index_screen.py:271` — assigning `...| str` to a `TagGroups | Tags` target
      (`self._open_tag_item.id`).
- [ ] `ui/speech_index_screen.py:357` — assigning `TagGroups | Tags | Titles | str` to a `str`
      (`index_term`). Also `# ty: ignore`-ed.
- [x] `barks-fantagraphics/.../title_search.py` — a `TagGroups` appended to a `list[Tags]`, and
      that list returned as `list[TagGroups | Tags]` (two findings). Fixed by `1378b2e4`
      (`list[Tags | TagGroups]`); `0a339ead` then replaced the function with
      `get_tags_matching`.

## P4 — Path / value-type edge cases (several already `# ty: ignore`-ed)

- [ ] `core/special_overrides_handler.py:74` — `PathLike[str] / str` unsupported. Wrap the left
      operand in `Path(...)` before `/`.
- [ ] `core/reader_setup.py:41` — `zipfile.Path | pathlib.Path` passed as `inset_dir` (`pathlib.Path`)
      to `ComicsDatabase.set_inset_info`. Narrow to `pathlib.Path` (the inset dir is real-FS).
- [ ] `core/reader_setup.py:37` — `configparser.ConfigParser` vs the local `ConfigParser`
      Protocol (`core/reader_settings.py`; `.write` signature mismatch). Adjust the Protocol
      or cast. (Already `# ty: ignore`-ed in four scripts: `check_random_title_images`,
      `find-splash-pages`, `copy-reader-pngs-to-jpgs`, `panels-info`.)
- [x] `ui/comic_book_reader.py` — a value typed `object` passed as `page_index`. Gone:
      `70071147` replaced the `filter(None.__ne__, ...)` with the typed `_needed_indices()`.
- [ ] `core/reader_file_paths_resolver.py:48` + `:55` — getter union return (`PanelPath | list | None`)
      vs `list[tuple[PanelPath, bool]]`. Already `# ty: ignore[not-iterable]`. Real fix = give the
      `FILE_TYPE_FILE_GETTERS` getters precise per-category return types so the COVER/other split
      narrows. Larger refactor; low priority.
- [ ] `ui/tree_view_manager.py:283` + `:286` — `Literal[True]` assigned to attribute
      `populated` inferred as `Never`. `populated` is already a Kivy `BooleanProperty`
      (`tree_view_nodes.py`), so this is the Kivy stub gap, not a missing annotation. The
      `:283` site came with `d895eabd`; one baseline entry covers both.

## P5 — not on the July list

Found on 2026-10-13: baselined in July but never listed, or new and hidden by the column match.

- [ ] `okf_reader/ui/viewer.py:1372` — `trigger_action` on a `Widget | None`
      (`self._bar_focus_widget`), narrowed only by `in buttons`; `Widget` has no
      `trigger_action` even without the `None`. New with `c5dd09d4`; hidden behind the
      `bundle_path` entries at the same column until the 2026-10-13 regeneration.
- [ ] `core/config_info.py:118`-`:123` — six `Path` attributes set to `None`
      (`app_config_dir`, `app_config_path`, `app_data_dir`, `kivy_config_dir`,
      `app_log_path`, `error_background_path`), deferred-init and `# ty: ignore`-ed.
- [ ] `ui/main_index_screen.py:289` — `.id` read from `self._open_tag_item: IndexItem | None`
      without narrowing.
- [ ] `ui/statistics_screen.py:179` + `:183` — `.container` / `.dismiss` on
      `self._word_stat_dropdown`, deferred-init as `None`.
- [ ] `ui/kivy_standalone_show_message.py:231` — `close_button` may be unbound (it is bound
      only under `add_close_button`).
- [ ] `ui/reader_keyboard_nav.py:396`/`:397`/`:404` — `DropdownNavMixin` reads attributes of
      its host with no host Protocol (`_menu_mode`, `_exit_menu_mode`, `_handle_menu_key`);
      `# ty: ignore`-ed.
- [ ] `comic_utils/cli_setup.py:17`-`:19` — attributes set on a module (`log_level`,
      `log_filename`, `APP_LOGGING_NAME`).

---

**Progress (2026-10-13):** of the July list's 24 findings, 16 are gone (ticked above) and 8
remain; P5 adds 7 items. The baseline holds 77 entries. A proper fix often lets you delete both the
pyrefly baseline entry and a `# ty: ignore` beside it.
