#
# demo_lazy_tree_scroll_to_child.py
#
# Demonstrates TreeView inside ScrollView with:
#  - Lazy loading of children
#  - Attempt to scroll to the first child
#  - The ScrollView still jumps due to layout height changes
#

import kivy

kivy.require("2.3.0")

from kivy.app import App
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock


class LazyDemo(App):
    def build(self):
        root = BoxLayout(orientation="vertical")

        # ScrollView
        sv = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["bars", "content"],
            bar_width=12,
        )
        self.sv = sv

        # TreeView
        tv = TreeView(
            hide_root=True,
            size_hint_y=None,
        )
        tv.bind(minimum_height=tv.setter("height"))
        tv.bind(on_node_expand=self.on_expand)

        self.tv = tv
        sv.add_widget(tv)
        root.add_widget(sv)

        # Add some parents
        for i in range(5):
            parent = tv.add_node(TreeViewLabel(text=f"Parent {i}", is_open=False))
            parent._lazy_populated = False

        return root

    # ------------------------------------------------------------
    # Lazy-expand handler
    # ------------------------------------------------------------
    def on_expand(self, tv, node):
        if node._lazy_populated:
            # Normal scroll for non-lazy second expansions
            Clock.schedule_once(lambda dt: self.scroll_to_first_child(node), 0)
            return

        node._lazy_populated = True

        # Simulate big lazy load (60 child nodes)
        for j in range(60):
            self.tv.add_node(TreeViewLabel(text=f"   Child {j}"), node)

        # Attempt to scroll to the first child AFTER population
        Clock.schedule_once(lambda dt: self.scroll_to_first_child(node), 0)

        # Log the scroll position to demonstrate the glitch
        Clock.schedule_once(lambda dt: self.debug_scroll("AFTER EXPAND"), 0)

    # ------------------------------------------------------------
    # Scroll to first child
    # ------------------------------------------------------------
    def scroll_to_first_child(self, parent_node):
        if not parent_node.nodes:
            return

        first_child = parent_node.nodes[0]
        widget = first_child

        # widget is not fully laid out until next frame, so defer again
        Clock.schedule_once(lambda dt: self._scroll_when_ready(widget), 0)

    def _scroll_when_ready(self, widget):
        # Try to ensure it is visible
        try:
            self.sv.scroll_to(widget, padding=10)
        except Exception as e:
            print("scroll_to error:", e)

        self.debug_scroll("AFTER scroll_to")

    # ------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------
    def debug_scroll(self, label):
        print(f"{label}: scroll_y = {round(self.sv.scroll_y, 3)}")


if __name__ == "__main__":
    LazyDemo().run()
