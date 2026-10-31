# cspell:ignore hiberfil
import os
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.input import MotionEvent
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView, FileSystemLocal
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.settings import (
    ContentPanel,
    SettingItem,
    SettingNumeric,
    SettingOptions,
    Settings,
)
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    is_escape_key,
    set_alt_escape_key,
)
from barks_reader.core.popup_frame import FrameButton, PopupSize
from barks_reader.core.reader_palette import Color, theme

from .action_bar_helpers import ACTION_BAR_SIZE_Y
from .alt_escape_capture_popup import AltEscapeCapturePopup, keycode_to_name
from .popup_frame import BUTTON_BACKGROUND, PopupFrame
from .reader_keyboard_nav import update_focus_in_list


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
# The settings panel's title is not a row of the scrolled panel but a bar pinned
# above it (<PinnedTitleSettingsInterface>), so this fully replaces Kivy's default
# <SettingsPanel> rule (the ``-`` prefix discards it) to drop its title Label.
<-SettingsPanel>:
    spacing: 5
    padding: 5
    size_hint_y: None
    height: self.minimum_height

# The settings' title bar, pinned above the scroll pane so neither it nor the
# scrollbar moves into the other. It is the app action bar's height
# (__TITLE_BAR_H__ px, substituted from ACTION_BAR_SIZE_Y), so it lines up with
# the main action bar, and main_screen sits the close X on its mid-line.
<PinnedTitleSettingsInterface>:
    orientation: 'vertical'
    content: content
    drag_region: drag_region
    Label:
        id: title_bar
        size_hint_y: None
        text: root.title
        text_size: self.width - dp(32), None
        height: __TITLE_BAR_H__
        color: .9, .9, .9, 1
        bold: True
        canvas.after:
            Color:
                rgba: .2, .2, .2, 1
            Rectangle:
                size: self.width, 1
                pos: self.x, self.y
        # The strip the window drags by while the settings are up: the title bar
        # short of the close X that main_screen sits at its right end. A Label lays
        # its children out nowhere, so the strip follows the bar by hand.
        Widget:
            id: drag_region
            size_hint: None, None
            pos: title_bar.pos
            size: max(0, title_bar.width - __TITLE_BAR_H__ - dp(14)), title_bar.height
    ContentPanel:
        id: content

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

# The directory chooser's body, on the popup frame (ui.popup_frame): the path box
# over the list of folders. Its Select and Cancel are the frame's buttons.
<FolderChooserBody>:
    orientation: 'vertical'
    spacing: dp(5)

    # Top row for displaying/editing the current path
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: [dp(4), dp(10), dp(4), dp(10)]
        spacing: dp(10)

        Label:
            text: 'Selected:'
            size_hint_x: None
            width: dp(70)
            color: __TEXT_SECONDARY_RGBA__

        TextInput:
            id: path_input
            text: file_chooser.selection[0] if file_chooser.selection else ""
            multiline: False
            font_size: '15sp'
            hint_text: 'Type or select a path'
            padding: [6, self.height / 2.0 - (self.line_height / 2.0) * len(self._lines), 6, 0]
            on_text_validate: root.popup.select_path(self.text)
            background_color: 0.2, 0.2, 0.2, 1
            foreground_color: __TEXT_TITLE_RGBA__
            cursor_color: __FOCUS_RGBA__

    # The FileChooser takes up the main space
    CustomFileChooserListView:
        id: file_chooser
        dirselect: True
        multiselect: False
        on_selection: root.popup.on_file_selection(self, self.selection)

# Corner close affordance for the (menu-less) settings panel: the app's own
# close glyph, theme-tinted, with no background chip so it reads as the same
# bare X the main action bar shows. Its glyph geometry mirrors the action bar's
# <ChromeBarButton> icon (dp(4)/sp(8) inset) and main_screen sizes/positions the
# button onto the action-bar mid-line, so closing settings barely moves the X.
# Mouse users get a visible Close; keyboard/remote still closes with Escape.
<SettingsCloseButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    Image:
        source: root.icon_source
        color: __ICON_TINT_RGBA__
        fit_mode: 'contain'
        mipmap: True
        opacity: 0.6 if root.state == 'down' else 1.0
        pos: root.x + dp(4), root.y + dp(4)
        size: root.width - dp(8), root.height - sp(8)

