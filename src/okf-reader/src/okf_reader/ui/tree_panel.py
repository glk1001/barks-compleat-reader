"""The contents tree: the bundle's folders and pages, one branch open at a time.

A folder's pages are read the first time it opens. The tree's selection band is the
keyboard's focus in it, and it follows the page on display however that was reached.
The viewer says what opening a page does and where the keys go on leaving the tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.treeview import TreeView, TreeViewLabel

from okf_reader.core.bundle import BundleDir, has_children, list_children
from okf_reader.ui import trace

from .keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_HOME,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    NAV_NOOP_KEYS,
    step_index,
)
from .widgets import DirNode, PageNode, scroll_view

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from okf_reader.core.bundle import ConceptNode
    from okf_reader.core.theme import ViewerThemeSpec

# One size for all the sidebar's text — tree rows, the search field, and result
# rows — a step under Kivy's 15sp Label default, so the navigation column reads
# as chrome next to the page body.
TREE_PANEL_FONT_SIZE = 13  # sp
# Tighter tree indents than Kivy's defaults (24/16dp), buying the deeper
# branches text room in the narrow panel. The disclosure arrow draws 20dp left
# of a node's x (style.kv <TreeViewNode>), so TREE_INDENT_START may not go
# below 20 without clipping the top level's arrows at the panel edge.
TREE_INDENT_START = 20  # dp — space before a top-level node's text
TREE_INDENT_LEVEL = 12  # dp — extra indent per tree depth

# Frames the reveal will wait for the tree's geometry to stop moving before
# scrolling to the banded node anyway (a runaway backstop, ~0.5s at 60fps —
# settling normally takes a frame or three).
TREE_REVEAL_MAX_FRAMES = 30

# When the quarter-way placement (`scroll_node_into_view`) would stop this
# close to the very top of the tree, snap to the top instead: stopping a few
# pixels short leaves the first row clipped by a sliver, which reads as a bug —
# about one tree row's height, so anything less than a full hidden row snaps.
TREE_TOP_SNAP = 28  # dp


class TreePanel:
    """The contents tree in its scroll view, and the keys that walk it."""

    def __init__(
        self,
        bundle: Path,
        theme: ViewerThemeSpec,
        *,
        on_open_page: Callable[[Path], None],
        on_cross_to_page: Callable[[], None],
        on_up_off_top: Callable[[], None],
    ) -> None:
        """Build the tree with the bundle's top level in it; `scroll` is what to lay out.

        Args:
            bundle: The bundle's folder.
            theme: The colors the embedding app themes the tree with.
            on_open_page: Shows the page a selected node stands for.
            on_cross_to_page: Hands the keys to the page panel, after Right or Enter on a page.
            on_up_off_top: Takes the keys when Up is pressed on the first node.

        """
        self._bundle = bundle
        self._theme = theme
        self._on_open_page = on_open_page
        self._on_cross_to_page = on_cross_to_page
        self._on_up_off_top = on_up_off_top
        self.syncing = False  # True while a node is selected to mirror the page on display
        self.scroll = scroll_view(theme, size_hint=(1, 1), do_scroll_x=False)
        self.tree = TreeView(
            # No visible root: the bundle-root node spent an indent level (and a
            # row) on no information; the tiers are the effective top level.
            hide_root=True,
            # Grow with the content instead of squeezing into the viewport — a
            # ScrollView only scrolls a child that is taller than itself.
            size_hint_y=None,
            indent_start=dp(TREE_INDENT_START),
            indent_level=dp(TREE_INDENT_LEVEL),
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        # bind passes (treeview, selected_node); we only want the node (2nd arg)
        self.tree.bind(selected_node=lambda *args: self.on_node(args[1]))
        self.scroll.add_widget(self.tree)
        # Lazy: load only the bundle's top level (all tiers) now; each directory's
        # children are read on first expansion (see _on_dir_open). This keeps startup
        # cheap even though the full bundle is ~900 files across ~200 dirs.
        self.add_nodes(list_children(bundle), None)

    def add_nodes(
        self, nodes: Iterable[BundleDir | ConceptNode], parent: TreeViewLabel | None
    ) -> None:
        # Bind one level of the Kivy-free bundle model (okf_reader.core list_children)
        # to TreeView widgets; the frontmatter reads for this level already happened there.
        for node in nodes:
            if isinstance(node, BundleDir):
                tv = DirNode(
                    node.path,
                    text=node.title or node.name,
                    font_size=sp(TREE_PANEL_FONT_SIZE),
                    bold=True,
                    color=self._theme.dir_text,
                    color_selected=self._theme.selection,
                    even_color=self._theme.row_stripe_even,
                    odd_color=self._theme.row_stripe_odd,
                )
                self.tree.add_node(tv, parent)
                # Disclosure triangle only when there is something to open (cheap
                # existence scan); the real children still load lazily on expand.
                tv.is_leaf = not has_children(node.path)
                tv.bind(is_open=self._on_dir_open)
            else:  # ConceptNode
                tv = PageNode(
                    node.path,
                    text=node.title,
                    font_size=sp(TREE_PANEL_FONT_SIZE),
                    color=self._theme.title_text,
                    color_selected=self._theme.selection,
                    even_color=self._theme.row_stripe_even,
                    odd_color=self._theme.row_stripe_odd,
                )
                self.tree.add_node(tv, parent)

    def _on_dir_open(self, dir_node: DirNode, is_open: bool) -> None:
        # Fires on both open and close; populate a directory's children once, lazily.
        if not is_open:
            trace.tree_branch_closed(dir_node.text)
            return
        if not dir_node.loaded:
            dir_node.loaded = True
            self.add_nodes(list_children(dir_node.bundle_path), dir_node)
        self._close_other_branches(dir_node)
        trace.tree_branch_opened(dir_node.text)

    def _close_other_branches(self, opened: TreeViewLabel) -> None:
        """Close every open node outside ``opened``'s ancestor chain.

        The Barks Reader's accordion rule: one open path at a time. Other
        branches are closed depth-first (children before parents), so nothing
        keeps a stale expanded state to spring back on its next open. Each
        toggle re-fires _on_dir_open with is_open=False, which returns
        immediately.
        """
        keep = {opened}
        node = opened.parent_node
        while node is not None:
            keep.add(node)
            node = node.parent_node

        def close_subtree(node: TreeViewLabel) -> None:
            for child in node.nodes:
                if child.is_open:
                    close_subtree(child)
                    self.tree.toggle_node(child)

        def walk(parent: TreeViewLabel) -> None:
            for child in parent.nodes:
                if not child.is_open:
                    continue
                if child in keep:
                    walk(child)  # on the kept path: only prune its off-path branches
                else:
                    close_subtree(child)
                    self.tree.toggle_node(child)

        walk(self.tree.root)

    def on_node(self, node: TreeViewLabel | None) -> None:
        if self.syncing:
            return  # programmatic selection mirroring the page already on display
        if isinstance(node, PageNode):
            self._on_open_page(node.file_path)
            return
        # A directory: show its reserved index.md listing when it has one. Its
        # relative links resolve against the directory (resolve_link gets the
        # index.md as the page path), so the listing is navigable.
        if isinstance(node, DirNode):
            index = node.bundle_path / "index.md"
            if index.is_file():
                self._on_open_page(index)

    def handle_key(self, key: int) -> bool:
        """Walk the contents tree: the selection band is the keyboard focus."""
        nodes = list(self.tree.iterate_open_nodes())
        if not nodes:
            return key in NAV_NOOP_KEYS
        focused = self.tree.selected_node
        idx = nodes.index(focused) if focused in nodes else None
        node = focused if idx is not None else None
        if key == KEY_UP and idx == 0:
            self._on_up_off_top()  # the remote's way into the search box
        elif key in (KEY_UP, KEY_DOWN):
            self._move(nodes, idx, 1 if key == KEY_DOWN else -1)
        elif key == KEY_HOME:
            self.focus_node(nodes[0])
        elif key == KEY_END:
            self.focus_node(nodes[-1])
        elif key == KEY_RIGHT:
            self.expand(node)
        elif key == KEY_LEFT:
            self._collapse(node)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate(node)
        else:
            return False
        return True

    def _move(self, nodes: list, idx: int | None, delta: int) -> None:
        """Move the focus band up or down the visible nodes (clamped, no wrap)."""
        if idx is None:
            new_idx = 0 if delta > 0 else len(nodes) - 1
        else:
            new_idx = step_index(idx, len(nodes), delta)
        self.focus_node(nodes[new_idx])

    def expand(self, node: TreeViewLabel | None) -> None:
        """Right in the tree: drill rightward — expand a directory, or cross to the page.

        The spatial continuum for a 6-button remote: Right keeps moving
        "rightward" — a closed directory expands, an open one steps into its
        first child, and a page leaf (nothing left to expand) opens its page
        exactly as Enter would and crosses over to the page panel to read it.
        """
        if node is None:
            self._on_cross_to_page()
            return
        if node.is_leaf:
            self._open_leaf_and_cross_to_page(node)
            return
        if not node.is_open:
            self.tree.toggle_node(node)  # lazy children load via _on_dir_open
            Clock.schedule_once(lambda _dt: self.scroll_node_into_view(node), 0)
        elif node.nodes:
            self.focus_node(node.nodes[0])

    def _collapse(self, node: TreeViewLabel | None) -> None:
        """Close the focused directory, or move the focus band to the parent."""
        if node is None:
            return
        if node.is_open and not node.is_leaf:
            self.tree.toggle_node(node)
        elif node.parent_node is not None and node.parent_node is not self.tree.root:
            self.focus_node(node.parent_node)

    def _activate(self, node: TreeViewLabel | None) -> None:
        """Open the focused leaf's page, or toggle a directory open/closed.

        Enter on a page leaf behaves exactly like Right: it opens the page and
        crosses over to the page panel to read it. Enter on an open section
        closes it (the main Barks tree's convention), so a reader scrolled up
        to the section heading can put the list away; on a closed one it
        expands and shows the section's index listing.
        """
        if node is None:
            return
        if node.is_leaf:
            self._open_leaf_and_cross_to_page(node)
            return
        was_open = node.is_open
        self.tree.toggle_node(node)
        if not was_open:
            self.on_node(node)

    def _open_leaf_and_cross_to_page(self, node: TreeViewLabel) -> None:
        """Open a page leaf's page and hand the keys to the page panel."""
        self.on_node(node)
        self._on_cross_to_page()

    def focus_node(self, node: TreeViewLabel) -> None:
        """Move the tree's selection band to ``node`` without navigating."""
        self.syncing = True
        try:
            self.tree.select_node(node)
        finally:
            self.syncing = False
        self.scroll_node_into_view(node)
        trace.tree_focus(node.text)

    def sync_to(self, path: Path) -> None:
        """Select and reveal the tree node for ``path``, expanding ancestors as needed.

        Keeps the tree in step with pages reached through links or Back. Walks the
        node's ancestor directories, lazily populating and opening each (the same
        loading path as a manual expand), then selects the node — a directory node
        when ``path`` is an ``index.md``, the concept leaf otherwise.
        """
        try:
            rel = path.resolve().relative_to(self._bundle.resolve())
        except ValueError:
            return
        # The directory node walked to so far (None == tree root).
        dir_node: DirNode | None = None
        children = self.tree.root.nodes
        for part in rel.parts[:-1]:
            dir_node = next(
                (n for n in children if isinstance(n, DirNode) and n.bundle_path.name == part),
                None,
            )
            if dir_node is None:
                return  # not represented in the tree (e.g. hidden dir) — nothing to sync
            if not dir_node.loaded:  # populate before opening, as a manual expand would
                dir_node.loaded = True
                self.add_nodes(list_children(dir_node.bundle_path), dir_node)
            if not dir_node.is_open:
                self.tree.toggle_node(dir_node)
            children = dir_node.nodes
        target: TreeViewLabel | None
        if rel.name == "index.md":  # a directory's own page selects the directory node
            target = dir_node  # None for the bundle root's index — no visible node
        else:
            resolved = path.resolve()
            target = next(
                (
                    n
                    for n in children
                    if isinstance(n, PageNode) and n.file_path.resolve() == resolved
                ),
                None,
            )
        if target is None or self.tree.selected_node is target:
            return
        self.syncing = True
        try:
            self.tree.select_node(target)
        finally:
            self.syncing = False
        # Scroll once the freshly-expanded tree has actually been laid out — a
        # single-frame deferral is not enough after a large expansion.
        self.reveal_when_settled(target)

    def reveal_when_settled(self, node: TreeViewLabel) -> None:
        """Scroll ``node`` into view once the tree's geometry has stopped moving.

        Right after a page sync or a fresh open, a large lazy expansion (e.g.
        the one-pagers section) and the host's deferred viewer sizing keep
        relaying the tree out for several frames; scrolling immediately would
        compute against node positions the layout has not yet placed and land
        the panel at the bottom. Poll once per frame and scroll only when two consecutive
        frames agree on the geometry (with a frame-count backstop so a
        perpetually-animating layout cannot stall the reveal forever).
        """
        state: dict[str, tuple[float, float, float, float] | int | None] = {
            "last": None,
            "frames": 0,
        }

        def check(_dt: float) -> None:
            # Width is watched too: the labels wrap to the tree's width, so a late
            # panel resize reflows every row height below the wrap point.
            geometry = (node.top, self.tree.width, self.tree.height, self.scroll.height)
            frames = state["frames"]
            assert isinstance(frames, int)
            if geometry == state["last"] or frames >= TREE_REVEAL_MAX_FRAMES:
                trace.tree_settled(node.text, frames)
                self.scroll_node_into_view(node)
                return
            state["last"] = geometry
            state["frames"] = frames + 1
            Clock.schedule_once(check, 0)

        Clock.schedule_once(check, 0)

    def scroll_node_into_view(self, node: TreeViewLabel) -> None:
        """Scroll the tree panel so ``node`` sits about a quarter of the way down.

        ScrollView.scroll_to would stop as soon as the node is visible, typically
        leaving it hugging the bottom edge; positioning it near the top keeps the
        following siblings (what you usually scan next) on screen.
        """
        viewport_h = self.scroll.height
        content_h = self.tree.height
        if content_h <= viewport_h:
            return  # everything already visible
        node_top = node.top - self.tree.y  # node top, measured from the tree's bottom
        offset = 0.25 * viewport_h
        scroll = (node_top - viewport_h + offset) / (content_h - viewport_h)
        # Snap to the very top when the placement would land within a row of it,
        # so the first row is never left clipped by a sliver (see TREE_TOP_SNAP).
        if (1.0 - scroll) * (content_h - viewport_h) < dp(TREE_TOP_SNAP):
            scroll = 1.0
        self.scroll.scroll_y = max(0.0, min(1.0, scroll))
