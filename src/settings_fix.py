import os

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivy.uix.settings import SettingItem

LONG_PATH = "longpath"

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

    def select_path(self, path: str):
        """Called when the 'Select' button is pressed."""
        if self.setting_widget and path:
            Clock.schedule_once(lambda dt: self.setting_widget.update_setting_value(path))
        self.dismiss()


class SettingLongPath(SettingItem):
    """
    Custom setting widget for displaying long paths that are
    shortened in the middle to prevent truncation.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(on_release=self._create_popup)

    def update_setting_value(self, new_path: str):
        self.value = new_path

    def _create_popup(self, _instance):
        """Creates and opens the directory selection popup."""

        setting_parent_dir = (
            os.path.dirname(self.value)
            if self.value and os.path.isdir(os.path.dirname(self.value))
            else os.path.expanduser("~")
        )
        setting_dir = self.value

        popup = SettingLongPathPopup(title=self.title, setting_widget=self)

        popup.ids.file_chooser.path = setting_parent_dir
        popup.ids.file_chooser.selection = [setting_dir]
        popup.ids.current_selection.text = f'"{setting_dir}"'

        popup.open()