# The settings panel's scroll pane (a ContentPanel, a ScrollView) wears the shared
# scroll-pane look. ContentPanel is Kivy's own class, so this mirrors
# barks_kivy_ui.scrolling rather than inheriting it; Kivy's default <ContentPanel>
# rule sets none of these, so this additive rule has no conflicts.
<ContentPanel>:
    scroll_type: ['bars', 'content']
    always_overscroll: False
    effect_cls: 'ScrollEffect'
    bar_width: dp(12)
    bar_color: __SCROLLBAR_RGBA__
    bar_inactive_color: __SCROLLBAR_INACTIVE_RGBA__
"""


class QuietFileSystem(FileSystemLocal):
    r"""Kivy's local file system, without its error for a file Windows keeps locked.

    On Windows, Kivy reads each listed file's attributes to tell whether it is hidden.
    For a file the system holds open (``pagefile.sys``, ``hiberfil.sys``) that fails,
    and Kivy logs the failure as an error, with its traceback, before taking the file
    as hidden. Browsing to the root of drive C: filled the log with them. Here such a
    file is hidden all the same, quietly.

    The attributes read are the entry's own, not its target's: Windows marks the junctions
    it keeps for old programs (``C:\Documents and Settings``) hidden, as Explorer shows
    them, while the folders they lead to are not, and it lets no one list them.
    """

    def is_hidden(self, fn: str) -> bool:
        """Return whether `fn` is hidden: a dot file, or on Windows marked hidden or locked."""
        if sys.platform == "win32":
            try:
                return bool(Path(fn).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
            except OSError:
                return True  # held by the system, so nothing the reader could use
        return bool(super().is_hidden(fn))


class CustomFileChooserListView(FileChooserListView):
    """Custom FileChooser that doesn't open directories on single click."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        kwargs.setdefault("file_system", QuietFileSystem())
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
            # Put the path back. Allowed for the assignment, or the on_path it
            # fires would block it in turn and recurse.
            self._allow_path_change = True
            try:
                self.path = self._real_path
            finally:
                self._allow_path_change = False
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


class PinnedTitleSettingsInterface(BoxLayout):
    """The settings' one panel, scrolling under a title bar that stays put (laid out in KV).

    Kivy's no-menu interface is the scroll pane itself, with the panel's title as its
    first row, so the title scrolled away and the scrollbar ran over it.
    """

    __events__ = ("on_close",)

    title = StringProperty("")
    content = ObjectProperty(None)  # the ContentPanel, as Kivy's menu interfaces name it
    # The title bar short of the close X: the OS window-drag region while the
    # settings are up (main_screen hands it over and back).
    drag_region = ObjectProperty(None)

    def add_panel(self, panel: Widget, name: str, uid: int) -> None:
        """Keep `panel`, showing it and its name in the title bar if it is the first.

        Only the first is ever shown; Kivy's own panel (``App.use_kivy_settings``)
        comes after the reader's, and is kept but never seen.
        """
        self.content.add_panel(panel, name, uid)
        if self.content.current_uid == uid:
            self.title = name

    def on_close(self, *_args: object) -> None:
        """Do nothing: the settings close from main_screen (the X or Escape), not from here."""


