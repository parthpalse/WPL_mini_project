"""Tests for financial projection functions in app/engine/inflation.py."""

import pytest
from app.engine.inflation import (
    calculate_sip_future_value,
    calculate_rd_maturity,
    calculate_fd_maturity,
    real_value_in_todays_rupees,
    real_return,
    project_goal
)


class TestProjections:

    def test_sip_future_value_annuity_due(self):
        """Monthly SIP: ₹10,000/month, 12% p.a., 12 months (Annuity Due).
        
        Using monthly rate r = 1%:
        FV = 10000 * ((1.01^12 - 1) / 0.01) * 1.01 = ₹1,28,093.28
        Total invested = ₹1,20,000
        """
        res = calculate_sip_future_value(
            monthly_investment=10000,
            annual_return_pct=12.0,
            tenure_months=12
        )
        assert res['total_invested'] == 120000.0
        assert pytest.approx(res['future_value'], abs=1.0) == 128093.28
        assert res['wealth_gain'] > 0.0

    def test_step_up_sip(self):
        """Step-up SIP: ₹10,000/month with 10% annual step-up over 24 months."""
        res = calculate_sip_future_value(
            monthly_investment=10000,
            annual_return_pct=12.0,
            tenure_months=24,
            step_up_pct=10.0
        )
        # Year 1: 10k * 12 = 120k; Year 2: 11k * 12 = 132k -> Total = 252k
        assert res['total_invested'] == 252000.0
        assert res['future_value'] > 280000.0

    def test_rd_maturity_quarterly_compounding(self):
        """Recurring Deposit: ₹5,000/month, 7% p.a., 12 months with quarterly compounding."""
        res = calculate_rd_maturity(
            monthly_deposit=5000,
            annual_interest_pct=7.0,
            tenure_months=12
        )
        assert res['total_invested'] == 60000.0
        assert res['maturity_value'] > 62000.0
        assert res['interest_earned'] > 2000.0

    def test_fd_maturity_quarterly_compounding_and_tax(self):
        """Fixed Deposit: ₹1,00,000, 7.5% p.a., 12 months (4 quarters) with 20% tax on interest."""
        res = calculate_fd_maturity(
            principal=100000,
            annual_interest_pct=7.5,
            tenure_months=12,
            marginal_tax_rate_pct=20.0
        )
        assert res['principal'] == 100000.0
        # Pre-tax maturity on 100k @ 7.5% quarterly = 100000 * (1 + 0.075/4)^4 = 107,713.59
        assert pytest.approx(res['pre_tax_maturity'], abs=1.0) == 107713.59
        assert res['gross_interest'] > 7700.0
        assert res['tax_on_interest'] > 1500.0
        assert res['post_tax_maturity'] < res['pre_tax_maturity']

    def test_project_goal_three_scenarios(self):
        """Goal projection produces Conservative, Base, and Optimistic scenarios."""
        proj = project_goal(
            monthly_allocation=25000,
            target_amount=2000000,
            horizon_months=60,
            product_type="Equity Fund"
        )
        scenarios = proj['scenarios']
        assert 'conservative' in scenarios
        assert 'base' in scenarios
        assert 'optimistic' in scenarios
        assert scenarios['optimistic']['nominal_future_value'] > scenarios['base']['nominal_future_value']
        assert scenarios['base']['nominal_future_value'] > scenarios['conservative']['nominal_future_value']
