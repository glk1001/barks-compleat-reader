from pathlib import Path

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ObjectProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.settings import SettingItem, SettingOptions
from kivy.uix.widget import Widget

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

<SettingLongPathPopup>:
    title: "Select Directory"
    title_align: "center"
    auto_dismiss: False
    size_hint: 0.8, 0.8

    BoxLayout:
        orientation: 'vertical'
        spacing: dp(5)
        padding: dp(10)

        # Top row for displaying the current path
        BoxLayout:
            size_hint_y: None
            height: self.minimum_height
            padding: [dp(10), dp(10), dp(10), dp(10)]
            spacing: dp(5)
            Label:
                text: 'Current selection:'
                size_hint_x: None
                width: self.texture_size[0]
            Label:
                # This label displays the selection from the FileChooser below
                id: current_selection
                # Don't forget to strip the double quotes before calling 'root.select_path' below.
                text: f'"{file_chooser.selection[0] if file_chooser.selection else ""}"'
                color: (1, 1, 0, 1)
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.width, None
                shorten: True
                shorten_from: 'left'  # Shows the end of the path, which is usually more important

        # The FileChooser takes up the main space
        FileChooserListView:
            id: file_chooser
            dirselect: True
            multiselect: False

        # The bottom row for action buttons
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(10)

            Button:
                text: 'Select Current Directory'
                bold: True
                # The root here is the SettingLongPathPopup instance
                # Don't forget to strip the double quotes here!
                on_release: root.select_path(current_selection.text.strip('"'))

            Button:
                text: 'Cancel'
                on_release: root.dismiss()
"""

Builder.load_string(KV_SETTINGS_OVERRIDE)


class SettingLongPathPopup(Popup):
    """A custom popup for directory selection."""

    setting_widget = ObjectProperty(None)

    def select_path(self, path: str) -> None:
        """Call the 'Select' button when pressed."""
        if self.setting_widget and path:
            Clock.schedule_once(lambda _dt: self.setting_widget.update_setting_value(path))
        self.dismiss()


class SettingLongPath(SettingItem):
    """Custom widget for long paths that are shortened in the middle to prevent truncation."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.bind(on_release=self._create_popup)

    def update_setting_value(self, new_path: str) -> None:
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

        popup = SettingLongPathPopup(title=self.title, setting_widget=self)

        popup.ids.file_chooser.path = str(setting_parent_dir)
        popup.ids.file_chooser.selection = [setting_dir]
        popup.ids.current_selection.text = f'"{setting_dir}"'

        popup.open()


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

    def on_value(self, _instance, _value) -> None:  # noqa: ANN001
        self._update_value_display()
