# Plan: tree navigation policy asked of the model, not of widget classes

> Status: **proposed 2026-11-22**, nothing started. One of four plans from the
> `ui` review of that date (see `core-move-navigation-coordinator.md`).

## Context

The project rule (`CLAUDE.md`, "Navigation model"): payloads live on destinations,
and widgets and coordinators route through `NavigationModel` rather than switching
on a widget subclass. Most of the tree does. These places still decide policy by
what class a node is, or by which node object it is:

| Where | What is decided | How |
|---|---|---|
| `MainScreenNavMixin._tree_nav_activate` (`ui/main_screen_nav.py`) | which screen Enter on a node moves the keys into | a dict of `id(node)` built on every press, then two `is` checks, then `isinstance(…, TitleTreeViewNode)` |
| `MainScreenNavMixin._has_view_of_its_own`, `_render_view_of`, `_open_group` | whether arriving on a node by the keys shows a view | `isinstance` on `TitleTreeViewNode` and `ButtonTreeViewNode` |
| `TreeViewManager.activate_node`, `setup_and_select_node` (`ui/tree_view_manager.py`) | title row or group row | `isinstance` |
| `TreeViewManager.on_node_expanded`, `on_node_collapsed` | a title row changes no view state | `isinstance` |
| `_REOPEN_ON_BACK` in `ui/tree_view_manager.py` | which destinations Go Back reopens as a full-window screen | a dict keyed on the destination's type, in `ui` |

The last is keyed on destinations already, so it is in the right terms and only in
the wrong package. The first is the furthest from the rule: the screens it maps to
are known from the node's destination (`MainIndexDestination`,
`SpeechIndexDestination`, `SpeechWordsDestination`, `NamesIndexDestination`,
`LocationsIndexDestination`, `StatisticsDestination`, `HistoryDestination`).

Not every `isinstance` here is policy. `TitleTreeViewNode` and `ButtonTreeViewNode`
have different methods, and a check that only narrows the type before a call
(`_auto_select_target_node`, `_child_to_open_on`) is fine as it is.

## Goal

Each question in the table is one `NavigationModel` method taking a `Destination`,
tested in `tests/unit/test_navigation_model.py` with no Kivy. The `ui` code asks
the model and acts on the answer. Behaviour does not change.

## Approach

### 1. What a node is, from its destination

Add to `NavigationModel`:

```python
def is_title(dest: Destination | None) -> bool            # TitleDestination
def bottom_screen_on_enter(dest: Destination | None) -> BottomScreen | None
def reopens_on_back(dest: Destination | None) -> ReopenKind | None
```

`BottomScreen` is a new enum in `core/navigation` (main index, speech index, names
index, locations index, statistics, history). `ReopenKind` is one too (wiki, corpus
statistics, document).

A prerequisite to check first, by a test over the built tree: every
`TitleTreeViewNode` has a `TitleDestination`, and nothing else has. If an article or
collection row breaks that, `is_title` has to say so in the model, and that case is
written into the test.

### 2. Enter on a node

`_tree_nav_activate` asks `bottom_screen_on_enter(selected.destination)` and looks
the enum up in a dict of screens built once in the mixin's setup. The `id(node)`
dict and the two `is` checks go. `treeview_index_node` on the index screens stays:
the index screens keep their saved state on it.

### 3. Go Back

`_REOPEN_ON_BACK` becomes `reopens_on_back` in the model; `TreeViewManager` keeps a
three-entry dict from `ReopenKind` to the coordinator call. The comment on why
these three reopen moves to the model with the rule.

### 4. Title row or group row

Where the manager and the mixin branch on `isinstance(node, TitleTreeViewNode)` to
decide what happens, they ask `is_title(node.destination)`. Where the branch then
calls a method only one class has, a narrowing check stays, on the line that needs
it.

`_open_group` ("an open group with a view of its own") is a question about the
tree's state as well as the node's kind; it stays in `ui`, using `is_title`.

## Commits

1. The model's three methods and enums, with tests. No caller yet.
2. Enter on a node (step 2).
3. Go Back (step 3).
4. Title or group (step 4).

Each is green on its own. The GUI suite runs after 2, 3 and 4: the remote-key
tests walk exactly these paths.

## Relation to the coordinator plan

Independent. If both are done, do this one first: it adds to `NavigationModel`,
which the coordinator would then sit beside.

## Questions

1. Is the prerequisite true today (title rows and `TitleDestination` one to one)?
   The plan's first act is the test that answers it.
2. `BottomScreen` names screens in `core`. That is a name, not a widget, and
   `SearchScreenMode` in `core/search_focus.py` is a precedent; say if you would
   rather the model returned the destination type and `ui` kept the whole mapping.
