#
# demo_tree_nojump_dropdown_select.py
#
# TreeView demo with:
#   • Lazy-populate done in on_press() BEFORE expand
#   • No scroll jumps
#   • Parent pinned while children drop down
#   • Selection highlighting
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
#   CLICKABLE TREE NODE
# --------------------------------------------------------

class DemoNode(ButtonBehavior, Label, TreeViewNode):

    def on_press(self):
        """
        Handle:
            1) Lazy populate (BEFORE expand)
            2) Select node
            3) Toggle expand
        """

        tv = self.parent  # TreeView

        # --------------------------
        # LAZY POPULATE (BEFORE EXPAND)
        # --------------------------
        if hasattr(self, "populate_callback") and not getattr(self, "populated", False):
            self.populate_callback()  # creates real children immediately
            self.populated = True

        # --------------------------
        # SELECT NODE
        # --------------------------
        tv.select_node(self)

        # --------------------------
        # EXPAND AFTER CHILDREN EXIST
        # (prevents scroll jumps)
        # --------------------------
        tv.toggle_node(self)

        # Action for leaf clicks
        if getattr(self, "is_leaf", False):
            print(f"Leaf clicked: {self.text}")

        return super().on_press()


# --------------------------------------------------------
#   MAIN UI
# --------------------------------------------------------

class DemoRoot(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        # ScrollView wraps the TreeView
        self.scroll = ScrollView(size_hint=(1, 1))
        self.add_widget(self.scroll)

        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(20),
            size_hint_y=None
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))

        self.scroll.add_widget(self.tree)

        # Build content
        self.build_tree()

    # ----------------------------------------------------

    def build_tree(self):
        """Create parent nodes that lazily load children."""
        for idx in range(1, 4):
            parent = DemoNode(
                text=f"[b]Parent {idx}[/b]",
                markup=True,
                font_size=22,
                color=(1, 1, 0.2, 1)
            )

            self.tree.add_node(parent)

            # Mark lazy
            parent.populated = False
            parent.populate_callback = self._make_loader(parent, idx)

    # ----------------------------------------------------

    def _make_loader(self, parent, idx):
        """
        Create the function that adds children.
        """
        def _populate():
            for i in range(1, 8):
                child = DemoNode(
                    text=f"Child {idx}.{i}",
                    font_size=18,
                    color=(0.9, 0.9, 0.9, 1)
                )
                child.is_leaf = True
                child.populated = True
                self.tree.add_node(child, parent)

        return _populate


# --------------------------------------------------------
#   RUN APP
# --------------------------------------------------------

class DemoApp(App):
    def build(self):
        return DemoRoot()


if __name__ == "__main__":
    DemoApp().run()
