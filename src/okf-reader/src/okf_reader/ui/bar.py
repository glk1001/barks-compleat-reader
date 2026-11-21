"""The viewer's top bar: its buttons, the page's action among them, and the keys on it.

A Python rendition of the Barks Reader's kv action-bar idiom. The viewer says what Home,
Back and the Contrast toggle do and where the keys go when they leave the bar; the bar
knows nothing else of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.actionbar import ActionButton
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.togglebutton import ToggleButton

from okf_reader.ui import trace

from .focus_ring import clear_focus_ring, draw_focus_ring
from .keynav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    NAV_NOOP_KEYS,
)
from .widgets import IconToggleButton, bar_separator, tint_bar_icon

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from kivy.uix.widget import Widget

    from okf_reader.core.actions import PageAction
    from okf_reader.core.top_bar import TopBarSpec


class TopBar:
    """The action-bar strip: app icon, markup heading, right-edge buttons."""

    def __init__(
        self,
        spec: TopBarSpec,
        icon_tint: tuple[float, float, float, float],
        *,
        on_home: Callable[[], None],
        on_back: Callable[[], None],
        on_contrast_state: Callable[[Widget, str], None],
        on_leave: Callable[[], None],
    ) -> None:
        """Build the bar as `spec` dresses it; `widget` is the strip to lay out.

        Args:
            spec: How the embedding app wants the bar dressed.
            icon_tint: The theme's tint for the icon buttons' glyphs.
            on_home: What a press on the bar's icon does.
            on_back: What the Back button does.
            on_contrast_state: Told the Contrast toggle's state whenever it changes.
            on_leave: Hands the keys back to wherever they were before the bar.

        """
        self._icon_tint = icon_tint
        self._on_home = on_home
        self._on_back = on_back
        self._on_contrast_state = on_contrast_state
        self._on_leave = on_leave
        self._page_action: PageAction | None = None
        self.focused: Button | None = None  # the button wearing the gold ring
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=round(dp(spec.height)),
            padding=(dp(2), 0, dp(5), 0),
            spacing=dp(5),
        )
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with bar.canvas.before:  # ty: ignore[missing-union-attribute]
            Color(rgba=spec.bg_color)
            bar_bg = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(
            pos=lambda _inst, pos: setattr(bar_bg, "pos", pos),
            size=lambda _inst, size: setattr(bar_bg, "size", size),
        )

        self.home_btn: Button | None = None  # the icon's hitbox, when there is an icon
        if spec.icon_path is not None:
            bar.add_widget(self._build_icon(spec.icon_path, spec.icon_width))

        # The heading takes all the stretch space, pinning the buttons right.
        # Kept as an attribute: it doubles as the window-drag region when the
        # app replaces the OS titlebar with this bar (see OKFApp.on_start) —
        # the Barks Reader's draggable_title_bar arrangement, where only the
        # title area drags and the icon/buttons stay clickable.
        self.drag_region = Label(
            text=spec.title_markup,
            color=spec.title_color,
            markup=True,
            halign="left",
            valign="middle",
        )
        self.drag_region.bind(size=lambda inst, size: inst.setter("text_size")(inst, size))
        bar.add_widget(self.drag_region)

        bar.add_widget(bar_separator(spec.separator_color))

        if spec.back_icon_path is not None:
            # ActionButton is the Barks bars' BarButton base: standalone it
            # renders as a dp(48) icon button on a flat action-item background.
            self.back_btn = ActionButton(icon=str(spec.back_icon_path), mipmap=True, disabled=True)
            tint_bar_icon(self.back_btn, self._icon_tint)
        else:
            self.back_btn = Button(text="< Back", size_hint_x=None, width=dp(90), disabled=True)
        self.back_btn.bind(on_release=lambda *_: self._on_back())
        bar.add_widget(self.back_btn)

        # Dials the section bands from their subtle default up to near-opaque
        # (BLOCK_BG_CONTRAST_ALPHA) when the background image fights the text.
        if spec.contrast_on_icon_path is None:
            self.contrast_btn = ToggleButton(text="Contrast", size_hint_x=None, width=dp(90))
        else:
            assert spec.contrast_off_icon_path is not None
            self.contrast_btn = IconToggleButton(
                str(spec.contrast_on_icon_path), str(spec.contrast_off_icon_path)
            )
            tint_bar_icon(self.contrast_btn, self._icon_tint)
        self.contrast_btn.bind(state=self._on_contrast_state)
        bar.add_widget(self.contrast_btn)

        # The page's contextual action (see PageActionProvider): an empty
        # fixed-width slot until a page offers one — _set_page_action fills it
        # with a text or icon button (the two render too differently to
        # restyle one persistent widget).
        self.action_btn: Button | None = None
        self._action_slot = AnchorLayout(size_hint_x=None, width=0)
        bar.add_widget(self._action_slot)

        # The exit control sits alone in the window corner (with the OS titlebar
        # replaced by this bar, it is the window's only close control), fenced
        # off by a separator so an overshoot on the working buttons can't kill
        # the app.
        bar.add_widget(bar_separator(spec.separator_color, spec.quit_fence_width))
        if spec.close_icon_path is not None:
            quit_btn = ActionButton(icon=str(spec.close_icon_path), mipmap=True)
            tint_bar_icon(quit_btn, self._icon_tint)
        else:
            quit_btn = Button(text="Quit", size_hint_x=None, width=dp(70))

        # The embedding app's leave-this-screen action, else stop the app (the
        # standalone case, where this bar carries the window's only close control).
        # pyrefly: ignore[missing-attribute]  # Quit is pressed only in a running app.
        on_close = spec.on_close or (lambda: App.get_running_app().stop())
        quit_btn.bind(on_release=lambda *_: on_close())
        bar.add_widget(quit_btn)
        self.quit_btn = quit_btn
        self.widget = bar

    def nav_buttons(self) -> list[Button]:
        """Return the bar's activatable buttons in visual order, skipping absent/disabled ones.

        Recomputed per key press: the page-action button comes and goes with the
        page, and Back's disabled state follows the history.
        """
        candidates = [
            self.home_btn,
            self.back_btn,
            self.contrast_btn,
            self.action_btn,
            self.quit_btn,
        ]
        return [btn for btn in candidates if btn is not None and not btn.disabled]

    def _build_icon(self, icon_path: Path, icon_width: int) -> RelativeLayout:
        """Build the bar's left-edge app icon: an image under a transparent hitbox.

        The main-screen pattern — pressing dims the image, releasing shows the
        bundle's home page.
        """
        icon_box = RelativeLayout(size_hint=(None, 1), width=dp(icon_width))
        icon = Image(
            source=str(icon_path),
            size_hint=(None, None),
            fit_mode="contain",
            mipmap=True,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        # Slightly smaller than its container, for padding (the kv idiom).
        icon_box.bind(
            size=lambda _inst, size: setattr(icon, "size", (size[0] - dp(8), size[1] - dp(8)))
        )
        hitbox = Button(background_color=(0, 0, 0, 0), size_hint=(1, 1))
        hitbox.bind(
            state=lambda _inst, state: setattr(icon, "opacity", 0.5 if state == "down" else 1.0)
        )
        hitbox.bind(on_release=lambda *_: self._on_home())
        icon_box.add_widget(icon)
        icon_box.add_widget(hitbox)
        self.home_btn = hitbox  # the bar's keyboard focus activates the home icon via this
        return icon_box

    def set_page_action(self, action: PageAction | None) -> None:
        """Show the contextual bar button for ``action``, or hide it for None."""
        if self.action_btn is not None and self.focused is self.action_btn:
            self.clear_focus()  # its ringed widget is being discarded with the slot
        self._page_action = action
        self._action_slot.clear_widgets()
        if action is None:
            self.action_btn = None
            self._action_slot.width = 0
            return
        if action.icon_path is not None:
            # The kv ActionButton style pins an icon button at dp(48) wide.
            self.action_btn = ActionButton(icon=str(action.icon_path), mipmap=True)
            tint_bar_icon(self.action_btn, self._icon_tint)
        else:
            self.action_btn = Button(text=action.label, size_hint_x=None, width=dp(120))
        self.action_btn.bind(on_release=lambda *_: self.run_page_action())
        self._action_slot.add_widget(self.action_btn)
        # Keep the slot tracking the button (the icon style computes its own width).
        self.action_btn.bind(width=self._action_slot.setter("width"))
        self._action_slot.width = self.action_btn.width

    def run_page_action(self) -> None:
        if self._page_action is not None:
            trace.page_action(self._page_action.label)
            self._page_action.run()

    def enter_focus(self) -> None:
        """Ring the button the keys start on: Back, or the first when Back is disabled.

        Back starts focused so the remote's back gesture stays two presses
        (Escape, Enter); when Back is disabled (the standalone reader at its
        history root) the focus starts on the bar's first button instead. The
        caller has checked the bar has a button to take the keys (`nav_buttons`).
        """
        buttons = self.nav_buttons()
        self.set_focus(self.back_btn if self.back_btn in buttons else buttons[0])

    def handle_key(self, key: int) -> bool:
        """Walk the top bar's buttons: Left/Right cycle, Enter activates, Down drops out.

        Escape also drops out, handled centrally in `_handle_escape_key`.
        Left/Right wrap, matching the comic reader's menu mode. Activation
        returns the focus to the region it came from *before* triggering, so a
        button that rebuilds the page (Back, the home icon) or closes the
        embedding screen (Quit) never runs with the bar still focused.
        """
        buttons = self.nav_buttons()
        if not buttons:  # every button vanished (can't normally happen) — drop out
            self._on_leave()
            return True
        focused = self.focused
        if key in (KEY_LEFT, KEY_RIGHT):
            if focused is not None and focused in buttons:
                idx = (buttons.index(focused) + (1 if key == KEY_RIGHT else -1)) % len(buttons)
            else:  # the ringed button was removed/disabled under us — re-seed
                idx = 0
            self.set_focus(buttons[idx])
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if focused is not None and focused in buttons:
                self._on_leave()
                focused.trigger_action(duration=0)
            return True
        if key == KEY_DOWN:
            self._on_leave()
            return True
        return key in NAV_NOOP_KEYS

    def set_focus(self, btn: Button) -> None:
        """Move the gold ring to top-bar button ``btn``."""
        if self.focused is not None:
            clear_focus_ring(self.focused)
        self.focused = btn
        draw_focus_ring(btn)

    def clear_focus(self) -> None:
        if self.focused is not None:
            clear_focus_ring(self.focused)
            self.focused = None
