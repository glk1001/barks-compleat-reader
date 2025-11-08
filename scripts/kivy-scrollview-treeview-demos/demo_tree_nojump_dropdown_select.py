#
# demo_tree_nojump_dropdown_select.py
#
# Demonstrates:
#   ✅ TreeView inside ScrollView
#   ✅ Lazy-loading children
#   ✅ No-jump dropdown expansion
#   ✅ Selecting nodes when clicked
#   ✅ on_press callback
#

import kivy
kivy.require("2.3.0")

from kivy.app import App
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock


class SelectableLabel(TreeViewLabel):
    """
    TreeViewLabel subclass that intercepts clicks:
    - selects itself
    - calls app.on_press(self)
    - expands parent nodes
    """

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        app = App.get_running_app()

        # Highlight the clicked node
        app.tv.select_node(self)

        # Dummy on_press callback
        app.on_press(self)

        # If this is a parent node, expand it
        if hasattr(self, "is_parent_node") and self.is_parent_node:
            app.tv.toggle_node(self)

        return True


class NoJumpDemo(App):

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
            indent_level=20,
        )
        tv.bind(minimum_height=tv.setter("height"))
        tv.bind(on_node_expand=self.on_expand)

        self.tv = tv
        sv.add_widget(tv)
        root.add_widget(sv)

        # Add parent nodes
        for i in range(6):
            lbl = SelectableLabel(text=f"Parent {i}", is_open=False)
            lbl.is_parent_node = True
            lbl._lazy_loaded = False
            tv.add_node(lbl)

        return root

    # ------------------------------------------------------------
    # Dummy on_press callback
    # ------------------------------------------------------------
    def on_press(self, node):
        print(f"[on_press] You clicked: {node.text}")

    # ------------------------------------------------------------
    # Lazy-expand handler WITH DROPDOWN EFFECT
    # ------------------------------------------------------------
    def on_expand(self, tree, parent):
        print(f"[on_expand] Expanding: {parent.text}")

        # Node widget
        parent_widget = parent

        # Record parent's Y pixel position
        old_win_y = parent_widget.to_window(parent_widget.x, parent_widget.y)[1]

        # Lazy load children once
        if not parent._lazy_loaded:
            parent._lazy_loaded = True

            for j in range(50):
                child = SelectableLabel(text=f"    Child {j}")
                child.is_parent_node = False
                self.tv.add_node(child, parent)

        # Apply dropdown repinning after layout stabilizes
        Clock.schedule_once(lambda dt: self._stabilize_and_repin(parent, old_win_y), 0)

    # ------------------------------------------------------------
    # Repin parent node visually so it stays in place
    # ------------------------------------------------------------
    def _stabilize_and_repin(self, parent, old_win_y):

        checks = {"frames": 0, "last_h": -1, "stable": 0}
        max_frames = 200

        def _poll(dt):

            widget = parent
            if widget.parent is None:
                return _again()

            # Detect layout stabilization
            content = self.sv.children[0]
            h_now = content.height

            if abs(h_now - checks["last_h"]) < 1:
                checks["stable"] += 1
            else:
                checks["stable"] = 0

            checks["last_h"] = h_now

            if checks["stable"] < 2:
                return _again()

            # Stable — compute new Y pos
            new_win_y = widget.to_window(widget.x, widget.y)[1]
            dy = new_win_y - old_win_y

            sv = self.sv
            sv.scroll_y = max(0.0, min(1.0, sv.scroll_y + (dy / content.height)))

        def _again():
            checks["frames"] += 1
            if checks["frames"] < max_frames:
                Clock.schedule_once(_poll, 0)

        Clock.schedule_once(_poll, 0)


if __name__ == "__main__":
    NoJumpDemo().run()
