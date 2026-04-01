"""Kivy bug workaround patches.

Kivy 2.3.1 bug: several methods call canvas._remove_group() but the
Canvas Cython extension only exposes the public remove_group().
"""


# TODO: Remove when Kivy fixes canvas._remove_group (broken in Kivy 2.3.1).
def apply_text_input_remove_group_patch() -> None:
    """Patch TextInput._update_graphics_selection to handle missing _remove_group.

    Idempotent: safe to call multiple times.
    """
    from kivy.uix.textinput import TextInput  # noqa: PLC0415

    if hasattr(TextInput, "_kivy_workaround_applied"):
        return

    _orig = TextInput._update_graphics_selection  # noqa: SLF001

    def _patched(self: TextInput) -> None:  # ty:ignore[invalid-type-form]
        try:
            _orig(self)
        except AttributeError as exc:
            if "_remove_group" in str(exc):
                self.canvas.remove_group("selection")
            else:
                raise

    TextInput._update_graphics_selection = _patched  # noqa: SLF001
    TextInput._kivy_workaround_applied = True  # noqa: SLF001
