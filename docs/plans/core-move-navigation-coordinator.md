# Plan: the navigation coordinator into `core`

> Status: **done 2026-11-22** (three commits). The coordinator is
> `core/navigation/navigation_coordinator.py` (the file kept its name) and the ports
> are `core/ports/navigation.py`. `TreePort` is `TreeViewManager` itself, with
> `get_selected_node` and `set_back_node` added; a tree node is `Any` in the ports,
> since the coordinator only hands nodes on. The year-range lookup is a `Mapping`
> keyed by `YearRangeKey` (`core/navigation/title_position.py`). The `groma`
> component file still names the old path: the maintainer's to change. One of four plans from the
> `ui` review of that date (the others: `core-move-tree-navigation-policy.md`,
> `core-move-window-geometry.md`, `core-move-document-pager.md`). Each stands alone.

## Context

`NavigationCoordinator` (`ui/navigation_coordinator.py`, about 730 lines) is the one
entry point for going to a title and opening content: the tree row, the title view's
goto-page offer, the comic, an article, a document, the wiki. It imports no Kivy at
run time. It is in `ui` only because its constructor and a few methods are typed
against widget classes, all under `TYPE_CHECKING`.

What it asks of each of them is small:

| Collaborator (ui class) | What the coordinator uses |
|---|---|
| `ViewRenderer` | `render_state`, `render_title` |
| `BottomTitleViewScreen` | `show_goto_page`, `set_overrides_state`, and reads `goto_page_active`, `goto_page_num`, `tagged_pages`, `use_overrides_active` |
| `TreeViewScreen` | `get_selected_node`, and `ids.reader_tree_view.set_back_node` |
| `TreeViewManager` | `deselect_and_close_open_nodes`, `open_node_and_parent_nodes`, `goto_node` |
| `ScreenSwitchers` | `switch_to_document_reader`, `switch_to_wiki_reader`, `switch_to_corpus_stats` |
| `UserErrorHandler` | `handle_error` (core already has `UserErrorHandlerPort`) |
| tree nodes | `ensure_populated`, `nodes` (core already has `BaseTreeViewNodeProtocol`) |

Its tests (`tests/unit/test_navigation_coordinator.py`) already hand it mocks for all
of these, so they need Kivy only for the import.

Two things in it are policy written against the tree's widgets:

- **Where a title sits in the tree.** `_get_title_parent_node` picks one of three
  dicts of year-range nodes (chronological, one-pagers, covers) that
  `ReaderTreeBuilder` fills and `MainScreen` hands over through three setters. The
  choice is made from Fantagraphics data alone.
- **`_series_nodes`** is set by `set_series_nodes` and never read.

## Goal

The coordinator is in `core/navigation`, typed against ports, importable and
testable with no Kivy. Behaviour does not change. `ui` keeps the widgets and the
wiring that builds the coordinator.

## Approach

### 1. Where a title sits: one core function

In `core/navigation` (beside `YearRangeDestination`):

```python
def title_year_range(title: Titles, fanta_info: FantaComicBookInfo) -> tuple[YearRangeKind, tuple[int, int]]
```

It returns `ONE_PAGER`, `COVER` or `CHRONO` with the year range, and raises as
`_year_range_parent_node` does now when there is none. The builder keeps one dict
keyed by `(kind, range)` in place of three, and the coordinator gets it through one
setter. `set_series_nodes` and `series_nodes` go, after a check that nothing else
reads the builder's dict.

This step is useful on its own and can be committed first, with the coordinator
still in `ui`.

### 2. Ports

New `core/ports/navigation.py`, one `Protocol` for each row of the table that has
none yet: `TitleRenderer`, `TitleViewPort`, `TreePort`, `ScreenSwitcherPort`.
Each lists only the members in the table.

`TreePort` joins what the coordinator asks of `TreeViewScreen` and
`TreeViewManager`, and takes `set_back_node` as a method of its own, so the
coordinator stops reaching through `ids`. In `ui` it is either a small adapter over
the two classes or `TreeViewManager` itself with two methods added: to be settled
when writing it (see the questions).

The four properties read off the title view become one method returning a frozen
value (`TitleViewChoices`: goto page active, page number, tagged pages, overrides
on), so the port has no attributes to keep in step.

### 3. The move

`git mv` the file to `core/navigation/coordinator.py`, change the annotations to
the ports, and re-export from `core/navigation/__init__.py`. Importers in `ui`
(`main_screen_components.py`, `tree_view_manager.py`, `main_screen.py`, others
found by grep, and any `.kv` `#: import`) change their import. The test file moves
to match and drops its Kivy fixtures.

`TitleTarget` moves with it.

### 4. Check

- unit suite, `lint-imports` (contract 1 now covers the coordinator), ty, pyrefly
- GUI suite: every navigation path runs through this class
- docs: `docs/code-walkthrough.md` and the `groma` component file name the old path;
  the map's file is the maintainer's to change

## Commits

1. `title_year_range` in core, one node dict in the builder, `series_nodes` removed.
2. The ports, with the coordinator typed against them, still in `ui`.
3. The move.

Each is green on its own. Commit 2 is the one where a mistake shows as a type error
and not as behaviour.

## Not in this plan

`ViewRenderer` and `AppInitializer` are in the same position (no Kivy at run time,
typed against widgets). They follow the same recipe, but each has its own
collaborators, so each wants its own table first.

## Questions

1. `TreePort`: an adapter class in `ui`, or two methods added to `TreeViewManager`?
   An adapter keeps the manager as it is; methods on the manager are less code.
2. Should the file keep its name (`navigation_coordinator.py`) in its new folder,
   for the sake of `git log --follow` and the docs, rather than `coordinator.py`?
