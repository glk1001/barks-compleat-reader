"""The shared action-bar widget used by the main, comic, and document screens.

``action_bar.kv`` (loaded first by ``barks_reader_app``) holds the skeleton:
the app-icon container, the draggable title region, and the right-hand
buttons box behind a thin separator. Screens declare their own ``BarButton``
children under a ``ReaderActionBar:`` in their kv — the ids they write there
register on the *screen's* rule, so ``self.ids.fullscreen_button`` etc. keep
working unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout

from barks_reader.core.reader_consts_and_types import ACTION_BAR_TITLE_COLOR

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

ACTION_BAR_KV_FILE = Path(__file__).with_suffix(".kv")


class ReaderActionBar(FloatLayout):
    """One action-bar skeleton; consumers fill the buttons box declaratively.

    Uses the canonical Kivy compound-widget redirect (as in Popup and
    TabbedPanel): while the class rule is being applied ``button_container``
    is still None (kv sets root properties after creating rule children), so
    skeleton children land on the FloatLayout itself; children declared by a
    consumer's kv arrive afterwards and are redirected into the right-hand
    buttons box.
    """

    icon_source = StringProperty("")
    icon_clickable = BooleanProperty(defaultvalue=False)
    title_text = StringProperty("")
    title_color = ColorProperty(ACTION_BAR_TITLE_COLOR)
    # Assigned by the kv rule; kv applies root properties only after creating
    # the rule's children, so this flips add_widget into redirect mode exactly
    # when the skeleton is complete.
    button_container = ObjectProperty(None)
    # The draggable title region, for Window.set_custom_titlebar.
    drag_region = ObjectProperty(None)
    # The transparent button over the app icon, for focus navigation.
    icon_hitbox = ObjectProperty(None)

    __events__ = ("on_icon_release",)

    def add_widget(self, widget: Widget, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Add skeleton children to self; consumer children to the buttons box."""
        if self.button_container is None:
            super().add_widget(widget, *args, **kwargs)
        else:
            self.button_container.add_widget(widget, *args, **kwargs)

    def on_icon_release(self) -> None:
        """Handle a click on the app icon — a no-op default; consumers bind in kv."""
