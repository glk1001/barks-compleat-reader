"""A Label that renders soft-hyphen-marked text with real hyphens at line breaks.

Kivy cannot handle soft hyphens itself, so this label drives the two-pass refinement
implemented in ``barks_reader.core.hyphen_break_engine``: render word fragments as
``[ref=...]`` runs, read back the ref bounding boxes to see where lines actually
broke, insert a visible ``-`` at exactly those points, and repeat until stable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel
from kivy.properties import NumericProperty, StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.label import Label
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.hyphen_break_engine import SOFT_HYPHEN, BreakRefinement, RefinementStatus
from barks_reader.core.justified_lines import JustifiedWord, repair_justified_lines

if TYPE_CHECKING:
    from kivy.input import MotionEvent

_MIN_USABLE_WIDTH = 2
_LOG_SNIPPET_LEN = 60
# Seconds of quiet before the lines are reported: the text, its width and the lines shown
# each settle on a frame of their own, and only where they end up says anything.
_LINES_REPORT_DELAY = 0.25


def _keep_justified_lines_inside(core_label: CoreMarkupLabel) -> None:
    """Have this core label repair its justified lines after each layout.

    On the instance rather than by a subclass: Kivy's `Label` checks that its core label's
    class is exactly `MarkupLabel`, and hands over no refs otherwise.
    """
    lay_out = core_label._pre_render  # noqa: SLF001

    def measure(word: JustifiedWord) -> float:
        options = core_label.options
        core_label.options = word.options
        try:
            return core_label.get_extents(word.text)[0]
        finally:
            core_label.options = options

    def lay_out_and_repair() -> tuple[int, int]:
        size = lay_out()
        width = core_label.text_size[0]
        if core_label.options["halign"] == "justify" and width is not None:
            padding = core_label.options["padding"]
            repair_justified_lines(
                core_label._cached_lines,  # noqa: SLF001
                width - padding[0] - padding[2],
                measure,
            )
        return size

    core_label._pre_render = lay_out_and_repair  # noqa: SLF001  # ty: ignore[invalid-assignment]


class HyphenatingLabel(Label):
    """Justified label with visible hyphens at the line breaks inside words.

    Set ``source_text`` (soft-hyphen-marked, e.g. from ``hyphenate_text``) instead
    of ``text``; the label manages ``text`` internally. Requires ``markup: True``
    and a width-constrained ``text_size`` (as for any justified label).
    """

    source_text = StringProperty("")
    # The lines to show, 0 for all: Kivy's ``max_lines``, applied once the breaks are
    # refined. Set during the refinement, the lines it drops render no refs, and the
    # refinement fails over to showing every word unhyphenated.
    shown_lines = NumericProperty(0)

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        self._refining = False
        self._applied_key: tuple[str, int, float] | None = None
        self._refine_trigger = Clock.create_trigger(self._refine, 0)
        self._line_count = 0
        self._counted_text = ""
        self._reported_lines: tuple[str, int, int] | None = None
        self._lines_report_trigger = Clock.create_trigger(self._report_lines, _LINES_REPORT_DELAY)

        self.bind(
            source_text=self._request_refine,
            width=self._request_refine,
            font_size=self._request_refine,
            shown_lines=self._apply_shown_lines,
        )
        # A text given to the constructor was set before the bindings were made.
        if self.source_text:
            self._request_refine()

    def _create_label(self) -> None:
        previous = self._label
        super()._create_label()
        if self._label is not previous and isinstance(self._label, CoreMarkupLabel):
            _keep_justified_lines_inside(self._label)

    def on_touch_down(self, touch: MotionEvent) -> bool:
        """Pass a touch to the label's children, as a plain widget does."""
        # The refs in this label are layout scaffolding, not links: skip Label's
        # ref hit-testing (which would swallow touches) and behave like a plain widget.
        return bool(super(Label, self).on_touch_down(touch))

    def _request_refine(self, *_args: object) -> None:
        self._refine_trigger()

    def _apply_shown_lines(self, *_args: object) -> None:
        if not self._refining:
            self.max_lines = int(self.shown_lines)
            if self.shown_lines and self.source_text and self._counted_text != self.source_text:
                # Refined while every line was shown, the text was never counted
                # (`_count_lines`): refine it again, for a count to report.
                self._applied_key = None
                self._request_refine()
            self._request_lines_report()

    def _request_lines_report(self) -> None:
        self._lines_report_trigger.cancel()
        self._lines_report_trigger()

    def _count_lines(self) -> None:
        """Count the lines with every one rendered, before the cut to `shown_lines`."""
        if self.shown_lines:
            self.texture_update()
            core_label = self._label
            self._line_count = len(core_label._cached_lines) if core_label else 0  # noqa: SLF001
            self._counted_text = self.source_text

    def _report_lines(self, *_args: object) -> None:
        shown = int(self.shown_lines)
        # A count is for the text it was made from: the text can change before the next one.
        if not shown or not self.source_text or self._counted_text != self.source_text:
            return
        report = (self.source_text, self._line_count, shown)
        if report == self._reported_lines:
            return
        self._reported_lines = report
        logger.debug(log_markers.TEXT_LAID_OUT.format(lines=self._line_count, shown=shown))
        if self._line_count > shown:
            logger.info(
                log_markers.TEXT_CUT_SHORT.format(
                    lines=self._line_count,
                    shown=shown,
                    snippet=self.source_text.replace(SOFT_HYPHEN, "")[:_LOG_SNIPPET_LEN],
                )
            )

    def _refine(self, *_args: object) -> None:
        if self._refining:
            return

        key = (self.source_text, int(self.width), float(self.font_size))
        if key == self._applied_key:
            return

        self._refining = True
        self._counted_text = ""
        try:
            self.max_lines = 0  # every line renders, so every fragment has a ref to read
            if not self.source_text or self.width < _MIN_USABLE_WIDTH:
                # No usable layout width yet: show the text unhyphenated for now.
                self.text = self.source_text.replace(SOFT_HYPHEN, "")
                self._applied_key = None
                return
            try:
                self._run_refinement(key)
            except Exception:  # noqa: BLE001 - text layout must never take down the UI
                logger.exception("Hyphen refinement error; showing text without break points.")
                self.text = self.source_text.replace(SOFT_HYPHEN, "")
                self._applied_key = key
            self._count_lines()
        finally:
            self.max_lines = int(self.shown_lines)
            self._refining = False
        self._request_lines_report()

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
