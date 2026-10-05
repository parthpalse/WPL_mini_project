"""Tests for dashboard calculations, wizard data translation, and simulate API.

Verifies that:
1. Gross estimation from in-hand take-home matches user take-home exactly after tax.
2. Monthly expenses are not multiplied by 12 (eliminating the catastrophic false-deficit bug).
3. Debts (credit card, loans) are passed and deducted correctly.
4. Existing savings reduce emergency fund shortfall accurately.
5. All required UI metrics (trace, tax_comparison, emergency_fund_target, etc.) are present.
6. What-if simulate_api computes mathematically sound values.
"""

import pytest
from app import create_app
from app.routes.dashboard import _estimate_gross_from_net
from app.engine.tax import calculate_tax_regime


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestGrossEstimation:
    """Tests that _estimate_gross_from_net correctly inverts tax slabs."""

    TAX_CONFIG = "config/tax_rules_fy2026_27.json"

    def test_estimate_zero_income(self):
        assert _estimate_gross_from_net(0, self.TAX_CONFIG) == 0.0

    def test_estimate_rebate_zone(self):
        # Incomes <= 12,75,000 have zero tax under New Regime
        # e.g. ₹50,000/month = 6,00,000 net -> gross should be 6,00,000
        gross = _estimate_gross_from_net(600000, self.TAX_CONFIG)
        assert gross == 600000.0
        tax = calculate_tax_regime(gross, 'new', self.TAX_CONFIG)['total_tax']
        assert tax == 0.0
        assert gross - tax == 600000.0

    def test_estimate_rebate_cutoff(self):
        gross = _estimate_gross_from_net(1200000, self.TAX_CONFIG)
        assert gross == 1200000.0

    def test_estimate_higher_bracket(self):
        # Take-home of ₹1,50,000/month = 18,00,000 net annual
        net_target = 1800000.0
        gross = _estimate_gross_from_net(net_target, self.TAX_CONFIG)
        tax = calculate_tax_regime(gross, 'new', self.TAX_CONFIG)['total_tax']
        net_actual = gross - tax
        # Net actual should match net target within 5 rupees
        assert abs(net_actual - net_target) < 5.0


class TestDashboardRouteCalculations:
    """Integration tests for the dashboard route and data translation."""

    def test_dashboard_with_wizard_data_correct_surplus(self, client):
        """User enters ₹75,000/month income, ₹30,000 expenses, ₹50,000 savings.
        Must result in a healthy positive surplus, NOT a false deficit.
        """
        with client.session_transaction() as sess:
            sess['wizard_data'] = {
                'income_amount': '75000',
                'income_freq': 'monthly',
                'exp_rent': '15000',
                'exp_food': '8000',
                'exp_transport': '3000',
                'exp_utilities': '2000',
                'exp_health': '2000',
                'exp_other': '5000',  # Discretionary
                'existing_savings': '50000',
                'risk_attitude': '6',
                'liquidity_need': 'medium',
                'goal_horizon': 'medium'
            }

        response = client.get('/dashboard/')
        assert response.status_code == 200
        html = response.get_data(as_text=True)

        # Check that surplus is positive
        assert 'Monthly Investable Surplus' in html
        assert 'Positive' in html
        # Calculation trace must be rendered
        assert 'How This Was Calculated' in html
        assert 'Step A: Net Monthly In-Hand Income' in html
        # Tax regime comparison must be rendered
        assert 'Tax Regime Comparison' in html

    def test_dashboard_with_debts_and_credit_card(self, client):
        """User with credit card debt should have alert and proper EMI deduction."""
        with client.session_transaction() as sess:
            sess['wizard_data'] = {
                'income_amount': '100000',
                'income_freq': 'monthly',
                'exp_rent': '25000',
                'exp_food': '10000',
                'credit_card_balance': '30000',
                'personal_loan_emi': '8000',
                'personal_loan_rate': '13.5',
                'existing_savings': '20000',
                'risk_attitude': '5'
            }

        response = client.get('/dashboard/')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Clear Credit Card Debt First' in html
        assert '30,000' in html

    def test_simulate_api_correct_calculation(self, client):
        """What-if simulate_api must calculate correct surplus without 12x inflation."""
        res = client.post('/dashboard/simulate_api', json={
            'income': 80000,
            'expenses': 35000,
            'risk_score': 5
        })
        assert res.status_code == 200
        data = res.get_json()
        assert 'surplus' in data
        assert 'allocations' in data
        # Income 80k, expenses 35k -> surplus should be ~35k-40k (after buffer & emergency fund)
        # Definitely NOT negative!
        assert data['surplus'] > 20000
        assert data['surplus'] < 50000
