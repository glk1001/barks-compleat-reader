from pathlib import Path

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.input import MotionEvent
from kivy.lang import Builder
from kivy.properties import ObjectProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.settings import SettingItem, SettingOptions
from kivy.uix.widget import Widget
from loguru import logger

KV_SETTINGS_OVERRIDE = """
<-SettingItem>:
    size_hint: .25, None
    height: labellayout.texture_size[1] + dp(10)
    content: content
    canvas:
        Color:
            rgba: 47 / 255., 167 / 255., 212 / 255., self.selected_alpha
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
            size_hint_x: .55
            id: labellayout
            markup: True
            text:
                u'{0}\\n[size=13sp][color=999999]{1}[/color][/size]'\
                .format(root.title or '', root.desc or '')
            font_size: '15sp'
            text_size: self.width - 32, None

        BoxLayout:
            id: content
            size_hint_x: .45

<SettingString>:
    Label:
        text: root.value or ''
        pos: root.pos
        font_size: '15sp'

<SettingBoolean>:
    Switch:
        text: 'Boolean'
        pos: root.pos
        active: bool(root.values.index(root.value)) if root.value in root.values else False
        on_active: root.value = root.values[int(args[1])]

<SettingLongPath>:
    Label:
        text: root.value or ''
        font_size: '13sp'
        halign: 'left'
        valign: 'middle'
        shorten: True
        shorten_from: 'center'
        text_size: self.width, None

# Custom selection color for file entries
<FileListEntry>:
    canvas.before:
        Color:
            rgba: (0.2, 0.4, 0.7, 1) if self.is_selected else (0.18, 0.18, 0.18, 1)
        Rectangle:
            pos: self.pos
            size: self.size

<SettingLongPathPopup>:
    title: "Select Directory"
    title_align: "center"
    auto_dismiss: False
    size_hint: 0.8, 0.8
    separator_color: 0.3, 0.5, 0.8, 1
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
                foreground_color: 1, 1, 0, 1
                cursor_color: 0.3, 0.6, 0.9, 1

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
                background_color: 0.3, 0.6, 0.9, 1
                color: 1, 1, 1, 1

            Button:
                text: 'Cancel'
                on_release: root.dismiss()
                background_color: 0.7, 0.3, 0.3, 1
                color: 1, 1, 1, 1
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
        return result

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


# Register the custom widget before loading KV.
Factory.register("CustomFileChooserListView", cls=CustomFileChooserListView)
Builder.load_string(KV_SETTINGS_OVERRIDE)


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

    # noinspection LongLine
    def on_value(self, _instance, _value) -> None:  # ty:ignore[invalid-method-override]  # noqa: ANN001
        self._update_value_display()
