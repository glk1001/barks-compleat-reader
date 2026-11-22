# Plan: the document reader's page walk as a core `DocumentPager`

> Status: **done 2026-11-22** (both commits). The story links stayed the screen's
> and `single_page` stayed its property, passed as `two_up` (the two questions'
> defaults); the pager gained `is_open`, `page_count` and `current_page_index`.
> One of four plans from the
> `ui` review of that date (see `core-move-navigation-coordinator.md`). The
> smallest of the four.

## Context

`DocumentReaderScreen` (`ui/document_reader.py`) shows a folder of page images: the
illustrated history's chapters, the how-to, the introduction. Which page is showing
is a model kept in the screen's own attributes:

- `_page_paths`, `_units`, `_unit_idx_for_index` (from
  `core.display_unit.build_document_units`), `_current_page_index`
- `_last_page_indexes`, each folder's page when it was last left, for `resume`
- `_story_links`, the links of the page or pair showing

and its rules are in the screen's methods:

| Method | Rule |
|---|---|
| `open_document` | start at the first page, or with `resume` at the page last left, held inside the document |
| `_current_unit` | on the spread the page shows with its pair; alone otherwise, or when `single_page` |
| `_update_page_source` | the current page becomes its unit's left page; the links are both pages'; the page is remembered for the folder |
| `next_page` | go to the page after the last one showing, if there is one; an empty document does nothing |
| `prev_page` | go back one page, to show as its unit does; stay on the first |

None of it needs Kivy. The tests (`tests/unit/test_document_reader.py`) build the
screen to reach it. The comic reader has the same split already: `ComicPageManager`
in `core` holds the walk, `ComicBookReader` draws it.

## Goal

A `DocumentPager` in `core` holds the walk and is tested with page counts alone.
The screen keeps the widgets, the properties its `.kv` binds, the log lines, the
taps and the keys. Behaviour does not change.

## Approach

### 1. The pager

New `core/document_pager.py`:

```python
@dataclass(frozen=True, slots=True)
class DocumentView:
    left: Path
    right: Path | None
    left_index: int
    right_index: int | None
    page_count: int

class DocumentPager:
    def open(self, doc_dir: Path, pages: list[Path], *, resume: bool) -> None
    def close(self) -> None
    def view(self, *, two_up: bool) -> DocumentView | None   # None: no pages
    def next_page(self, *, two_up: bool) -> bool             # whether the page changed
    def prev_page(self) -> bool
```

`two_up` is the screen's "spread layout and not `single_page`", passed in on each
call because the layout can change under an open document (`on_layout_mode`).

`view` does what `_update_page_source` does to the model: snaps the current page to
its unit's left page and remembers it for the folder. The pager owns
`_last_page_indexes`, so it outlives its documents as the screen does now.

The pager takes the list of pages; `list_document_pages` stays the caller's, as it
reads the disk.

### 2. The screen

`open_document` lists the pages and calls `open`. `_update_page_source` asks for
the view and sets `page_source`, `right_page_source`, the story links (still
`load_story_links` here: it reads files) and logs the page markers from the view's
indexes. `next_page` and `prev_page` call the pager and update if it moved.
`close` calls `close`. The six attributes go.

The log markers and their order are part of the GUI tests' contract and must come
out unchanged: `DOCUMENT_OPENED`, `DOCUMENT_PAGE`, `DOCUMENT_RIGHT_PAGE`.

### 3. Tests

New `tests/unit/test_document_pager.py`, from the rules in the table, with these
cases named:

- an empty document: no view, and neither step moves
- an odd page count on the spread: the last page alone
- stepping forward from a pair lands on the next pair's left page
- stepping back from a pair's left page shows the pair before it
- the layout changing between steps (two-up to one-up and back)
- `resume` after the folder has fewer pages than before
- two folders remembered apart

The screen's tests that only reach the walk are thinned to one or two that show
the screen draws what the pager says.

## Commits

1. `DocumentPager` and its tests; no caller.
2. The screen on the pager.

Each is green on its own. The GUI suite after 2 (document paging, the history
chapters, Go Back into a chapter at the page it was left on).

## Questions

1. Should the story links move too, as a second step? They are a per-view lookup
   from files beside the pages; a pager that returned them would need the loader
   passed in. Left out here to keep the pager free of file reads.
2. `single_page` stays the screen's, passed as `two_up=False`. Say if you would
   rather the pager held it from `open`.
