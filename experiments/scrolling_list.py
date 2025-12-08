def main():
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    def change_color(label, old_color):
        label.color = old_color

    def print_it(instance, value):
        old_color = instance.color
        instance.color = (0.0, 1.0, 0.0, 1)
        Clock.schedule_once(lambda dt: change_color(instance, old_color), 5)
        print(f"*** Clicked on {instance}:{value}")

    class ScrollableLabelList(ScrollView):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.do_scroll_x = False
            self.do_scroll_y = True
            self.always_overscroll = False
            self.effect_cls = "ScrollEffect"

            self.bar_color = (0.8, 0.8, 0.8, 1)
            self.bar_inactive_color = (0.8, 0.8, 0.8, 0.8)
            self.bar_width = 5

            self.layout = GridLayout(
                cols=1, spacing=1, pos=(0, 0), size_hint_x=0.1, size_hint_y=None
            )
            self.add_widget(self.layout)
            self.layout.bind(minimum_height=self.layout.setter("height"))

        def add_item(self, text):
            label = Label(
                text=f"[ref={text}]{text}[/ref]",
                size_hint_y=None,
                height=20,
                markup=True,
                underline=True,
            )
            label.bind(on_ref_press=print_it)
            self.layout.add_widget(label)

    class MyApp(App):
        def build(self):
            self.title = "Scrollable Label List with Refs"

            label_list = ScrollableLabelList()
            for i in range(50):
                label_list.add_item(f"Label {i + 1}")

            Window.show()

            return label_list

    MyApp().run()


if __name__ == "__main__":
    main()
