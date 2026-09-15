"""Inflation adjustment tests."""
import pytest
from app.engine.inflation import adjust_for_inflation, real_return


class TestInflation:
    def test_adjust_one_year(self, inflation_config):
        """₹1,00,000 after 1 year at 6% = ₹1,06,000"""
        result = adjust_for_inflation(100000, 1, inflation_config)
        assert result == 106000.0

    def test_adjust_five_years(self, inflation_config):
        """₹1,00,000 after 5 years at 6% = 1,00,000 × 1.06^5 = ₹1,33,822.56"""
        result = adjust_for_inflation(100000, 5, inflation_config)
        assert result == pytest.approx(133822.56, abs=0.01)

    def test_adjust_zero_years(self, inflation_config):
        """No change for 0 years."""
        result = adjust_for_inflation(100000, 0, inflation_config)
        assert result == 100000.0

    def test_real_return_equity(self, inflation_config):
        """12% nominal - 6% inflation → real return.
        Fisher: (1.12 / 1.06) - 1 = 0.056604... = 5.6604%
        """
        result = real_return(12.0, inflation_config)
        assert result == pytest.approx(5.6604, abs=0.001)

    def test_real_return_savings(self, inflation_config):
        """3.5% nominal - 6% inflation → negative real return.
        Fisher: (1.035 / 1.06) - 1 = -0.023585... = -2.3585%
        """
        result = real_return(3.5, inflation_config)
        assert result == pytest.approx(-2.3585, abs=0.001)
