"""Branch-coverage tests for ``validate_payment_data``.

The top-level ``test_barks_payments.py`` only confirms validation passes on
real data. This file exercises each individual error branch by patching the
module-level data tables with minimal synthetic fixtures.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from barks_fantagraphics import barks_payments as bp_module
from barks_fantagraphics.barks_payments import PaymentInfo, validate_payment_data
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import ComicBookInfo
from barks_fantagraphics.comic_issues import Issues


def _info(
    title: Titles,
    submitted_day: int,
    submitted_month: int,
    submitted_year: int,
) -> ComicBookInfo:
    return ComicBookInfo(
        title=title,
        is_barks_title=True,
        issue_name=Issues.US,
        issue_number=1,
        issue_month=1,
        issue_year=1943,
        submitted_day=submitted_day,
        submitted_month=submitted_month,
        submitted_year=submitted_year,
    )


def _payment(
    title: Titles,
    accepted_day: int,
    accepted_month: int,
    accepted_year: int,
) -> PaymentInfo:
    return PaymentInfo(
        title=title,
        num_pages=10,
        accepted_day=accepted_day,
        accepted_month=accepted_month,
        accepted_year=accepted_year,
        payment=100.0,
    )


def _run_validation(
    capsys: pytest.CaptureFixture[str],
    *,
    title_info: list[ComicBookInfo],
    payments: dict[Titles, PaymentInfo],
    one_pagers: list[Titles] | None = None,
    non_comic: list[Titles] | None = None,
    expect_assertion_error: bool = False,
) -> str:
    """Run ``validate_payment_data`` against patched data tables and return its output."""
    with (
        patch.object(bp_module, "BARKS_TITLE_INFO", title_info),
        patch.object(bp_module, "BARKS_PAYMENTS", payments),
        patch.object(bp_module, "ONE_PAGERS", one_pagers or []),
        patch.object(bp_module, "NON_COMIC_TITLES", non_comic or []),
    ):
        if expect_assertion_error:
            with pytest.raises(AssertionError):
                validate_payment_data()
        else:
            validate_payment_data()  # Should not raise.

    return capsys.readouterr().out


class TestValidatePaymentData:
    def test_happy_path_within_acceptance_window_passes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={title: _payment(title, 15, 2, 1943)},
        )
        assert "0 issue(s) found" in out

    def test_missing_payment_for_multi_page_title_raises(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Multi-page (non one-pager) without a payment entry — counted as
        # ``missing_payment_errors`` and fails the assertion.
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={},
            expect_assertion_error=True,
        )
        assert "has no payment info" in out
        assert "missing payment info: 1" in out

    def test_missing_payment_for_one_pager_does_not_raise(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # One-pagers without payment info are reported but not counted as a
        # hard error — assertion still passes.
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={},
            one_pagers=[title],
        )
        assert "missing one-pager payments: 1" in out
        assert "missing payment info: 0" in out

    def test_accepted_before_submitted_is_date_order_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 15, 6, 1943)],
            payments={title: _payment(title, 1, 6, 1943)},
        )
        assert "is before submitted date" in out
        assert "accepted-before-submitted: 1" in out

    def test_accepted_more_than_13_months_after_submitted_is_gap_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={title: _payment(title, 15, 3, 1944)},  # 14 months later.
        )
        assert "more than 3 months after" in out
        assert "13-months-after-submitted: 1" in out

    def test_exactly_13_months_after_is_not_a_gap_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={title: _payment(title, 1, 2, 1944)},  # Exactly 13 months.
        )
        assert "0 issue(s) found" in out

    def test_submitted_day_minus_one_normalised_to_first_of_month(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # When the day is unknown (-1), the function uses day=1 — so an
        # accepted date later in the same month must NOT be flagged as
        # accepted-before-submitted.
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, -1, 5, 1943)],
            payments={title: _payment(title, 20, 5, 1943)},
        )
        assert "0 issue(s) found" in out

    def test_non_comic_titles_are_skipped(self, capsys: pytest.CaptureFixture[str]) -> None:
        # A non-comic entry with no payment info should not be flagged.
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        out = _run_validation(
            capsys,
            title_info=[_info(title, 1, 1, 1943)],
            payments={},
            non_comic=[title],
        )
        assert "0 issue(s) found" in out

    def test_summary_counts_all_categories(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Mix of: 1 missing multi-page, 1 missing one-pager, 1 date-order
        # error, 1 date-gap error, 1 good entry.
        t_missing = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        t_one_pager = Titles.VICTORY_GARDEN_THE
        t_order = Titles.RABBITS_FOOT_THE
        t_gap = Titles.LIFEGUARD_DAZE
        t_good = Titles.GOOD_DEEDS

        out = _run_validation(
            capsys,
            title_info=[
                _info(t_missing, 1, 1, 1943),
                _info(t_one_pager, 1, 1, 1943),
                _info(t_order, 15, 6, 1943),
                _info(t_gap, 1, 1, 1943),
                _info(t_good, 1, 1, 1943),
            ],
            payments={
                t_order: _payment(t_order, 1, 6, 1943),
                t_gap: _payment(t_gap, 15, 3, 1944),
                t_good: _payment(t_good, 15, 2, 1943),
            },
            one_pagers=[t_one_pager],
            expect_assertion_error=True,
        )
        assert "4 issue(s) found" in out
        assert "missing payment info: 1" in out
        assert "missing one-pager payments: 1" in out
        assert "accepted-before-submitted: 1" in out
        assert "13-months-after-submitted: 1" in out
