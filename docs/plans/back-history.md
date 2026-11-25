# Plan: a full history behind Go Back

> Status: **design agreed 2026-11-25, not yet built.** The three decisions at the end
> were the maintainer's, taken that day.

## Context

Go Back (the action bar's button, `MainScreen.on_action_bar_go_back`) has one slot.
`ReaderTreeView.on_selected_node` (`ui/tree_view_nodes.py`) keeps only
`previous_selected_node`, and going back is itself a selection, so the slot then
holds the node just left. Back therefore swaps between the last two nodes, and
anything older is gone. With no previous node it collapses the tree.

The app now has trails several hops long (search, a title, its wiki page, another
title; an index, a story, a playlist). On a six-key remote, walking back through the
tree by hand is costly, and Back is the only cheap way out. A swap undoes one hop.

Four things in the code shape the design:

- **Every selection counts.** `on_selected_node` records the previous node for any
  selection, including each row an arrow key passes in
  `MainScreenNav._tree_nav_move`. A stack fed the same way fills with every row
  walked past.
- **Closing the tree wipes the slot.** `TreeViewScreen.deselect_and_close_open_nodes`
  calls `reset_selection_tracking`, so go-to-title (`NavigationCoordinator`) and the
  bar's Search (`TreeViewManager.open_search`) each save the node first and put it
  back with `set_back_node`.
- **The slot holds a widget.** Rows made lazily are replaced, so
  `TreeViewManager._clear_and_repopulate` moves the slot to the parent.
- **A `Destination` does not name a row.** One title sits under Chronological,
  Series, Categories and more. The saved-node restore already names a row by its
  path of node names (`get_tree_view_node_path`, `TreeViewScreen.find_node_by_path`),
  and the history uses the same.

## The rule: history records jumps, not steps

| Gesture | Kind | Effect on the history |
|---|---|---|
| Up, Down or Left moving through the tree | step | Updates where you are; nothing is pushed |
| A selection made inside one gesture (Search opening on Titles, the single-title child, the collapse overlay) | step | The same |
| A click or Enter on a node; go-to-title from an index, a search, a fun image, a wiki or document link; the bar's Search | jump | Pushes the place left |
| Collapse | jump to nowhere | Pushes the place left, so Back undoes a Collapse |
| Go Back | pop | Never pushes |

Arrow steps are already cheap to undo with the arrows. Back undoes what the arrows
cannot.

## The model

A new class, `BackHistory`, in `core/navigation/`, with no Kivy in it:

- It holds the current location and a stack of locations. A location is the tuple of
  node names from the root; nowhere (the collapsed tree) is `None`.
- `visit(location, kind)` takes a step or a jump. A jump pushes the current location
  when there is one and it differs from the new one; a step only replaces it.
- `back()` pops the top location and makes it the current one, pushing nothing.
- A push equal to the top of the stack is skipped. The stack holds 30; the oldest is
  dropped.
- It lasts the session and is not saved. The saved-node restore covers startup.

## Wiring

- `ReaderTreeView.on_selected_node` reports each selection to the model, as a jump
  unless told otherwise.
- The arrow moves (`MainScreenNav._tree_nav_move`, `_tree_nav_collapse_to_parent`)
  and the selections `TreeViewManager` makes inside a gesture run under
  `with tree.stepping():` and count as steps.
- The user's Collapse (`TreeViewManager.deselect_and_close_open_nodes` with
  `from_collapse_all`) reports a jump to nowhere. The closes made on the way to
  somewhere else report nothing.
- `TreeViewManager.go_back_to_previous_node` pops a path, finds its node with
  `find_node_by_path`, and then does what it does now: `NavigationModel.reopens_on_back`
  for the wiki, By the Numbers and the chapters, `keep_images=True` for the rest.
- A path that no longer finds a node (a deleted playlist, a random list made again)
  is skipped with a log line and the next is tried.
- An empty stack collapses the tree, as now.

## What goes

`previous_selected_node`, `reset_selection_tracking`, `set_back_node` on the tree,
on `TreeViewManager` and on `TreePort`, the save-and-restore in go-to-title and
`open_search`, and the move to the parent in `_clear_and_repopulate`. Closes made inside the
app no longer touch the history, and a path does not go stale when its row is made
again.

## Not in this version

- No Forward button: the action bar and the remote have no room for one.
- No screen state in an entry. Going back to Search shows the search last made, not
  the one from three hops before.
- The wiki reader's own back, within its pages, stays as it is.

## Tests, markers and docs

- **Unit:** `BackHistory` alone: step against jump, the skipped duplicate, the cap,
  the empty stack. The Go Back tests in `test_tree_view_manager.py`,
  `test_reader_ui_classes.py` and `test_navigation_coordinator.py` are rewritten to
  match, with one for a stale path.
- **Log markers:** `GOING_BACK_TO_NODE` gains how many entries remain; a new marker
  says a stale entry was skipped. Each has a `loguru_sink` test.
- **GUI:** three jumps, then Back three times and a fourth that collapses; and rows
  walked with the arrows, then Back, which passes over them. Each GUI test that goes
  back now is checked for leaning on the swap.
- **Docs:** the Go Back paragraph in `docs/code-walkthrough.md`.

## Commits

1. `BackHistory` and its unit tests; nothing uses it yet.
2. The wiring, the removals, the markers, the GUI tests and the walkthrough.

## Decisions taken (2026-11-25)

1. **Jumps only.** The other way pushed every row whose view was shown: nearer a
   browser, but Back then crawls through a list walked on the remote.
2. **Back undoes a Collapse.** Today a Collapse wipes the slot.
3. **The swap goes.** Back twice no longer returns to where you began; it goes two
   places back.