class PinnedTitleSettings(Settings):
    """Kivy's Settings with one panel, its title pinned above it (no menu, no Close button)."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.interface_cls = PinnedTitleSettingsInterface
        super().__init__(**kwargs)


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
Factory.register("ContentPanel", cls=ContentPanel)  # Kivy does not, and the KV builds one

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
        .replace("__TEXT_SECONDARY_RGBA__", _rgba(t.text_secondary, alpha=1.0))
        .replace("__FOCUS_RGBA__", _rgba(t.focus_ring, alpha=1.0))
        .replace("__DANGER_RGBA__", _rgba(t.danger, alpha=1.0))
        .replace("__ICON_TINT_RGBA__", _rgba(t.icon_tint, alpha=1.0))
        .replace("__HEADING_RGBA__", _rgba(t.app_title, alpha=1.0))
        .replace("__HEADING_RULE_RGBA__", _rgba(t.app_title, alpha=0.4))
        .replace("__SWITCH_ON_RGBA__", _rgba(t.accent_selection, alpha=1.0))
        .replace("__SCROLLBAR_RGBA__", _rgba(t.scrollbar))
        .replace("__SCROLLBAR_INACTIVE_RGBA__", _rgba(t.scrollbar_inactive))
        .replace("__TITLE_BAR_H__", str(ACTION_BAR_SIZE_Y))
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


class FolderChooserBody(BoxLayout):
    """The directory chooser's body: the path box over the folders (laid out in KV)."""

    popup = ObjectProperty(None)


class SettingLongPathPopup(PopupFrame):
    """The directory chooser, on the shared frame (``ui.popup_frame``).

    Its keys are the remote's: the arrows browse, Return keeps the box's path, and
    Escape is the frame's, pressing Cancel. While the box has the keyboard, every key
    but Escape is the box's.
    """

    setting_widget = ObjectProperty(None)

    def __init__(self, title: str, setting_widget: object = None) -> None:
        body = FolderChooserBody()
        super().__init__(
            title=title,
            body=body,
            size=PopupSize.LARGE,
            buttons=(
                # Select closes the popup itself, once the path is on its way back.
                FrameButton("Select", self._select_the_box_path, closes=False),
                FrameButton("Cancel", lambda: None),
            ),
        )
        body.popup = self
        # The body's kv ids, where the chooser's code and its tests reach them.
        self.ids.update(body.ids)
        self.setting_widget = setting_widget
        self._updating = False  # Flag to prevent infinite loops
        self._update_event = None  # Store the scheduled event
        self.key_handler = self._handle_key
        self.bind(on_open=self._log_opened)

    def _log_opened(self, *_args: object) -> None:
        # Logged once it is open, its keys taken before its fade-in by the frame.
        logger.debug(log_markers.FOLDER_CHOOSER_OPENED.format(title=self.title))

    def _select_the_box_path(self) -> None:
        self.select_path(self.ids.path_input.text)

    def _handle_key(self, key: int) -> bool:
        """Take the remote's browsing keys: the arrows, and Return to keep the box's path.

        Up/Down move the highlight through the listed entries (the box follows it),
        Right opens the highlighted folder and Left the parent one. What is not taken
        here (Escape, and every key while the box is typed in) is the frame's.
        """
        if is_escape_key(key) or self.ids.path_input.focus:
            return False
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self.select_path(self.ids.path_input.text)
        elif key in (KEY_UP, KEY_DOWN):
            self._move_highlight(-1 if key == KEY_UP else 1)
        elif key == KEY_RIGHT:
            self._open_highlighted()
        elif key == KEY_LEFT:
            self._open_folder(str(Path(self.ids.file_chooser.path).parent))
        else:
            return False
        return True

    def _move_highlight(self, delta: int) -> None:
        """Move the selection `delta` entries down the list, scrolling it into view."""
        chooser = self.ids.file_chooser
        entries = [entry for entry in chooser._items if getattr(entry, "path", None)]  # noqa: SLF001
        if not entries:
            return
        paths = [entry.path for entry in entries]
        current = chooser.selection[0] if chooser.selection else None
        idx = paths.index(current) + delta if current in paths else 0
        idx = max(0, min(len(entries) - 1, idx))
        chooser.selection = [paths[idx]]
        chooser.layout.ids.scrollview.scroll_to(entries[idx])
        logger.debug(log_markers.FOLDER_CHOOSER_AT.format(path=paths[idx]))

    def _open_highlighted(self) -> None:
        """Open the highlighted folder ('../' is the parent); a file stays highlighted."""
        chooser = self.ids.file_chooser
        if not chooser.selection:
            return
        target = chooser.selection[0].rstrip("/\\")
        if target.endswith(".."):
            self._open_folder(str(Path(chooser.path).parent))
        elif Path(target).is_dir():
            self._open_folder(target)

    def _open_folder(self, folder: str) -> None:
        """Show `folder`'s entries, nothing highlighted, and put it in the box.

        A folder the reader may not list stays shut, the chooser where it was: Kivy
        would show it empty and log the refusal as an error.
        """
        try:
            with os.scandir(folder):
                pass
        except OSError:
            logger.debug(log_markers.FOLDER_CHOOSER_NOT_LISTED.format(path=folder))
            return
        chooser = self.ids.file_chooser
        chooser.set_path(folder)
        chooser.selection = []
        self.ids.path_input.text = folder
        logger.debug(log_markers.FOLDER_CHOOSER_IN.format(path=folder))

    def select_path(self, path: str) -> None:
        """Call the 'Select' button when pressed."""
        logger.info(log_markers.FOLDER_CHOOSER_SELECTED.format(path=path.strip()))
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


