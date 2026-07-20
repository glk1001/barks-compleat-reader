from pathlib import Path

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.input import MotionEvent
from kivy.lang import Builder
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.settings import SettingItem, SettingOptions
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader.core.reader_palette import Color, theme

from .alt_escape_capture_popup import AltEscapeCapturePopup, keycode_to_name
from .reader_keyboard_nav import set_alt_escape_key


def _rgba(color: Color, alpha: float | None = None) -> str:
    """Return an ``r, g, b, a`` KV literal for ``color`` (optionally forcing alpha)."""
    r, g, b = color[:3]
    a = alpha if alpha is not None else (color[3] if len(color) > 3 else 1.0)  # noqa: PLR2004
    return f"{r}, {g}, {b}, {a}"


# Color tokens are substituted from the active theme in ``install_settings_theme_kv``
# (called after ``set_active_theme``), so the settings panel selection bar, file
# chooser, and popup buttons speak the same palette as the rest of the app rather
# than the old fixed programmer-blue.
KV_SETTINGS_OVERRIDE = """
<-SettingItem>:
    # Non-folder rows stay compact/left (Option B) but wider than Kivy's default
    # .25 so the label column has real room. Folder (long-path) rows override
    # size_hint_x to 1 below to break out to full width.
    size_hint: .62, None
    height: labellayout.texture_size[1] + dp(10)
    content: content
    canvas:
        Color:
            rgba: __SEL_RGB__, self.selected_alpha
        Rectangle:
            pos: self.x, self.y + 1
            size: self.size
        Color:
            rgb: .2, .2, .2
        Rectangle:
            pos: self.x, self.y - 2
            size: self.width, 1

    BoxLayout:
        pos: root.pos

        Label:
            size_hint_x: .6
            id: labellayout
            markup: True
            text:
                u'{0}\\n[size=13sp][color=999999]{1}[/color][/size]'\
                .format(root.title or '', root.desc or '')
            font_size: '15sp'
            text_size: self.width - 32, None

        BoxLayout:
            id: content
            size_hint_x: .4

# On-brand section heading: an uppercase "eyebrow" in the theme heading color
# with a hairline underline, replacing Kivy's flat grey label with a fill box.
<SettingTitle>:
    text: (self.title or '').upper()
    text_size: self.width - dp(28), None
    size_hint_y: None
    height: max(dp(36), self.texture_size[1] + dp(26))
    color: __HEADING_RGBA__
    bold: True
    font_size: '13sp'
    halign: 'left'
    valign: 'middle'
    canvas.after:
        Color:
            rgba: __HEADING_RULE_RGBA__
        Rectangle:
            pos: self.x + dp(14), self.y + dp(1)
            size: self.width - dp(28), dp(1.5)

<SettingString>:
    Label:
        text: root.value or ''
        pos: root.pos
        font_size: '15sp'

<SettingBoolean>:
    # Flexible spacers either side centre the fixed-size switch in the value
    # column, matching the centred value labels on the other setting types.
    Widget:
    ThemedSwitch:
        active: bool(root.values.index(root.value)) if root.value in root.values else False
        on_active: root.value = root.values[int(self.active)]
    Widget:

# On-brand toggle replacing Kivy's blue/grey atlas Switch: a pill track in the
# theme accent when on, warm grey when off, with a warm-white knob.
<ThemedSwitch>:
    size_hint: None, None
    size: dp(48), dp(26)
    pos_hint: {'center_y': 0.5}
    on_release: self.active = not self.active
    knob_x: (self.x + dp(3)) if not self.active else (self.right - self.height + dp(3))
    canvas:
        Color:
            rgba: (__SWITCH_ON_RGBA__) if self.active else (0.30, 0.27, 0.24, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.height / 2.0]
        Color:
            rgba: 0.96, 0.94, 0.88, 1
        Ellipse:
            size: self.height - dp(6), self.height - dp(6)
            pos: self.knob_x, self.y + dp(3)

<SettingLongPath>:
    # Folder paths break out of the compact non-folder width to full width.
    size_hint_x: 1
    Label:
        text: root.value or ''
        font_size: '13sp'
        halign: 'left'
        valign: 'middle'
        shorten: True
        shorten_from: 'center'
        text_size: self.width, None

<SettingAltEscapeKey>:
    Label:
        text: root.display_text
        font_size: '15sp'
        halign: 'center'
        valign: 'middle'
        text_size: self.width, None

# Custom selection color for file entries
<FileListEntry>:
    canvas.before:
        Color:
            rgba: (__SEL_RGBA__) if self.is_selected else (0.18, 0.18, 0.18, 1)
        Rectangle:
            pos: self.pos
            size: self.size

<SettingLongPathPopup>:
    title: "Select Directory"
    title_align: "center"
    auto_dismiss: False
    size_hint: 0.8, 0.8
    separator_color: __SEL_RGBA__
    title_color: 1, 1, 1, 1

    BoxLayout:
        orientation: 'vertical'
        spacing: dp(5)
        padding: dp(10)
        #canvas.before:
        #    Color:
        #        rgba: 0.12, 0.12, 0.12, 1
        #    Rectangle:
        #        pos: self.pos
        #        size: self.size

        # Top row for displaying/editing the current path
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: [dp(10), dp(10), dp(10), dp(10)]
            spacing: dp(10)

            Label:
                text: 'Selected:'
                size_hint_x: None
                width: dp(50)
                bold: False
                color: 1, 1, 1, 1

            TextInput:
                id: path_input
                text: file_chooser.selection[0] if file_chooser.selection else ""
                multiline: False
                font_size: '15sp'
                hint_text: 'Type or select a path'
                padding_y: [self.height / 2.0 - (self.line_height / 2.0) * len(self._lines), 0]
                on_text_validate: root.select_path(self.text)
                background_color: 0.2, 0.2, 0.2, 1
                foreground_color: __TEXT_TITLE_RGBA__
                cursor_color: __FOCUS_RGBA__

        # The FileChooser takes up the main space
        CustomFileChooserListView:
            id: file_chooser
            dirselect: True
            multiselect: False
            on_selection: root.on_file_selection(self, self.selection)

        # The bottom row for action buttons
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(10)

            Button:
                text: 'Select'
                bold: True
                on_release: root.select_path(path_input.text)
                background_color: __SEL_RGBA__
                color: 1, 1, 1, 1

            Button:
                text: 'Cancel'
                on_release: root.dismiss()
                background_color: __DANGER_RGBA__
                color: 1, 1, 1, 1

# Corner close affordance for the (menu-less) settings panel: the app's own
# close glyph, theme-tinted, on a warm near-black rounded chip. Mouse users get
# a visible Close; keyboard/remote still closes with Escape.
<SettingsCloseButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: 0.12, 0.10, 0.08, 0.82
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
    Image:
        source: root.icon_source
        color: __ICON_TINT_RGBA__
        fit_mode: 'contain'
        mipmap: True
        opacity: 0.6 if root.state == 'down' else 1.0
        pos: root.x + dp(9), root.y + dp(9)
        size: root.width - dp(18), root.height - dp(18)
"""


