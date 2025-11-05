from barks_reader.kivy_standalone_show_message import show_standalone_popup
from kivy.graphics import Color, RoundedRectangle
from kivy.graphics.texture import Texture  # ty: ignore[unresolved-import]
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget


class _InstallerSuccessContent(BoxLayout):
    def __init__(  # noqa: PLR0915
        self,
        fanta_volumes_dir: str,
        data_zips: list[str],
        app_config_dir: str,
        app_log_path: str,
    ) -> None:
        super().__init__(orientation="vertical", padding=0, spacing=0)

        if data_zips is None:
            data_zips = []

        # === BACKGROUND ======================================================
        tex = Texture.create(size=(1, 64), colorfmt="rgba")
        grad = bytearray()
        for i in range(64):
            t = 250 - int(10 * i / 63)
            grad.extend([t, t, 255, 255])
        tex.blit_buffer(bytes(grad), colorfmt="rgba", bufferfmt="ubyte")

        with self.canvas.before:  # ty: ignore[possibly-missing-attribute]
            Color(0, 0, 0, 0.18)
            self._shadow = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)], texture=tex)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # === SCROLL AREA =====================================================
        scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content_box = BoxLayout(
            orientation="vertical", padding=[25, 20], spacing=10, size_hint_y=None
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        # === SUCCESS BANNER ==================================================
        banner = BoxLayout(size_hint_y=None, height=70, padding=10)
        with banner.canvas.before:  # ty: ignore[possibly-missing-attribute]
            Color(0.12, 0.6, 0.33, 1)
            banner.bg = RoundedRectangle(size=banner.size, pos=banner.pos, radius=[dp(8)])
        banner.bind(size=lambda _i, v: setattr(banner.bg, "size", v))
        banner.bind(pos=lambda _i, v: setattr(banner.bg, "pos", v))
        banner.add_widget(
            Label(
                text="✅  Installation Completed Successfully",
                color=[1, 1, 1, 1],
                font_size="18sp",
                bold=True,
                halign="center",
                valign="middle",
            )
        )
        content_box.add_widget(banner)

        # === Fantagraphics Library ==========================================
        self._add_section_header(content_box, "Fantagraphics Library Location")
        if fanta_volumes_dir:
            self._add_info_text(content_box, "The Fantagraphics Carl Barks Library was found at:")
            self._add_path_box(content_box, fanta_volumes_dir)
        else:
            self._add_warning_text(content_box, "⚠ The Library was NOT found.")
            self._add_info_text(
                content_box,
                "You'll need to configure the library location when the app starts.",
            )

        # === Next Steps ======================================================
        self._add_section_header(content_box, "Next Steps")
        self._add_info_text(
            content_box,
            "The main Barks Reader app will now start.\n"
            "Once you're happy with it, you can delete the installer zips:",
        )
        if data_zips:
            self._add_path_box(content_box, ", ".join(data_zips))

        # === Config & Logs ===================================================
        self._add_section_header(content_box, "Configuration & Logs")

        if app_config_dir:
            self._add_info_text(content_box, "Default config files written to:")
            self._add_path_box(content_box, app_config_dir)

        if app_log_path:
            self._add_info_text(content_box, "Logging will go to:")
            self._add_path_box(content_box, app_log_path)

        # Add a small spacer
        content_box.add_widget(Widget(size_hint_y=None, height=10))

        scroll_view.add_widget(content_box)
        self.add_widget(scroll_view)

        # === OK BUTTON =======================================================
        btn_layout = BoxLayout(size_hint_y=None, height=60, padding=[100, 5])
        btn_ok = Button(
            text="🚀  Start Barks Reader",
            font_size="16sp",
            bold=True,
            color=[1, 1, 1, 1],
            background_normal="",
            background_color=[0.2, 0.5, 0.9, 1],
        )
        btn_ok.bind(on_press=self._dismiss)
        btn_layout.add_widget(btn_ok)
        self.add_widget(btn_layout)

    # === Helpers ============================================================
    def _update_bg(self, *_args) -> None:  # noqa: ANN002
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._shadow.pos = (self.x + dp(5), self.y - dp(5))
        self._shadow.size = self.size

    @staticmethod
    def _add_section_header(parent: Widget, text: str) -> None:
        lbl = Label(
            text=text,
            font_size="15sp",
            bold=True,
            color=[0.1, 0.15, 0.25, 1],
            size_hint_y=None,
            height=28,
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        parent.add_widget(lbl)

    @staticmethod
    def _add_info_text(parent: Widget, text: str) -> None:
        lbl = Label(
            text=text,
            font_size="13sp",
            color=[0.25, 0.25, 0.35, 1],
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        lbl.bind(
            size=lambda i, v: (
                setattr(i, "text_size", (v[0], None)),
                i.texture_update(),
                setattr(i, "height", i.texture_size[1] + dp(4)),
            )
        )
        parent.add_widget(lbl)

    @staticmethod
    def _add_warning_text(parent: Widget, text: str) -> None:
        lbl = Label(
            text=text,
            font_size="13sp",
            color=[0.95, 0.45, 0.1, 1],
            bold=True,
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        lbl.bind(
            size=lambda i, v: (
                setattr(i, "text_size", (v[0], None)),
                i.texture_update(),
                setattr(i, "height", i.texture_size[1] + dp(4)),
            )
        )
        parent.add_widget(lbl)

    @staticmethod
    def _add_path_box(parent: Widget, path: str) -> None:
        card = BoxLayout(size_hint_y=None, height=45, padding=[10, 6])
        with card.canvas.before:  # ty: ignore[possibly-missing-attribute]
            Color(0.96, 0.97, 1, 1)
            card.bg = RoundedRectangle(size=card.size, pos=card.pos, radius=[dp(5)])
        card.bind(size=lambda _i, v: setattr(card.bg, "size", v))
        card.bind(pos=lambda _i, v: setattr(card.bg, "pos", v))

        lbl = Label(
            text=path,
            font_name="RobotoMono-Regular",
            font_size="11sp",
            color=[0.1, 0.2, 0.6, 1],
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0] - 15, None)))
        card.add_widget(lbl)
        parent.add_widget(card)

    def _dismiss(self, *_args) -> None:  # noqa: ANN002
        parent = self.parent
        while parent and not hasattr(parent, "dismiss"):
            parent = parent.parent
        if parent:
            parent.dismiss()


# Example usage
if __name__ == "__main__":
    show_standalone_popup(
        title="Installation Complete",
        content=_InstallerSuccessContent(
            fanta_volumes_dir="/home/greg/Documents/Fantagraphics",
            data_zips=["barks-reader-data-1.zip", "barks-reader-data-2.zip"],
            app_config_dir="/home/greg/.config/barks-reader/",
            app_log_path="/home/greg/.local/share/barks-reader/logs/",
        ),
        size=(800, 950),
    )
