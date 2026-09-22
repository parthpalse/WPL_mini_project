"""Golden test scenarios for BankEase financial engine.

Hand-calculated test cases across income levels, tax regimes, rebate boundaries,
surcharges, deficit cases, and employment types.
"""

import pytest
from decimal import Decimal
from app.engine.tax import calculate_tax, calculate_tax_regime
from app.engine.max_investment import calculate_surplus
from app.engine.optimizer import optimize_allocation
from app.engine.models import UserProfile, DebtItem, TaxDeductions


TAX_CONFIG = "config/tax_rules_fy2026_27.json"
PROD_CONFIG = "config/product_rates_2026.json"
RULES_CONFIG = "config/planning_rules.json"


class TestGoldenScenarios:
    """10 Comprehensive Golden Test Scenarios."""

    def test_scenario_1_low_income_3l(self):
        """Scenario 1: Low Income (₹3,00,000 / ₹3L)
        Taxable income: 0 (after 75k std ded, 2.25L taxable < 4L 0% slab).
        Tax: 0. Net monthly: ₹25,000.
        """
        res = calculate_tax(300000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 225000.0
        assert res['total_tax'] == 0.0
        assert res['effective_rate_pct'] == 0.0
        assert res['net_monthly_income'] == 25000.0

    def test_scenario_2_rebate_zone_6l(self):
        """Scenario 2: Rebate Zone (₹6,00,000 / ₹6L)
        Taxable: 5,25,000. Slab tax before rebate:
        4L @ 0% = 0; 1.25L @ 5% = 6,250.
        Sec 87A rebate: 6,250. Total tax: 0. Net monthly: 50,000.
        """
        res = calculate_tax(600000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 525000.0
        assert res['tax_before_cess'] == 6250.0
        assert res['rebate_87a'] == 6250.0
        assert res['total_tax'] == 0.0
        assert res['net_monthly_income'] == 50000.0

    def test_scenario_3_mid_income_9l(self):
        """Scenario 3: Mid Income (₹9,00,000 / ₹9L)
        Taxable: 8,25,000.
        Slab tax: 4L @ 0% = 0; 4L @ 5% = 20,000; 25k @ 10% = 2,500. Total = 22,500.
        Eligible for 87A rebate (taxable <= 12L). Rebate = 22,500.
        Total tax: 0.
        """
        res = calculate_tax(900000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 825000.0
        assert res['tax_before_cess'] == 22500.0
        assert res['rebate_87a'] == 22500.0
        assert res['total_tax'] == 0.0

    def test_scenario_4_rebate_cutoff_exact_12_75l(self):
        """Scenario 4: Exact Rebate Cutoff (₹12,75,000 / ₹12.75L)
        Taxable income: 12,00,000.
        Slab tax: 4L @ 0% = 0; 4L @ 5% = 20,000; 4L @ 10% = 40,000. Total = 60,000.
        Max rebate: 60,000. Total tax: 0.
        """
        res = calculate_tax(1275000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 1200000.0
        assert res['tax_before_cess'] == 60000.0
        assert res['rebate_87a'] == 60000.0
        assert res['total_tax'] == 0.0

    def test_scenario_5_just_above_rebate_cutoff_marginal_relief(self):
        """Scenario 5: Just Above Cutoff (₹12,80,000 / ₹12.8L) — Marginal Relief in Action!
        Taxable: 12,05,000 (₹5,000 excess over ₹12L).
        Without relief: tax would be ₹63,180.
        WITH marginal relief: tax cannot exceed excess income (₹5,000) + 4% cess = ₹5,200!
        """
        res = calculate_tax(1280000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 1205000.0
        assert res['tax_after_rebate'] == 5000.0
        assert res['cess'] == 200.0
        assert res['total_tax'] == 5200.0
        # Net annual income is 12,80,000 - 5,200 = 12,74,800
        assert res['net_annual_income'] == 1274800.0

    def test_scenario_6_upper_mid_salaried_15l(self):
        """Scenario 6: Upper-Mid Income with EMI (₹15,00,000 / ₹15L)
        Taxable: 14,25,000.
        Slab tax: 0-4L: 0; 4-8L: 20k; 8-12L: 40k; 12-14.25L (2.25L @ 15%): 33,750.
        Total base tax: 93,750. Cess (4%): 3,750. Total tax: 97,500.
        """
        res = calculate_tax(1500000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 1425000.0
        assert res['tax_before_cess'] == 93750.0
        assert res['total_tax'] == 97500.0

    def test_scenario_7_affluent_dual_regime_comparison(self):
        """Scenario 7: Dual Regime Comparison (₹25,00,000 / ₹25L)
        Tests that both Old and New regimes are computed and compared.
        """
        deductions = TaxDeductions(
            sec_80c=Decimal('150000'),
            sec_80d=Decimal('25000'),
            home_loan_interest_24b=Decimal('200000')
        )
        res = calculate_tax(2500000, TAX_CONFIG, regime_preference='auto', deductions=deductions)
        assert res['regime_comparison'] is not None
        assert 'new_tax' in res['regime_comparison']
        assert 'old_tax' in res['regime_comparison']
        assert res['recommended_regime'] in ('new', 'old')

    def test_scenario_8_surcharge_boundary_60l(self):
        """Scenario 8: Surcharge on High Earner (₹60,00,000 / ₹60L)
        Taxable: 59,25,000 > 50L -> Triggers 10% surcharge with marginal relief.
        """
        res = calculate_tax(6000000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 5925000.0
        assert res['surcharge'] > 0.0
        assert res['total_tax'] > res['tax_before_cess']

    def test_scenario_9_super_hni_1cr(self):
        """Scenario 9: Super HNI (₹1,00,00,000 / ₹1 Crore)
        High tax slab + 15% surcharge tier check.
        """
        res = calculate_tax(10000000, TAX_CONFIG, regime_preference='new')
        assert res['taxable_income'] == 9925000.0
        assert res['surcharge'] > 0.0
        assert res['effective_rate_pct'] > 25.0

    def test_scenario_10_deficit_recovery_plan(self):
        """Scenario 10: Deficit Case (₹4L income, ₹45K monthly expenses)
        Tests that when capacity <= 0, a deficit plan with levers is returned.
        """
        surplus = calculate_surplus(
            gross_income=400000,
            fixed_expenses=[{'name': 'Rent', 'amount': 25000, 'category': 'essential'}],
            variable_expenses=[{'name': 'Dining', 'amount': 20000, 'category': 'discretionary'}],
            tax_config=TAX_CONFIG,
            rules_config=RULES_CONFIG
        )
        assert surplus['summary']['surplus_is_positive'] is False
        assert surplus['deficit_plan'] is not None
        assert surplus['deficit_plan']['gap_amount'] > 0
        assert len(surplus['deficit_plan']['top_levers']) >= 2

    def test_scenario_variable_income_freelancer_emergency_fund(self):
        """Bonus Scenario: Variable-Income Freelancer
        Profile with self_employed + variable income should get 12 months emergency fund target.
        """
        profile = UserProfile(
            age=28,
            employment_type="self_employed",
            income_stability="variable",
            dependents=1
        )
        surplus = calculate_surplus(
            gross_income=1800000,
            fixed_expenses=[{'name': 'Living', 'amount': 50000}],
            user_profile=profile,
            tax_config=TAX_CONFIG,
            rules_config=RULES_CONFIG
        )
        ef = surplus['emergency_fund_result']
        assert ef['target_months'] == 12