def open_folder_chooser_popup(title: str, value: str, setting_widget: object) -> None:
    """Open the directory chooser on `value`, its parent folder listed.

    One function, so the popup gallery (`ui.popup_gallery`) opens the very popup a
    long-path setting does.

    Args:
        title: The popup's title: the setting's.
        value: The directory chosen so far.
        setting_widget: The setting the chosen directory goes back to
            (``update_setting_value``).

    """
    selected_dir = Path(value)
    setting_parent_dir = (
        selected_dir.parent if value and selected_dir.parent.is_dir() else Path("~").expanduser()
    )
    setting_dir = str(selected_dir)

    popup = SettingLongPathPopup(title=title, setting_widget=setting_widget)

    popup.ids.file_chooser.path = str(setting_parent_dir)
    popup.ids.path_input.text = setting_dir

    # Bind the text input to update file chooser.
    popup.ids.path_input.bind(text=lambda _instance, text: popup.update_file_chooser_path(text))

    def set_initial_selection(_dt: float) -> None:
        """Set the initial selection after files are loaded."""
        fc = popup.ids.file_chooser

        # Look for the matching directory in the files list.
        for file_path in fc.files:
            if Path(file_path).resolve() == Path(setting_dir).resolve():
                fc.set_initial_selection([file_path])
                return

    popup.bind(on_dismiss=lambda *_a: logger.debug(log_markers.FOLDER_CHOOSER_CLOSED))
    popup.open()

    # Set selection after a short delay to ensure files are loaded.
    Clock.schedule_once(set_initial_selection, 0.2)


class SettingLongPath(SettingItem):
    """Custom widget for long paths that are shortened in the middle to prevent truncation."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.bind(on_release=self._create_popup)

    def on_kv_post(self, base_widget) -> None:  # noqa: ANN001, ARG002
        """Hug the value to the title for this (only) long-path row.

        The shared ``<-SettingItem>`` rule gives every row a 60/40 title/value
        split, which for the short "Fantagraphics Directory" title leaves a wide
        gap before the value and squeezes the path into 40% (so it shortens).
        Here we shrink the title column to just fit its text/description and let
        the value ``content`` box (the only remaining size-hinted sibling) expand
        to fill the rest, so the path sits next to the title and stays readable.
        """
        # Every setting row has it: Kivy's <SettingItem> rule and the themed one above.
        label = self.ids.labellayout
        label.size_hint_x = None
        label.width = dp(310)

    def update_setting_value(self, new_path: str) -> None:
        """Update the setting with a new path value."""
        self.value = new_path

    def _create_popup(self, _instance: Widget) -> None:
        """Create and open the directory selection popup."""
        open_folder_chooser_popup(self.title, self.value, self)


# A choice setting's list and a number setting's entry box.
CHOICE_HEIGHT = dp(44)
CHOICE_SPACING = dp(6)
CHOICE_FONT_SIZE = sp(16)
NUMBER_FONT_SIZE = sp(22)
NUMBER_BOX_BACKGROUND = (0.0, 0.0, 0.0, 0.35)
_CHOICE_FOCUS_GROUP = "setting_choice_focus"


def _choice_button(option: str, *, current: bool) -> Button:
    """Return a choice's button: the current one marked, in the selection colour."""
    return Button(
        text=option,
        size_hint_y=None,
        height=CHOICE_HEIGHT,
        font_size=CHOICE_FONT_SIZE,
        bold=current,
        background_normal="",
        background_color=list(theme().accent_selection if current else BUTTON_BACKGROUND),
        color=list(theme().text_secondary),
    )


