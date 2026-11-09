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


# TODO: Remove when Kivy fixes canvas._remove_group (broken in Kivy 2.3.1).
def apply_swap_transition_remove_group_patch() -> None:
    """Patch SwapTransition.on_complete to handle missing _remove_group.

    Idempotent: safe to call multiple times.
    """
    from kivy.uix.screenmanager import SwapTransition  # noqa: PLC0415

    if hasattr(SwapTransition, "_kivy_workaround_applied"):
        return

    _orig = SwapTransition.on_complete

    def _patched(self: SwapTransition) -> None:  # ty:ignore[invalid-type-form]
        try:
            _orig(self)
        except AttributeError as exc:
            if "_remove_group" in str(exc):
                for screen in self.screen_in, self.screen_out:
                    for canvas in screen.canvas.before, screen.canvas.after:
                        # noinspection SpellCheckingInspection
                        canvas.remove_group("swaptransition_scale")
                super(SwapTransition, self).on_complete()  # ty:ignore[invalid-super-argument]
            else:
                raise

    SwapTransition.on_complete = _patched
    SwapTransition._kivy_workaround_applied = True  # noqa: SLF001
