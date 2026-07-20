"""A Label that renders soft-hyphen-marked text with real hyphens at line breaks.

Kivy cannot handle soft hyphens itself, so this label drives the two-pass refinement
implemented in ``barks_reader.core.hyphen_break_engine``: render word fragments as
``[ref=...]`` runs, read back the ref bounding boxes to see where lines actually
broke, insert a visible ``-`` at exactly those points, and repeat until stable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.properties import StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.label import Label
from loguru import logger

from barks_reader.core.hyphen_break_engine import SOFT_HYPHEN, BreakRefinement, RefinementStatus

if TYPE_CHECKING:
    from kivy.input import MotionEvent

_MIN_USABLE_WIDTH = 2
_LOG_SNIPPET_LEN = 60


class HyphenatingLabel(Label):
    """Justified label with visible hyphens at the line breaks inside words.

    Set ``source_text`` (soft-hyphen-marked, e.g. from ``hyphenate_text``) instead
    of ``text``; the label manages ``text`` internally. Requires ``markup: True``
    and a width-constrained ``text_size`` (as for any justified label).
    """

    source_text = StringProperty("")

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        self._refining = False
        self._applied_key: tuple[str, int, float] | None = None
        self._refine_trigger = Clock.create_trigger(self._refine, 0)

        self.bind(
            source_text=self._request_refine,
            width=self._request_refine,
            font_size=self._request_refine,
        )

    def on_touch_down(self, touch: MotionEvent) -> bool:
        # The refs in this label are layout scaffolding, not links: skip Label's
        # ref hit-testing (which would swallow touches) and behave like a plain widget.
        return bool(super(Label, self).on_touch_down(touch))

    def _request_refine(self, *_args: object) -> None:
        self._refine_trigger()

    def _refine(self, *_args: object) -> None:
        if self._refining:
            return

        key = (self.source_text, int(self.width), float(self.font_size))
        if key == self._applied_key:
            return

        if not self.source_text or self.width < _MIN_USABLE_WIDTH:
            # No usable layout width yet: show the text unhyphenated for now.
            self.text = self.source_text.replace(SOFT_HYPHEN, "")
            self._applied_key = None
            return

        self._refining = True
        try:
            self._run_refinement(key)
        except Exception:  # noqa: BLE001 - text layout must never take down the UI
            logger.exception("Hyphen refinement error; showing text without break points.")
            self.text = self.source_text.replace(SOFT_HYPHEN, "")
            self._applied_key = key
        finally:
            self._refining = False

    def _run_refinement(self, key: tuple[str, int, float]) -> None:
        refinement = BreakRefinement(self.source_text)

        if not refinement.has_gaps:
            self.text = refinement.markup()
            self._applied_key = key
            return

        status = RefinementStatus.CONTINUE
        while status is RefinementStatus.CONTINUE:
            self.text = refinement.markup()
            self.texture_update()  # refs are valid synchronously after this
            status = refinement.observe(self.refs)

        if status is RefinementStatus.FAILED:
            self._apply_fallback(refinement)
        else:
            self._apply_final_markup(refinement)

        self._applied_key = key

    def _apply_fallback(self, refinement: BreakRefinement) -> None:
        """Render breaks without hyphens and report which words broke unhyphenated."""
        self.text = refinement.fallback_markup()
        self.texture_update()

        snippet = self.source_text.replace(SOFT_HYPHEN, "")[:_LOG_SNIPPET_LEN]
        broken = refinement.fallback_broken_words(self.refs)
        if broken is None:
            logger.error(
                "Hyphenation failed for {!r}...: break detection unavailable "
                "(a fragment ref did not render); showing text without hyphens.",
                snippet,
            )
        elif broken:
            logger.error(
                "Hyphenation did not stabilize for {!r}...: {} word(s) wrapped without "
                "a hyphen: {}",
                snippet,
                len(broken),
                broken,
            )

    def _apply_final_markup(self, refinement: BreakRefinement) -> None:
        """Swap in the merged final markup, keeping the stable one if breaks move."""
        stable_text = self.text
        final_text = refinement.final_markup()
        if final_text == stable_text:
            return

        self.text = final_text
        self.texture_update()
        if not refinement.verify_final(self.refs):
            # The merged words measure slightly narrower and a break moved: keep the
            # verified stable layout (hairline run gaps beat a mid-line hyphen).
            self.text = stable_text
