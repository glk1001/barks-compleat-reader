#
# demo_tree_nojump_dropdown_single_expand.py
#
# Same as before, but now:
#   • Only ONE parent can be expanded at a time
#   • Expanding a new parent collapses the previous one
#

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock


# --------------------------------------------------------
# CLICKABLE TREE NODE
# --------------------------------------------------------

class DemoNode(ButtonBehavior, Label, TreeViewNode):

    def on_press(self):
        tv = self.parent  # TreeView instance

        # 1) Lazy populate BEFORE expand (prevents jumps)
        if hasattr(self, "populate_callback") and not getattr(self, "populated", False):
            self.populate_callback()
            self.populated = True

        # 2) Select node
        tv.select_node(self)

        # 3) Single-expand logic: collapse previous parent
        root_widget = tv.parent  # BoxLayout with scroll + tree
        if hasattr(root_widget, "_last_expanded_parent"):
            last = root_widget._last_expanded_parent
            if last is not self and getattr(last, "is_open", False):
                tv.toggle_node(last)  # collapses it

        # 4) Expand this parent
        tv.toggle_node(self)
        root_widget._last_expanded_parent = self

        # 5) Leaf behavior
        if getattr(self, "is_leaf", False):
            print(f"Leaf clicked: {self.text}")

        return super().on_press()


# --------------------------------------------------------
# ROOT UI WITH TREE + SCROLLVIEW
# --------------------------------------------------------

class DemoRoot(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        # Track last expanded parent
        self._last_expanded_parent = None

        self.scroll = ScrollView(size_hint=(1, 1))
        self.add_widget(self.scroll)

        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(20),
            size_hint_y=None
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        self.scroll.add_widget(self.tree)

        self.build_tree()

    # -----------------------------------------------------

    def build_tree(self):
        """Create 3 parents that lazily load their children."""
        for idx in range(1, 4):

            parent = DemoNode(
                text=f"[b]Parent {idx}[/b]",
                markup=True,
                font_size=22,
                color=(1, 1, 0.2, 1),
            )

            self.tree.add_node(parent)

            # Lazy populate
            parent.populated = False
            parent.populate_callback = self._make_loader(parent, idx)

    # -----------------------------------------------------

    def _make_loader(self, parent, idx):
        def _populate():
            # Create 7 leaf children
            for i in range(1, 8):
                child = DemoNode(
                    text=f"Child {idx}.{i}",
                    font_size=18,
                    color=(0.9, 0.9, 0.9, 1),
                )
                child.is_leaf = True
                child.populated = True
                self.tree.add_node(child, parent)

        return _populate


# --------------------------------------------------------
# RUN APP
# --------------------------------------------------------

class DemoApp(App):
    def build(self):
        return DemoRoot()


if __name__ == "__main__":
    DemoApp().run()
