# ruff: noqa: PLC0415

"""Standalone popup utilities for displaying messages when Kivy may or may not be running."""

from pathlib import Path
from typing import Any

from loguru import logger

_SAME_SIZE_CUTOFF_PX = 10


# --- Light divider line widget ---
def divider_line() -> Any:  # Widget  # noqa: ANN401
    from kivy.graphics import Color, Rectangle
    from kivy.uix.widget import Widget

    w = Widget(size_hint_y=None, height=1)
    with w.canvas.before:  # ty: ignore[possibly-missing-attribute]
        Color(0.5, 0.5, 0.5, 1)
        w.rect = Rectangle(size=w.size, pos=w.pos)
    w.bind(size=lambda inst, val: setattr(inst.rect, "size", val))
    w.bind(pos=lambda inst, val: setattr(inst.rect, "pos", val))

    return w


def show_standalone_popup(  # noqa: PLR0915
    title: str,
    content,  # noqa: ANN001
    size_hint: tuple[float, float] = (0.9, 0.9),
    timeout: float = 0,
    auto_dismiss: bool = False,
    add_close_button: bool = True,
    background_image_file: Path | None = None,
) -> None:
    """Show a popup even if no Kivy app or event loop is running."""
    from kivy.app import App
    from kivy.base import EventLoop, runTouchApp, stopTouchApp
    from kivy.clock import Clock
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.widget import Widget

    from barks_reader.comic_book_reader import get_image_stream

    app_already_running = (App.get_running_app() is not None) and (EventLoop.status == "started")

    def _show(*_) -> None:  # noqa: ANN002, PLR0915
        # --- Root layout ---
        root_box = BoxLayout(orientation="vertical", spacing=0)

        # --- Title bar (gradient + shadow) ---
        title_bar = BoxLayout(size_hint_y=None, height=56, padding=[12, 8], spacing=8)

        with title_bar.canvas.before:  # ty: ignore[possibly-missing-attribute]
            # Shadow under title bar.
            Color(0, 0, 0, 0.1)
            shadow_rect = Rectangle(pos=(title_bar.x, title_bar.y - 4), size=(title_bar.width, 6))

            # Gradient simulation: two stacked rectangles.
            Color(0.12, 0.28, 0.54, 1)  # top
            top_rect = Rectangle(pos=(title_bar.x, title_bar.y + 28), size=(title_bar.width, 28))
            Color(0.15, 0.32, 0.60, 1)  # bottom
            bottom_rect = Rectangle(pos=(title_bar.x, title_bar.y), size=(title_bar.width, 28))

        def update_title_bg(inst: Widget, _val) -> None:  # noqa: ANN001
            shadow_rect.pos = (inst.x, inst.y - 4)
            shadow_rect.size = (inst.width, 6)
            top_rect.pos = (inst.x, inst.y + 28)
            top_rect.size = (inst.width, 28)
            bottom_rect.pos = (inst.x, inst.y)
            bottom_rect.size = (inst.width, 28)

        title_bar.bind(pos=update_title_bg, size=update_title_bg)

        # --- Title label ---
        title_label = Label(
            text=title,
            color=[1, 1, 1, 1],
            font_size="18sp",
            bold=True,
            halign="left",
            valign="middle",
        )
        title_label.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        title_bar.add_widget(title_label)

        # --- Close button ---
        if add_close_button:
            close_button = Button(
                text="X",
                size_hint=(None, 1),
                width=44,
                background_normal="",
                background_color=[0.86, 0.2, 0.2, 0.5],
                color=[1, 1, 1, 1],
                font_size="16sp",
            )
            title_bar.add_widget(close_button)

        # --- Content wrapper with rounded white background + subtle shadow ---
        content_wrapper = BoxLayout(orientation="vertical", padding=[14, 12, 14, 12], spacing=10)

        # Store references for the update function
        bgnd_rect = None
        bgnd_texture_size = None

        with content_wrapper.canvas.before:  # ty: ignore[possibly-missing-attribute]
            # Drop shadow.
            Color(0, 0, 0, 0.05)
            shadow = Rectangle(
                pos=(content_wrapper.x + 2, content_wrapper.y - 2),
                size=(content_wrapper.width, content_wrapper.height),
            )

            # Background image (if provided)
            if background_image_file:
                # noinspection PyNoneFunctionAssignment
                bgnd_texture = get_image_stream(background_image_file)
                # noinspection PyUnresolvedReferences
                bgnd_texture_size = (
                    (bgnd_texture.width, bgnd_texture.height) if bgnd_texture else (1, 1)
                )

                Color(1, 1, 1, 0.4)
                bgnd_rect = RoundedRectangle(
                    pos=content_wrapper.pos,
                    size=content_wrapper.size,
                    texture=bgnd_texture,
                    radius=[12],
                )

            # White rounded background (semi-transparent) OVER the image
            Color(1, 1, 1, 0.4)
            wrapper_bg = RoundedRectangle(
                pos=content_wrapper.pos, size=content_wrapper.size, radius=[12]
            )

        def update_wrapper_bgnd(inst: Widget, _val) -> None:  # noqa: ANN001
            shadow.pos = (inst.x + 2, inst.y - 2)
            shadow.size = (inst.width, inst.height)
            wrapper_bg.pos = inst.pos
            wrapper_bg.size = inst.size

            if background_image_file and bgnd_rect and bgnd_texture_size:
                texture_ratio = (
                    bgnd_texture_size[0] / bgnd_texture_size[1] if bgnd_texture_size[1] > 0 else 1
                )

                bgnd_rect.pos, bgnd_rect.size = _get_background_image_pos_and_size(
                    (inst.x, inst.y),
                    inst.size,
                    texture_ratio,
                )

        # Place user content directly inside the wrapper.
        content_wrapper.add_widget(content)

        # --- Assemble root layout ---
        root_box.add_widget(title_bar)
        root_box.add_widget(content_wrapper)

        # --- Create popup ---
        popup = Popup(
            title="",  # hide native title
            content=root_box,
            size_hint=size_hint,
            auto_dismiss=auto_dismiss,
        )
        content.popup_ref = popup

        if add_close_button:
            # noinspection PyUnboundLocalVariable
            close_button.bind(on_press=lambda *_: popup.dismiss())

        popup.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        if timeout > 0:
            Clock.schedule_once(lambda _dt: popup.dismiss(), timeout)

        if not app_already_running:
            popup.bind(on_dismiss=lambda *_: stopTouchApp())

        def popup_is_open() -> None:
            if background_image_file and bgnd_rect and bgnd_texture_size:
                update_wrapper_bgnd(content, 1)

        popup.bind(on_open=lambda *_: popup_is_open())

        popup.open()

    try:
        if app_already_running:
            Clock.schedule_once(_show, 0)
        else:
            logger.warning("No Kivy app running, starting temporary UI loop for popup.")
            Clock.schedule_once(_show, 0)
            runTouchApp()
    except Exception as e:
        logger.critical(f"Failed to show standalone popup: {e}")
        raise