class CustomFileChooserListView(FileChooserListView):
    """Custom FileChooser that doesn't open directories on single click."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._allow_path_change = True
        self._real_path = self.path
        # Bind to selection changes to update visual state.
        self.bind(selection=self._on_selection_changed)

    def _on_selection_changed(self, _instance, value: list[str]) -> None:  # noqa: ANN001
        """Update visual state when selection changes."""
        # Update the is_selected property on all file entries
        # This forces the visual update without rescanning.
        for entry in self._items:
            if hasattr(entry, "path"):
                entry.is_selected = entry.path in value

    def on_path(self, _instance, value: str) -> None:  # noqa: ANN001
        """Intercept and block unauthorized path changes."""
        if not self._allow_path_change:
            # Revert the path change
            # Use the parent class property setter to avoid recursion
            FileChooserListView.path.fset(self, self._real_path)
            return

        # Allowed change, update our tracking.
        self._real_path = value

    def on_touch_down(self, touch: MotionEvent) -> bool:
        """Block path changes during touch handling."""
        self._allow_path_change = False
        result = super().on_touch_down(touch)
        self._allow_path_change = True
        return bool(result)

    def set_path(self, new_path: str) -> None:
        """Explicitly allow setting path programmatically."""
        self._allow_path_change = True
        self.path = new_path
        self._real_path = new_path

    def set_initial_selection(self, selection: list[str]) -> None:
        """Set the initial selection with visual refresh."""
        self.selection = selection
        # Force a full visual refresh for initial selection.
        self._update_files()


class SettingsCloseButton(Button):
    """Corner close affordance for the menu-less settings panel (styled in KV)."""

    icon_source = StringProperty("")


class ThemedSwitch(ButtonBehavior, Widget):
    """On-brand on/off toggle used by SettingBoolean (styled in KV).

    Replaces Kivy's default Switch, whose blue/grey look is baked into an image
    atlas and cannot be themed by tinting.
    """

    active = BooleanProperty(defaultvalue=False)
    knob_x = NumericProperty(0.0)


# Register the custom widgets before loading KV.
Factory.register("CustomFileChooserListView", cls=CustomFileChooserListView)
Factory.register("SettingsCloseButton", cls=SettingsCloseButton)
Factory.register("ThemedSwitch", cls=ThemedSwitch)

_settings_kv_installed = False


def _themed_settings_kv() -> str:
    """Return the settings KV with color tokens filled in from the active theme."""
    t = theme()
    sel = t.accent_selection
    sel_rgb = f"{sel[0]}, {sel[1]}, {sel[2]}"
    return (
        KV_SETTINGS_OVERRIDE.replace("__SEL_RGBA__", _rgba(sel, alpha=1.0))
        .replace("__SEL_RGB__", sel_rgb)
        .replace("__TEXT_TITLE_RGBA__", _rgba(t.text_title, alpha=1.0))
        .replace("__FOCUS_RGBA__", _rgba(t.focus_ring, alpha=1.0))
        .replace("__DANGER_RGBA__", _rgba(t.danger, alpha=1.0))
        .replace("__ICON_TINT_RGBA__", _rgba(t.icon_tint, alpha=1.0))
        .replace("__HEADING_RGBA__", _rgba(t.app_title, alpha=1.0))
        .replace("__HEADING_RULE_RGBA__", _rgba(t.app_title, alpha=0.4))
        .replace("__SWITCH_ON_RGBA__", _rgba(t.accent_selection, alpha=1.0))
    )


def install_settings_theme_kv() -> None:
    """Load the settings-panel KV, themed from the active palette.

    Must be called after ``set_active_theme`` and before the settings panel is
    built. Idempotent: repeated calls are no-ops.
    """
    global _settings_kv_installed  # noqa: PLW0603
    if _settings_kv_installed:
        return
    Builder.load_string(_themed_settings_kv())
    _settings_kv_installed = True


class SettingLongPathPopup(Popup):
    """A custom popup for directory selection."""

    setting_widget = ObjectProperty(None)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._updating = False  # Flag to prevent infinite loops
        self._update_event = None  # Store the scheduled event

    def select_path(self, path: str) -> None:
        """Call the 'Select' button when pressed."""
        if self.setting_widget and path:
            Clock.schedule_once(lambda _dt: self.setting_widget.update_setting_value(path.strip()))
        self.dismiss()

    def update_file_chooser_path(self, text: str) -> None:
        """Update the FileChooser when text is manually edited."""
        if self._updating:
            return

        # Cancel previous scheduled update.
        if self._update_event:
            self._update_event.cancel()

        def do_update(_dt: float) -> None:
            # noinspection PyBroadException
            try:
                self._updating = True
                path = Path(text).expanduser()
                if path.is_dir():
                    self.ids.file_chooser.set_path(str(path))
                    self.ids.file_chooser.selection = [str(path)]
                elif path.parent.is_dir():
                    # If the typed path doesn't exist but parent does, navigate to parent.
                    self.ids.file_chooser.set_path(str(path.parent))
                    self.ids.file_chooser.selection = [str(path)]
            except Exception:  # noqa: BLE001
                # Invalid path, just ignore.
                logger.info(f'Invalid path in long path file chooser: "{text}"')
            finally:
                self._updating = False

        self._update_event = Clock.schedule_once(do_update, 0.5)

    def on_file_selection(self, _instance, value: list[str]) -> None:  # noqa: ANN001
        """Handle file chooser selection changes."""
        # Cancel any pending path updates from typing.
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None

        # Set the updating flag to prevent the text change from triggering path updates.
        self._updating = True

        if value:
            selected = value[0]
            # If "../" was selected, use the current path instead.
            if selected.endswith(("../", "/..")):
                self.ids.path_input.text = self.ids.file_chooser.path
            else:
                self.ids.path_input.text = selected

        # Reset cursor to the beginning to show the start of the path.
        self.ids.path_input.cursor = (0, 0)

        # Clear the flag after a brief delay to allow manual typing again.
        Clock.schedule_once(lambda _dt: setattr(self, "_updating", False), 0.6)


class SettingLongPath(SettingItem):
    """Custom widget for long paths that are shortened in the middle to prevent truncation."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.bind(on_release=self._create_popup)

    def update_setting_value(self, new_path: str) -> None:
        """Update the setting with a new path value."""
        self.value = new_path

    def _create_popup(self, _instance: Widget) -> None:
        """Create and open the directory selection popup."""
        selected_dir = Path(self.value)
        setting_parent_dir = (
            selected_dir.parent
            if self.value and selected_dir.parent.is_dir()
            else Path("~").expanduser()
        )
        setting_dir = str(selected_dir)

        popup = SettingLongPathPopup(title=self.title, title_size="18sp", setting_widget=self)

        popup.ids.file_chooser.path = str(setting_parent_dir)
        popup.ids.path_input.text = setting_dir

        # Bind the text input to update file chooser.
        popup.ids.path_input.bind(
            text=lambda _instance, value: popup.update_file_chooser_path(value)
        )

        def set_initial_selection(_dt: float) -> None:
            """Set the initial selection after files are loaded."""
            fc = popup.ids.file_chooser

            # Look for the matching directory in the files list.
            for file_path in fc.files:
                if Path(file_path).resolve() == Path(setting_dir).resolve():
                    fc.set_initial_selection([file_path])
                    return

        popup.open()

        # Set selection after a short delay to ensure files are loaded.
        Clock.schedule_once(set_initial_selection, 0.2)


