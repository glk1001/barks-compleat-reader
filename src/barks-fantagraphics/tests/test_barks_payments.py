import pytest
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS, validate_payment_data
from barks_fantagraphics.barks_titles import Titles


class TestBarksPayments:
    """Test suite for validating the Barks payment data."""

    def test_validate_payment_data_succeeds_with_current_data(self) -> None:
        """Tests that the validation passes with the complete, correct data."""
        try:
            validate_payment_data()
        except AssertionError:
            pytest.fail("validate_payment_data() failed.")

    def test_barks_payments_submission_order(self) -> None:
        titles_as_list = list(Titles)
        prev_title = -1
        for payment_title in BARKS_PAYMENTS:
            title = titles_as_list.index(payment_title)
            assert prev_title < title, f"Payment order error: {payment_title.name}"
            prev_title = title