class SettingOptionsPopup(PopupFrame):
    """A choice setting's list, on the shared frame (``ui.popup_frame``).

    The choices are a column, the current one marked and focused. Up and Down move
    along it, stopping at its top; Down past the last choice reaches the frame's
    Cancel, and Up there comes back. Return picks the focused choice, a tap the one
    tapped; Escape cancels.
    """

    def __init__(
        self, title: str, options: Sequence[str], current: str, on_pick: Callable[[str], None]
    ) -> None:
        self.choices = [_choice_button(option, current=option == current) for option in options]
        column = BoxLayout(orientation="vertical", size_hint_y=None, spacing=CHOICE_SPACING)
        column.bind(minimum_height=column.setter("height"))
        for choice in self.choices:
            column.add_widget(choice)
        scroll = ScrollView(do_scroll_x=False)  # a list too long for the frame scrolls
        scroll.add_widget(column)
        super().__init__(
            title=title,
            body=scroll,
            size=PopupSize.MEDIUM,
            buttons=(FrameButton("Cancel", lambda: None),),
            first_focus=None,  # the list has the focus
        )
        self._options = list(options)
        self._on_pick = on_pick
        self._scroll = scroll
        self.choice_idx: int | None = (
            self._options.index(current) if current in self._options else (0 if options else None)
        )
        for option, choice in zip(self._options, self.choices, strict=True):
            choice.bind(on_release=lambda _btn, option=option: self._pick(option))
        self.key_handler = self._handle_key
        self.bind(on_pre_open=self._show_choice_focus)
        if self.choice_idx is None:  # nothing to choose: the focus is Cancel's
            self.focus_button(0)

    def _pick(self, option: str) -> None:
        self.dismiss()
        self._on_pick(option)

    def _show_choice_focus(self, *_args: object) -> None:
        if self.choice_idx is not None:
            update_focus_in_list(self.choices, self.choice_idx, _CHOICE_FOCUS_GROUP)

    def _focus_choice(self, idx: int | None) -> None:
        if idx == self.choice_idx:
            return  # at the list's top: Up stays, as the app's lists do
        self.choice_idx = idx
        if idx is None:
            update_focus_in_list(self.choices, -1, _CHOICE_FOCUS_GROUP)
            self.focus_button(0)
            return
        self.focus_button(None)
        self._show_choice_focus()
        self._scroll.scroll_to(self.choices[idx], animate=False)

    def _handle_key(self, key: int) -> bool:
        """Take the list's keys; Escape, and Return on Cancel, are the frame's."""
        last = len(self.choices) - 1
        if self.choice_idx is None:  # on Cancel, the bottom
            if key == KEY_UP and self.choices:
                self._focus_choice(last)
                return True
            return key == KEY_DOWN
        if key == KEY_UP:
            self._focus_choice(max(0, self.choice_idx - 1))
            return True
        if key == KEY_DOWN:
            self._focus_choice(None if self.choice_idx == last else self.choice_idx + 1)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._pick(self._options[self.choice_idx])
            return True
        return not is_escape_key(key)  # Left and Right have nowhere to go in a column


