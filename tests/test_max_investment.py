"""Surplus (max investment) calculator tests — full pipeline.

These are the 5 end-to-end hand-calculated scenarios
that MUST pass before proceeding to Phase 2.
"""
import pytest
from app.engine.max_investment import calculate_surplus


class TestSurplusCalculation:

    def test_case1_6l_minimal_expenses(self, tax_config):
        """₹6L income, minimal expenses, no debt.

        Tax: 0 (87A rebate) → Net monthly: 50,000
        Expenses: 15,000/month
        Debt: 0
        Emergency: 6 × 15,000 = 90,000 / 12 = 7,500/month
        Surplus: 50,000 - 15,000 - 0 - 7,500 = 27,500/month
        """
        result = calculate_surplus(
            gross_income=600000,
            fixed_expenses=[{'name': 'Rent', 'amount': 10000}],
            variable_expenses=[{'name': 'Food', 'amount': 5000}],
            monthly_debt_payments=0,
            existing_emergency_fund=0,
            tax_config=tax_config
        )
        s = result['summary']
        assert s['net_monthly_income'] == 50000
        assert s['total_monthly_expenses'] == 15000
        assert s['emergency_fund_monthly'] == 7500
        assert s['monthly_surplus'] == 27500
        assert s['surplus_is_positive'] is True

    def test_case2_15l_moderate_with_emi(self, tax_config):
        """₹15L income, moderate expenses + ₹15K EMI.

        Tax: 97,500 → Net monthly: 1,16,875
        Expenses: 40,000/month
        Debt: 15,000/month
        Emergency: 6 × 40,000 = 2,40,000, existing 50,000
            Shortfall: 1,90,000, monthly: 1,90,000/12 ≈ 15,833.33
        Surplus: 1,16,875 - 40,000 - 15,000 - 15,833.33 = 46,041.67
        """
        result = calculate_surplus(
            gross_income=1500000,
            fixed_expenses=[
                {'name': 'Rent', 'amount': 20000},
                {'name': 'Insurance', 'amount': 5000}
            ],
            variable_expenses=[
                {'name': 'Food', 'amount': 10000},
                {'name': 'Transport', 'amount': 5000}
            ],
            monthly_debt_payments=15000,
            existing_emergency_fund=50000,
            tax_config=tax_config
        )
        s = result['summary']
        assert s['net_monthly_income'] == 116875
        assert s['total_monthly_expenses'] == 40000
        assert s['monthly_debt_payments'] == 15000
        assert s['emergency_fund_monthly'] == pytest.approx(15833.33, abs=0.01)
        assert s['monthly_surplus'] == pytest.approx(46041.67, abs=0.01)
        assert s['surplus_is_positive'] is True

    def test_case3_30l_high_expenses(self, tax_config):
        """₹30L income, high expenses + ₹25K debt.

        Tax: 4,75,800 → Net monthly: 2,10,350
        Expenses: 80,000/month
        Debt: 25,000/month
        Emergency: 6 × 80,000 = 4,80,000, existing 1,00,000
            Shortfall: 3,80,000, monthly: 3,80,000/12 ≈ 31,666.67
        Surplus: 2,10,350 - 80,000 - 25,000 - 31,666.67 = 73,683.33
        """
        result = calculate_surplus(
            gross_income=3000000,
            fixed_expenses=[
                {'name': 'Rent', 'amount': 40000},
                {'name': 'Insurance', 'amount': 10000},
                {'name': 'Utilities', 'amount': 5000}
            ],
            variable_expenses=[
                {'name': 'Food', 'amount': 15000},
                {'name': 'Transport', 'amount': 5000},
                {'name': 'Shopping', 'amount': 5000}
            ],
            monthly_debt_payments=25000,
            existing_emergency_fund=100000,
            tax_config=tax_config
        )
        s = result['summary']
        assert s['net_monthly_income'] == 210350
        assert s['total_monthly_expenses'] == 80000
        assert s['emergency_fund_monthly'] == pytest.approx(31666.67, abs=0.01)
        assert s['monthly_surplus'] == pytest.approx(73683.33, abs=0.01)
        assert s['surplus_is_positive'] is True

    def test_case4_4l_negative_surplus(self, tax_config):
        """₹4L income, high expenses — negative surplus edge case.

        Tax: 0 → Net monthly: 33,333.33
        Expenses: 30,000/month
        Debt: 5,000/month
        Emergency: 6 × 30,000 = 1,80,000, existing 0
            Monthly: 15,000
        Surplus: 33,333.33 - 30,000 - 5,000 - 15,000 = -16,666.67
        """
        result = calculate_surplus(
            gross_income=400000,
            fixed_expenses=[{'name': 'Rent', 'amount': 20000}],
            variable_expenses=[{'name': 'Food', 'amount': 10000}],
            monthly_debt_payments=5000,
            existing_emergency_fund=0,
            tax_config=tax_config
        )
        s = result['summary']
        assert s['net_monthly_income'] == pytest.approx(33333.33, abs=0.01)
        assert s['total_monthly_expenses'] == 30000
        assert s['monthly_surplus'] == pytest.approx(-16666.67, abs=0.01)
        assert s['surplus_is_positive'] is False

    def test_case5_12l_rebate_boundary_no_debt(self, tax_config):
        """₹12L income (rebate boundary), no debt.

        Tax: 0 (rebate) → Net monthly: 1,00,000
        Expenses: 35,000/month
        Debt: 0
        Emergency: 6 × 35,000 = 2,10,000, existing 1,00,000
            Shortfall: 1,10,000, monthly: 1,10,000/12 ≈ 9,166.67
        Surplus: 1,00,000 - 35,000 - 0 - 9,166.67 = 55,833.33
        """
        result = calculate_surplus(
            gross_income=1200000,
            fixed_expenses=[{'name': 'Rent', 'amount': 20000}],
            variable_expenses=[
                {'name': 'Food', 'amount': 10000},
                {'name': 'Transport', 'amount': 5000}
            ],
            monthly_debt_payments=0,
            existing_emergency_fund=100000,
            tax_config=tax_config
        )
        s = result['summary']
        assert s['net_monthly_income'] == 100000
        assert s['total_monthly_expenses'] == 35000
        assert s['emergency_fund_monthly'] == pytest.approx(9166.67, abs=0.01)
        assert s['monthly_surplus'] == pytest.approx(55833.33, abs=0.01)
        assert s['surplus_is_positive'] is True
