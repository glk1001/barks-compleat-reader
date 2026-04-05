from kivy.config import Config

Config.set("kivy", "keyboard_mode", "dock")

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label


class DebugApp(App):
    def build(self):
        print(f"Window.allow_vkeyboard = {Window.allow_vkeyboard}")
        print(f"Window.docked_vkeyboard = {Window.docked_vkeyboard}")

        box = BoxLayout()
        box.add_widget(Label(text="Tap anywhere, then press Ctrl+C to exit"))

        original = Window.on_touch_down

        def debug_touch(touch):
            print(
                f"TOUCH: device={touch.device!r} profile={touch.profile!r}"
                f" type_id={touch.type_id!r} pos={touch.pos}"
            )
            return original(touch)

        Window.on_touch_down = debug_touch
        return box


DebugApp().run()