class SettingOptionsWithValue(SettingOptions):
    """Override class to fix Kivy SettingOptions not displaying value in settings panel."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        Clock.schedule_once(self._delayed_update, 0.1)

    def _delayed_update(self, _dt: float) -> None:
        self._update_value_display()

    def _update_value_display(self) -> None:
        if not hasattr(self, "value") or not self.value:
            return

        value_text = str(self.value)

        # Navigate the structure.
        if hasattr(self, "children") and len(self.children) > 0:
            main_box = self.children[0]

            if hasattr(main_box, "children") and len(main_box.children) >= 2:  # noqa: PLR2004
                # Get the FIRST BoxLayout (index 0 in the list, which is the rightmost one).
                # This is the empty BoxLayout meant for the value display.
                content_box = main_box.children[0]

                # Make sure it's actually a BoxLayout.
                if type(content_box).__name__ == BoxLayout.__name__:
                    # Check for existing label.
                    value_label = None
                    for child in content_box.children:
                        if isinstance(child, Label):
                            value_label = child
                            break

                    if value_label is not None:
                        value_label.text = value_text
                    else:
                        # Create new label with proper styling - use size_hint_x=1 for full width.
                        value_label = Label(
                            text=value_text, size_hint=(1, 1), halign="center", valign="middle"
                        )
                        value_label.bind(size=value_label.setter("text_size"))
                        content_box.add_widget(value_label)

    def _create_popup(self, instance) -> None:  # noqa: ANN001
        super()._create_popup(instance)

    def _set_option(self, instance: Label) -> None:
        super()._set_option(instance)

        # Manually ensure it's saved to config.
        if hasattr(self, "panel") and self.panel:
            config = self.panel.config
            if config:
                config.set(self.section, self.key, self.value)
                config.write()

        Clock.schedule_once(lambda _dt: self._update_value_display(), 0.1)

    def on_value(self, _instance, _value) -> None:  # ty:ignore[invalid-method-override]  # noqa: ANN001
        self._update_value_display()


class SettingAltEscapeKey(SettingItem):
    """Settings widget that captures a key press to use as an alternate Escape."""

    display_text = StringProperty("<unset>")

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.bind(on_release=self._open_capture_popup)
        self._refresh_display_text()

    def _refresh_display_text(self) -> None:
        try:
            keycode = int(self.value) if self.value else 0
        except (TypeError, ValueError):
            keycode = 0
        self.display_text = keycode_to_name(keycode)

    def on_value(self, _instance, _value) -> None:  # ty:ignore[invalid-method-override]  # noqa: ANN001
        self._refresh_display_text()

    def _open_capture_popup(self, _instance: Widget) -> None:
        try:
            current = int(self.value) if self.value else 0
        except (TypeError, ValueError):
            current = 0

        popup = AltEscapeCapturePopup(
            current_keycode=current,
            on_capture=self._set_keycode,
            on_clear=lambda: self._set_keycode(0),
        )
        popup.open()

    def _set_keycode(self, keycode: int) -> None:
        self.value = str(int(keycode))

        # Manually ensure it's saved to config (Kivy SettingItem subclasses don't auto-persist).
        if hasattr(self, "panel") and self.panel:
            config = self.panel.config
            if config:
                config.set(self.section, self.key, self.value)
                config.write()

        set_alt_escape_key(int(keycode))
