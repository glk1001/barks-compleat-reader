# pyrefly annotation-debt checklist

The 24 "union-type / nullability" findings pyrefly surfaced that are **grandfathered** in
`pyrefly-baseline.json` (see `pyrefly.toml`). None block anything — work through them
**opportunistically** when you're already in the file. After fixing one:

```bash
bash scripts/pyrefly.sh --update-baseline   # regenerates the baseline minus what you fixed
```

The baseline shrinks over time. These are *real* type imprecision (unlike the ~60 Kivy-boundary
items also baselined, which need the stubs work in `reference_kivy_stubs`). Fix notes below are a
**starting point derived from the type errors** — verify at the call site; some may reveal a real
`None`/wrong-variant bug, which is the point.

> Cross-repo caution: `title_search.py` lives in `barks-fantagraphics` (consumed by sibling repos);
> `reader_setup.py:37` involves a `ConfigParser` Protocol. Change public signatures there carefully.

---

## P1 — possible real `None` bugs (verify first: is `None` actually reachable?)

Each is a spot where a possibly-`None` value flows into a parameter/return declared non-`None`.
If `None` can occur at runtime → real bug, add a guard. If it genuinely can't → tighten the source
type or `assert x is not None`.

- [ ] `ui/barks_reader_app.py:314` — `Unknown | None` passed as `parser` (ConfigParser) to
      `bootstrap_reader_environment`. Narrow with `is not None` (or fix the source's type).
- [ ] `ui/navigation_coordinator.py:231` — `Titles | None` passed as `article_title` (Titles) to
      `read_article`. Guard or make the caller's value non-optional.
- [ ] `ui/search_screen.py:349` — `Unknown | None` passed as `tag_group` (TagGroups) to
      `ComicSearch.get_tag_group_members`. Guard.
- [ ] `ui/comic_book_reader.py:362` — returns `OrderedDict[str, PageInfo] | None` but declared
      `OrderedDict[...]`. Either narrow before return or widen the return type to `| None`.
- [ ] `core/comic_book_loader.py:217` — `not-iterable`: iterating a value typed `None`. Guard the
      iteration or fix the source type.

## P2 — one shared signature, clears 8 findings at 4 call sites

All from `PanelTextureLoader.load_texture` (`ui/panel_texture_loader.py`). Two independent fixes:

- [ ] **`panel_path` nullability** — callers pass `... | None`, param declares no `None`.
      Decide: does `load_texture` handle `None`? If yes, widen its `panel_path` param to `| None`.
      If no, guard at each caller. Sites:
      `ui/main_index_screen.py:225`, `ui/snapshot_applicator.py:224`, `ui/speech_index_screen.py:466`.
- [ ] **`callback` err param** — callers pass `(tex, err: Exception) -> None`; `load_texture` calls
      it with `Exception | None`. Widen each callback's `err` annotation to `Exception | None`. Sites:
      `ui/bottom_title_view_screen.py:236`, `ui/main_index_screen.py:225`,
      `ui/snapshot_applicator.py:224`, `ui/speech_index_screen.py:466`.

## P3 — union too wide for a narrower declared type

A `TagGroups | Tags | Titles | str` (or similar) value flows into a narrower slot. Narrow with an
`isinstance`/guard, or widen the declared type to match reality.

- [ ] `ui/main_index_screen.py:235` — `...| str` passed as `item_id` (`TagGroups | Tags | Titles`).
- [ ] `ui/main_index_screen.py:292` — assigning `...| str` to a `TagGroups | Tags` target.
- [ ] `ui/speech_index_screen.py:502` — assigning `TagGroups | Tags | Titles | str` to a `str`.
- [ ] `barks-fantagraphics/.../title_search.py:154` — appending `TagGroups` into a `list[Tags]`.
- [ ] `barks-fantagraphics/.../title_search.py:156` — returning `list[Tags]` where
      `list[TagGroups | Tags]` is declared. (154 + 156 are one fix — the list's element type.)

## P4 — Path / value-type edge cases (several already `# ty: ignore`-ed)

- [ ] `core/special_overrides_handler.py:74` — `PathLike[str] / str` unsupported. Wrap the left
      operand in `Path(...)` before `/`.
- [ ] `core/reader_setup.py:41` — `zipfile.Path | pathlib.Path` passed as `inset_dir` (`pathlib.Path`)
      to `ComicsDatabase.set_inset_info`. Narrow to `pathlib.Path` (the inset dir is real-FS).
- [ ] `core/reader_setup.py:37` — `configparser.ConfigParser` vs the local `ConfigParser` Protocol
      (`.write` signature mismatch). Adjust the Protocol or cast. (Already `# ty: ignore`-ed in scripts.)
- [ ] `ui/comic_book_reader.py:623` — value typed `object` passed as `page_index` (`int`). Add the
      right annotation/cast at the source so it's `int`.
- [ ] `core/reader_file_paths_resolver.py:48` + `:55` — getter union return (`PanelPath | list | None`)
      vs `list[tuple[PanelPath, bool]]`. Already `# ty: ignore[not-iterable]`. Real fix = give the
      `FILE_TYPE_FILE_GETTERS` getters precise per-category return types so the COVER/other split
      narrows. Larger refactor; low priority.
- [ ] `ui/tree_view_manager.py:254` — `Literal[True]` assigned to attribute `populated` inferred as
      `Never`. `populated` needs an explicit type (likely a bool attr/property mis-inferred). Annotate it.

---

**Progress:** 24 items. As they're fixed, note that several are *also* `# ty: ignore`-ed — a proper
fix lets you delete both the pyrefly baseline entry and the ty-ignore.