class SettingNumberPopup(PopupFrame):
    """A number setting's entry box, on the shared frame (``ui.popup_frame``).

    The box has the keyboard from the start: Return there takes the number, Escape
    cancels. Down leaves the box for the frame's OK and Cancel, and Up from them
    goes back to it.
    """

    def __init__(self, title: str, value: str, on_enter: Callable[[str], None]) -> None:
        box = TextInput(
            text=value,
            multiline=False,
            write_tab=False,
            input_filter="float" if "." in value else "int",
            font_size=NUMBER_FONT_SIZE,
            size_hint_y=None,
            height=NUMBER_FONT_SIZE * 2,
            padding=[dp(10), dp(8)],
            background_normal="",
            background_active="",
            background_color=list(NUMBER_BOX_BACKGROUND),
            foreground_color=list(theme().text_title),
            cursor_color=list(theme().focus_ring),
        )
        body = BoxLayout(orientation="vertical")
        body.add_widget(Widget())
        body.add_widget(box)
        body.add_widget(Widget())
        super().__init__(
            title=title,
            body=body,
            size=PopupSize.SMALL,
            buttons=(
                FrameButton("OK", lambda: on_enter(box.text)),
                FrameButton("Cancel", lambda: None),
            ),
            first_focus=None,  # the box has the keyboard
        )
        self.textinput = box
        self._on_enter = on_enter
        box.bind(on_text_validate=self._enter)
        self.key_handler = self._handle_key
        self.bind(on_pre_open=self._focus_box)

    def _focus_box(self, *_args: object) -> None:
        self.textinput.focus = True

    def _enter(self, *_args: object) -> None:
        self.dismiss()
        self._on_enter(self.textinput.text)

    def _handle_key(self, key: int) -> bool:
        """Move between the box and the row; a one-line box has no use for Up or Down."""
        if key == KEY_DOWN and self.textinput.focus:
            self.textinput.focus = False
            self.focus_button(0)
            return True
        if key == KEY_UP and not self.textinput.focus:
            self.focus_button(None)
            self._focus_box()
            return True
        return key in (KEY_UP, KEY_DOWN)


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

    def _create_popup(self, instance: Widget) -> None:  # noqa: ARG002
        """Open the choices on the shared frame, in the place of Kivy's popup."""
        self.popup = popup = SettingOptionsPopup(
            self.title, self.options, self.value, self._pick_option
        )
        popup.bind(
            on_open=lambda *_a: logger.debug(
                log_markers.SETTING_OPTIONS_OPENED.format(key=self.key, value=self.value)
            )
        )
        popup.open()

    def _pick_option(self, option: str) -> None:
        self.value = option
        logger.info(log_markers.SETTING_OPTION_SET.format(key=self.key, value=self.value))
        Clock.schedule_once(lambda _dt: self._update_value_display(), 0.1)

    def on_value(self, instance: SettingItem, value: str) -> None:
        # Kivy's handler is what saves the value and dispatches the panel's
        # on_config_change, which is how a changed setting reaches the app
        # (BarksReaderApp.on_config_change). Overridden without calling it, an
        # option was written to the config by hand and the app never heard of it
        # (the main screen layout, 2026-10-29).
        super().on_value(instance, value)
        self._update_value_display()


class SettingNumberEntry(SettingNumeric):
    """Kivy's number setting, its entry box on the shared frame (``ui.popup_frame``)."""

    def _create_popup(self, instance: Widget) -> None:  # noqa: ARG002
        """Open the entry box on the shared frame, in the place of Kivy's popup."""
        self.popup = popup = SettingNumberPopup(self.title, str(self.value), self._take_number)
        self.textinput = popup.textinput
        popup.bind(
            on_open=lambda *_a: logger.debug(
                log_markers.SETTING_NUMBER_OPENED.format(key=self.key, value=self.value)
            )
        )
        popup.open()

    def _take_number(self, text: str) -> None:
        """Take `text` as the value, a float if the value was one; leave it if not a number."""
        is_float = "." in str(self.value)
        try:
            self.value = str(float(text) if is_float else int(text))
        except ValueError:
            logger.info(log_markers.SETTING_NUMBER_REFUSED.format(key=self.key, text=text))


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
