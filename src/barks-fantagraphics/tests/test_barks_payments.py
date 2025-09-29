import unittest

from barks_fantagraphics.barks_payments import (
    validate_payment_data,
)


class TestBarksPayments(unittest.TestCase):
    """Test suite for validating the Barks payment data."""

    def test_validate_payment_data_succeeds_with_current_data(self) -> None:
        """Tests that the validation passes with the complete, correct data."""
        try:
            validate_payment_data()
        except AssertionError:
            self.fail("validate_payment_data() failed.")
