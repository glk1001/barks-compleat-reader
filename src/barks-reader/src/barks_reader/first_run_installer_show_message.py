# ruff: noqa: PLC0415

from pathlib import Path
from typing import Any

from barks_reader.core.popup_frame import FrameButton
from barks_reader.core.reader_utils import (
    get_centred_position_on_primary_monitor,
    quote_and_join_with_and,
)
from barks_reader.ui.kivy_standalone_show_message import show_standalone_popup

DEFAULT_INSTALLER_POPUP_SIZE = (800, 1000)
# A path's box: a darker well in the frame's dark card.
PATH_BOX_BACKGROUND = (0.0, 0.0, 0.0, 0.35)


def show_installer_message(
    title: str,
    fanta_volumes_dir: Path | None,
    data_zips: list[Path],
    app_config_dir: Path,
    app_log_path: Path,
    size: tuple[int, int] = DEFAULT_INSTALLER_POPUP_SIZE,
    background_image_file: Path | None = None,
) -> None:
    x, y = get_centred_position_on_primary_monitor(*size)

    # Set the window pos and size now to avoid moving window flicker.
    from kivy import Config

    Config.set("graphics", "left", x)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "top", y)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "width", size[0])  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "height", size[1])  # ty:ignore[unresolved-attribute]

    show_standalone_popup(
        title,
        _get_installer_success_content(fanta_volumes_dir, data_zips, app_config_dir, app_log_path),
        fill_window=True,
        buttons=(FrameButton("Start Barks Reader", lambda: None),),  # closing it starts it
        background_image_file=background_image_file,
    )


def _get_installer_success_content(  # noqa: C901
    fanta_vol_dir: Path | None,
    dat_zips: list[Path],
    config_dir: Path,
    log_path: Path,
) -> Any:  # noqa: ANN401
    # Delay Kivy imports until instantiation
    from barks_kivy_ui.scrolling import ReaderScrollView
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_palette import theme

    banner_header_font_size = sp(19)
    section_header_font_size = sp(16)
    file_path_font_size = sp(13)
    warning_text_font_size = sp(14)
    info_text_font_size = sp(14)

    class _InstallerSuccessContent(BoxLayout):
        """The installer's report, on the frame's dark card; its Start button is the frame's."""

        def __init__(
            self,
            fanta_volumes_dir: Path | None,
            data_zips: list[Path],
            app_config_dir: Path,
            app_log_path: Path,
        ) -> None:
            super().__init__(orientation="vertical", padding=0, spacing=0)
            self.popup_ref = None

            if data_zips is None:
                data_zips = []

            # === SCROLL AREA =====================================================
            scroll_view = ReaderScrollView(size_hint=(1, 1), do_scroll_y=False)
            content_box = BoxLayout(
                orientation="vertical",
                padding=[dp(4), 0],
                spacing=10,
                size_hint_y=None,
            )
            content_box.bind(minimum_height=content_box.setter("height"))

            # === SUCCESS BANNER ==================================================
            banner = BoxLayout(size_hint_y=None, height=70, padding=10)
            with banner.canvas.before:  # ty:ignore[unresolved-attribute]
                Color(0.12, 0.6, 0.33, 1)
                banner.bg = RoundedRectangle(size=banner.size, pos=banner.pos, radius=[dp(12)])
            banner.bind(size=lambda _i, v: setattr(banner.bg, "size", v))
            banner.bind(pos=lambda _i, v: setattr(banner.bg, "pos", v))
            banner.add_widget(
                Label(
                    text="Installation Completed Successfully",
                    color=[1, 1, 1, 1],
                    font_size=banner_header_font_size,
                    bold=True,
                    halign="center",
                    valign="middle",
                )
            )
            content_box.add_widget(banner)

            # === Fantagraphics Library ==========================================
            self._add_section_header(content_box, "Fantagraphics Library Location")
            if fanta_volumes_dir:
                self._add_info_text(
                    content_box, "Your Fantagraphics Carl Barks Library was found at:"
                )
                self._add_paths_box(content_box, [fanta_volumes_dir])
            else:
                self._add_warning_text(
                    content_box, "Your Fantagraphics Carl Barks Library was NOT found."
                )
                self._add_info_text(
                    content_box,
                    "You'll need to configure the library location when the app starts.",
                )

            # === Config & Logs ===================================================
            self._add_section_header(content_box, "Configuration & Logs")
            if app_config_dir:
                self._add_info_text(content_box, "Default configuration files were written to:")
                self._add_paths_box(content_box, [app_config_dir])

            if app_log_path:
                self._add_info_text(content_box, "App logging will go to:")
                self._add_paths_box(content_box, [app_log_path])

            # === Next Steps ======================================================
            self._add_section_header(content_box, "Next Steps")
            self._add_info_text(
                content_box,
                "The main Barks Reader app will now start. Once you're happy "
                "the app is working properly, you can delete the installer data packs:",
            )
            if data_zips:
                self._add_paths_box(content_box, data_zips)

            # Spacer
            content_box.add_widget(Widget(size_hint_y=None, height=10))

            scroll_view.add_widget(content_box)
            self.add_widget(scroll_view)

        # === Helpers ============================================================
        @staticmethod
        def _add_section_header(parent: Widget, text: str) -> None:
            lbl = Label(
                text=text,
                font_size=section_header_font_size,
                bold=True,
                color=list(theme().text_title),
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
                font_size=info_text_font_size,
                color=list(theme().text_secondary),
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
                font_size=warning_text_font_size,
                color=[0.95, 0.55, 0.2, 1],
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
        def _add_paths_box(parent: Widget, paths: list[Path]) -> None:
            card = BoxLayout(size_hint_y=None, height=45, padding=[10, 6])
            with card.canvas.before:  # ty:ignore[unresolved-attribute]
                Color(*PATH_BOX_BACKGROUND)
                card.bg = RoundedRectangle(size=card.size, pos=card.pos, radius=[dp(5)])
            card.bind(size=lambda _i, v: setattr(card.bg, "size", v))
            card.bind(pos=lambda _i, v: setattr(card.bg, "pos", v))

            path_str = quote_and_join_with_and(paths)

            lbl = Label(
                text=path_str,
                font_name="RobotoMono-Regular",
                font_size=file_path_font_size,
                bold=True,
                color=list(theme().text_secondary),
                halign="center",
                valign="middle",
            )
            lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0] - 15, None)))
            card.add_widget(lbl)
            parent.add_widget(card)

    return _InstallerSuccessContent(fanta_vol_dir, dat_zips, config_dir, log_path)


# Example usage
if __name__ == "__main__":
    show_installer_message(
        "Installation Complete",
        fanta_volumes_dir=Path(
            "~/Documents/Fantagraphics Complete Carl Barks Disney Library"
        ).expanduser(),
        data_zips=[Path("barks-reader-data-1.barkspack"), Path("barks-reader-data-2.barkspack")],
        app_config_dir=Path("~/opt/barks-reader/barks-reader.ini").expanduser(),
        app_log_path=Path("~/opt/barks-reader/config/kivy/logs/barks-reader.log").expanduser(),
        background_image_file=Path(
            "~/opt/barks-reader/Reader Files/Various/success-background.png"
        ).expanduser(),
    )
