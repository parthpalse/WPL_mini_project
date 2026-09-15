"""Emergency fund calculator tests."""
import pytest
from app.engine.emergency_fund import calculate_emergency_fund


class TestEmergencyFund:
    def test_no_existing_fund(self):
        """Monthly expenses ₹30,000, no existing fund.
        Target: 30,000 × 6 = 1,80,000
        Shortfall: 1,80,000
        Monthly contribution: 1,80,000 / 12 = 15,000
        """
        result = calculate_emergency_fund(30000, existing_fund=0)
        assert result['target'] == 180000
        assert result['shortfall'] == 180000
        assert result['monthly_contribution'] == 15000
        assert result['fully_funded'] is False

    def test_partially_funded(self):
        """Expenses ₹40,000, existing ₹50,000.
        Target: 40,000 × 6 = 2,40,000
        Shortfall: 2,40,000 - 50,000 = 1,90,000
        Monthly: 1,90,000 / 12 ≈ 15,833.33
        """
        result = calculate_emergency_fund(40000, existing_fund=50000)
        assert result['target'] == 240000
        assert result['shortfall'] == 190000
        assert result['monthly_contribution'] == pytest.approx(15833.33, abs=0.01)
        assert result['fully_funded'] is False

    def test_fully_funded(self):
        """Existing fund exceeds target."""
        result = calculate_emergency_fund(20000, existing_fund=200000)
        assert result['target'] == 120000
        assert result['shortfall'] == 0
        assert result['monthly_contribution'] == 0
        assert result['fully_funded'] is True

    def test_custom_months(self):
        """3-month target instead of 6."""
        result = calculate_emergency_fund(25000, existing_fund=0, target_months=3)
        assert result['target'] == 75000
        assert result['shortfall'] == 75000
