#
# demo_tree_nojump_dropdown.py
#
# Demonstrates TreeView inside ScrollView with lazy-loading
# AND perfect “dropdown” expansion where the parent stays pinned.
#

import kivy
kivy.require("2.3.0")

from kivy.app import App
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock


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
        )
        tv.bind(minimum_height=tv.setter("height"))
        tv.bind(on_node_expand=self.on_expand)

        self.tv = tv
        sv.add_widget(tv)
        root.add_widget(sv)

        # Add a handful of parents
        for i in range(6):
            parent = tv.add_node(TreeViewLabel(text=f"Parent {i}", is_open=False))
            parent._lazy_loaded = False

        return root

    # ------------------------------------------------------------
    # Lazy-expand handler WITH DROPDOWN EFFECT
    # ------------------------------------------------------------
    def on_expand(self, tree, parent):

        # Get parent widget for coordinate math
        parent_widget = parent

        # Record parent's current Y pixel position
        old_win_y = parent_widget.to_window(parent_widget.x, parent_widget.y)[1]

        # Lazy load children once
        if not parent._lazy_loaded:
            parent._lazy_loaded = True

            for j in range(60):
                self.tv.add_node(TreeViewLabel(text=f"    Child {j}"), parent)

        # Now stabilize and apply dropdown pinning
        Clock.schedule_once(lambda dt: self._stabilize_and_repin(parent, old_win_y), 0)

    # ------------------------------------------------------------
    # Dropdown-effect repinning logic
    # ------------------------------------------------------------
    def _stabilize_and_repin(self, parent, old_win_y):

        checks = {"frames": 0, "last_h": -1, "stable": 0}
        max_frames = 200

        def _poll(dt):

            # Parent widget available?
            widget = parent
            if widget.parent is None:
                return _again()

            # Has ScrollView content height stopped changing?
            content = self.sv.children[0]
            height_now = content.height

            if abs(height_now - checks["last_h"]) < 1:
                checks["stable"] += 1
            else:
                checks["stable"] = 0

            checks["last_h"] = height_now

            # Need at least 2–3 stable frames
            if checks["stable"] < 2:
                return _again()

            # Layout stable: now compute new parent position
            new_win_y = widget.to_window(widget.x, widget.y)[1]
            dy = new_win_y - old_win_y

            # Adjust scroll_y to compensate
            sv = self.sv
            sv.scroll_y = max(0.0, min(1.0, sv.scroll_y + (dy / content.height)))

        def _again():
            checks["frames"] += 1
            if checks["frames"] < max_frames:
                Clock.schedule_once(_poll, 0)

        Clock.schedule_once(_poll, 0)


if __name__ == "__main__":
    NoJumpDemo().run()