def _get_background_image_pos_and_size(
    container_pos: tuple[int, int],
    container_size: tuple[int, int],
    texture_ratio: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
    container_ratio = (container_size[0] / container_size[1]) if container_size[1] > 0 else 1
    max_width = container_size[0]
    max_height = container_size[1]

    # COVER mode
    if container_ratio < texture_ratio:
        bgnd_width = max_width
        bgnd_height = max_width / texture_ratio
    else:
        bgnd_height = max_height
        bgnd_width = max_height * texture_ratio

    if bgnd_width > max_width:
        bgnd_width = max_width
        bgnd_height = bgnd_width / texture_ratio
    elif bgnd_height > max_height:
        bgnd_height = max_width
        bgnd_width = bgnd_height * texture_ratio

    if (max_width - bgnd_width) < _SAME_SIZE_CUTOFF_PX:
        bgnd_width = max_width
    if (max_height - bgnd_height) < _SAME_SIZE_CUTOFF_PX:
        bgnd_height = max_height

    bgnd_x = container_pos[0] + ((container_size[0] - bgnd_width) / 2)
    bgnd_y = container_pos[1] + ((container_size[1] - bgnd_height) / 2)

    return (round(bgnd_x), round(bgnd_y)), (round(bgnd_width), round(bgnd_height))
