from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock


# ----------------------------------------------------------
#   TREE NODE WIDGET (Selectable + Expandable)
# ----------------------------------------------------------

class Node(ButtonBehavior, Label, TreeViewNode):

    def on_press(self):
        """Runs BEFORE expand. Perfect place to do lazy populate."""
        parent_tree = self.parent

        # Only expandable nodes have populate_callback + children list
        if hasattr(self, "populate_callback") and not self.populated:
            self.populate_callback()   # <-- create children BEFORE expand
            self.populated = True

        # Now toggle the expand/collapse
        parent_tree.toggle_node(self)

        # Dummy user callback
        if hasattr(self, "is_leaf") and self.is_leaf:
            print(f"Leaf clicked: {self.text}")

        return super().on_press()


# ----------------------------------------------------------
#   MAIN UI
# ----------------------------------------------------------

class DemoRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.scroll = ScrollView(size_hint=(1, 1))
        self.add_widget(self.scroll)

        # Setup the TreeView
        self.tree = TreeView(
            hide_root=True,
            indent_level=dp(20),
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        self.scroll.add_widget(self.tree)

        # Build tree
        self.build_demo_tree()

    # ------------------------------------------------------
    # BUILD THE DEMO TREE WITH LAZY POPULATE
    # ------------------------------------------------------
    def build_demo_tree(self):

        # Root-level expandable nodes
        for i in range(1, 4):
            parent = self.add_expandable_node(f"Group {i}")

            # lazy callback
            parent.populate_callback = self.make_lazy_loader(parent, i)
            parent.populated = False

    def add_expandable_node(self, text):
        return self.tree.add_node(Node(text=text, font_size=20))

    # Lazy loader factory
    def make_lazy_loader(self, parent, index):
        def _populate():
            print(f"Populating children of {parent.text}")

            for n in range(1, 6):  # 5 children per group
                leaf = Node(text=f"   Item {index}.{n}",
                            font_size=18)
                leaf.is_leaf = True
                leaf.populated = True
                self.tree.add_node(leaf, parent)
        return _populate


class DemoApp(App):
    def build(self):
        return DemoRoot()


if __name__ == "__main__":
    DemoApp().run()
