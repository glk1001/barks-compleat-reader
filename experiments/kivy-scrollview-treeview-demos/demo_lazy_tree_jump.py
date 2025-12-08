#
# demo_lazy_tree_jump.py
#
# A minimal reproducible example of:
# - TreeView embedded in ScrollView
# - Lazy loading of children when parent node is expanded
# - The ScrollView "jump" when many new child widgets are inserted
#
# Run with: python3 demo_lazy_tree_jump.py
#

import kivy

kivy.require("2.3.0")

from kivy.app import App
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock


class LazyDemo(App):
    def build(self):
        root = BoxLayout(orientation="vertical")

        sv = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["bars", "content"],
            bar_width=12,
        )

        self.tv = TreeView(
            hide_root=True,
            size_hint_y=None,
        )
        self.tv.bind(minimum_height=self.tv.setter("height"))
        self.tv.bind(on_node_expand=self.on_expand)

        # Add the TreeView to the ScrollView
        sv.add_widget(self.tv)
        root.add_widget(sv)

        # Add several top-level nodes
        for i in range(5):
            parent = self.tv.add_node(TreeViewLabel(text=f"Parent {i}", is_open=False))
            parent._lazy_populated = False

        return root

    def on_expand(self, tv, node):
        """Lazy load the children, triggering the jump."""
        if getattr(node, "_lazy_populated", False):
            return

        node._lazy_populated = True

        # Simulate expensive lazy population: add 60 child rows
        # This alone causes the ScrollView to jump because
        # the content height changes dramatically.
        for j in range(60):
            self.tv.add_node(TreeViewLabel(text=f"  Child {j}"), node)

        # Demonstrate the observed Kivy behavior:
        # ScrollView recalculates scroll_y in the next frame
        # resulting in a visible jump/jitter.
        #
        # We attempt a naive "restore scroll", but even this fails
        # because the layout is in flux.
        #
        # The point is: the jump is caused by TreeView + ScrollView
        # reacting to a massive mid-frame height change.
        Clock.schedule_once(lambda _: self.debug_scroll(tv), 0)

    def debug_scroll(self, tv):
        # Debug print: shows that scroll_y is altered by ScrollView
        sv = tv.parent
        print("scroll_y after new children:", round(sv.scroll_y, 3))


if __name__ == "__main__":
    LazyDemo().run()
