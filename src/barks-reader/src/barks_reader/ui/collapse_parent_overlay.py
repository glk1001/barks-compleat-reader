from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from loguru import logger

if TYPE_CHECKING:
    from kivy.uix.scrollview import ScrollView

    from .reader_ui_classes import ButtonTreeViewNode

COLLAPSE_PARENT_OVERLAY_KV_FILE = Path(__file__).with_suffix(".kv")

_OVERLAY_HEIGHT = dp(28)
_OVERLAY_MARGIN_TOP = dp(5)
_ICON_SIZE = dp(20)
_ICON_PADDING_X = dp(6)
_LABEL_FONT_SIZE = sp(14)


class CollapseParentOverlay(FloatLayout):
    """A floating bar that appears when an expanded parent node scrolls off-screen.

    Tapping the bar collapses the parent node and scrolls back to it.
    """

    parent_name = StringProperty("")
    is_visible = BooleanProperty(defaultvalue=False)
    on_collapse_request = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._tracked_node: ButtonTreeViewNode | None = None
        self._scroll_view: ScrollView | None = None
        self._bar_widget: _CollapseBar | None = None
        self._bar_built = False
        self._suppress_checks = False

    def setup(self, scroll_view: ScrollView) -> None:
        """Bind to the scroll view so we can monitor scroll position."""
        self._scroll_view = scroll_view
        scroll_view.bind(scroll_y=self._on_scroll_changed)

    def track_node(self, node: ButtonTreeViewNode) -> None:
        """Start tracking a newly expanded parent node.

        The overlay won't appear until the user scrolls past the node
        (detected via the scroll_y binding).
        """
        from .reader_ui_classes import ButtonTreeViewNode  # noqa: PLC0415

        if not isinstance(node, ButtonTreeViewNode):
            return
        if not self._bar_built:
            self._bar_built = True
            self._build_bar()
        self._tracked_node = node
        self.parent_name = node.get_name()
        self.is_visible = False
        # Suppress scroll-triggered visibility checks while the layout stabilizes
        # after node expansion.  Without this, intermediate scroll_y adjustments
        # from _pin_parent_position_while_populating can produce stale coordinates
        # that make a visible node look off-screen, briefly flashing the overlay.
        # Suppression is lifted by end_suppression(), called by TreeViewManager
        # when scroll stabilization completes.
        self._suppress_checks = True

    def clear_tracking(self) -> None:
        """Stop tracking and hide the overlay."""
        self._tracked_node = None
        self.parent_name = ""
        self.is_visible = False
        self._suppress_checks = False

    def recheck_visibility(self) -> None:
        """Re-evaluate whether the overlay should be shown.

        Called after external events (e.g. node collapsed via keyboard) that
        don't trigger a scroll change.
        """
        self._check_visibility()

    def end_suppression(self) -> None:
        """Re-enable scroll-triggered visibility checks after layout stabilization.

        Defers the actual visibility check to the next frame so that widget
        positions reflect the final scroll_y that stabilization just applied.
        """
        self._suppress_checks = False
        Clock.schedule_once(lambda _dt: self._check_visibility(), 0)

    def _on_scroll_changed(self, *_args: object) -> None:
        self._check_visibility()

    def _check_visibility(self) -> None:
        if self._suppress_checks:
            return

        if self._tracked_node is None or self._scroll_view is None:
            self.is_visible = False
            return

        if not self._tracked_node.is_open:
            self.clear_tracking()
            return

        # Check if the tracked node's top edge is above the scroll view's visible top.
        # Uses the same to_window pattern as TreeViewManager._pin_parent_position_while_populating.
        sv_top_win_y = self._scroll_view.to_window(0, self._scroll_view.top)[1]
        node_top_win_y = self._tracked_node.to_window(0, self._tracked_node.top)[1]
        self.is_visible = node_top_win_y > sv_top_win_y

    def _on_bar_pressed(self) -> None:
        if self._tracked_node is None:
            return
        logger.info(f"Collapse overlay tapped: collapsing '{self._tracked_node.get_name()}'.")
        node = self._tracked_node
        self.clear_tracking()
        if self.on_collapse_request:
            self.on_collapse_request(node)

    def _build_bar(self) -> None:
        bar = _CollapseBar(overlay=self)
        self._bar_widget = bar

        sys_paths = App.get_running_app().reader_settings.sys_file_paths
        bar.icon_source = str(sys_paths.get_barks_reader_collapse_icon_file())

        self.bind(pos=lambda *_a: self._update_bar_pos())
        self.bind(size=lambda *_a: self._update_bar_pos())
        self.bind(is_visible=lambda *_a: self._update_bar_visibility())

        self.add_widget(bar)
        self._update_bar_pos()
        self._update_bar_visibility()

    def _update_bar_pos(self) -> None:
        if self._bar_widget is None:
            return
        self._bar_widget.x = self.x
        self._bar_widget.width = self.width
        self._bar_widget.y = self.y + self.height - _OVERLAY_HEIGHT - _OVERLAY_MARGIN_TOP

    def _update_bar_visibility(self) -> None:
        if self._bar_widget is None:
            return
        self._bar_widget.opacity = 1.0 if self.is_visible else 0.0
        self._bar_widget.disabled = not self.is_visible


class _CollapseBar(RelativeLayout):
    """The visual bar widget: collapse icon + label.

    Uses RelativeLayout so children are positioned relative to the bar
    and touch coordinates are correctly transformed.
    """

    icon_source = StringProperty("")

    def __init__(self, overlay: CollapseParentOverlay, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._overlay = overlay
        self.size_hint = (None, None)
        self.height = _OVERLAY_HEIGHT

        self._build_contents()

    def on_touch_down(self, touch: object) -> bool:
        if self.disabled or self.opacity < 0.1:  # noqa: PLR2004
            return False
        if self.collide_point(*touch.pos):  # ty: ignore[unresolved-attribute]
            self._overlay._on_bar_pressed()  # noqa: SLF001
            return True
        return False

    def _build_contents(self) -> None:
        from kivy.factory import Factory  # noqa: PLC0415
        from kivy.uix.image import Image  # noqa: PLC0415

        # Background label fills the bar and provides the colored background.
        label = Factory.BgColorLabel(
            text="",
            markup=True,
            color=(1, 1, 1, 1),
            font_size=_LABEL_FONT_SIZE,
            bold=True,
            size_hint=(1, 1),
            background_color=(0.15, 0.15, 0.25, 0.85),
            halign="left",
            valign="middle",
        )
        # Offset text to the right of the icon.
        text_indent = _ICON_SIZE + (_ICON_PADDING_X // 2)
        label.bind(
            size=lambda inst, _s: setattr(inst, "text_size", (inst.width - text_indent, None)),
        )
        label.padding_x = text_indent

        self._overlay.bind(
            parent_name=lambda _inst, val: setattr(label, "text", f"[i]{val}[/i]"),
        )

        # Collapse icon on the left side.
        icon = Image(
            size_hint=(None, None),
            size=(_ICON_SIZE, _ICON_SIZE),
            fit_mode="contain",
            mipmap=True,
        )
        icon.x = _ICON_PADDING_X
        self.bind(icon_source=icon.setter("source"))
        self.bind(size=lambda *_a: setattr(icon, "center_y", self.height / 2))

        self.add_widget(label)
        self.add_widget(icon)
