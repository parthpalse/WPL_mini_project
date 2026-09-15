"""Tax engine tests — hand-calculated cases for FY 2026-27 New Regime.

Each test has the full hand calculation in comments so any reviewer
can verify correctness without running code.
"""
import pytest
from app.engine.tax import calculate_tax


class TestTaxCalculation:
    """5+ hand-calculated tax scenarios."""

    def test_case1_6l_income_full_rebate(self, tax_config):
        """₹6L income — should get full 87A rebate, zero tax.

        Hand calculation:
            Gross: 6,00,000
            Std deduction: 75,000
            Taxable: 5,25,000
            Tax: 4,00,000 @ 0% = 0
                 1,25,000 @ 5% = 6,250
            Tax before cess: 6,250
            Taxable (5,25,000) ≤ 12,00,000 → 87A rebate
            Rebate: min(6250, 60000) = 6,250
            Tax after rebate: 0
            Cess: 0
            Total tax: 0
            Net: 6,00,000
        """
        result = calculate_tax(600000, tax_config)
        assert result['taxable_income'] == 525000
        assert result['tax_before_cess'] == 6250
        assert result['rebate_87a'] == 6250
        assert result['total_tax'] == 0
        assert result['net_annual_income'] == 600000
        assert result['net_monthly_income'] == 50000

    def test_case2_15l_income_no_rebate(self, tax_config):
        """₹15L income — above rebate threshold, moderate tax.

        Hand calculation:
            Gross: 15,00,000
            Std deduction: 75,000
            Taxable: 14,25,000
            Tax: 4,00,000 @ 0%  = 0
                 4,00,000 @ 5%  = 20,000
                 4,00,000 @ 10% = 40,000
                 2,25,000 @ 15% = 33,750
            Tax before cess: 93,750
            Taxable (14,25,000) > 12,00,000 → no rebate
            Rebate: 0
            Tax after rebate: 93,750
            Cess: 93,750 × 4% = 3,750
            Total tax: 97,500
            Net: 15,00,000 - 97,500 = 14,02,500
            Monthly net: 14,02,500 / 12 = 1,16,875
        """
        result = calculate_tax(1500000, tax_config)
        assert result['taxable_income'] == 1425000
        assert result['tax_before_cess'] == 93750
        assert result['rebate_87a'] == 0
        assert result['cess'] == 3750
        assert result['total_tax'] == 97500
        assert result['net_annual_income'] == 1402500
        assert result['net_monthly_income'] == 116875

    def test_case3_30l_income_high_bracket(self, tax_config):
        """₹30L income — hits 30% slab.

        Hand calculation:
            Gross: 30,00,000
            Std deduction: 75,000
            Taxable: 29,25,000
            Tax: 4,00,000 @ 0%  = 0
                 4,00,000 @ 5%  = 20,000
                 4,00,000 @ 10% = 40,000
                 4,00,000 @ 15% = 60,000
                 4,00,000 @ 20% = 80,000
                 4,00,000 @ 25% = 1,00,000
                 5,25,000 @ 30% = 1,57,500
            Tax before cess: 4,57,500
            No rebate
            Cess: 4,57,500 × 4% = 18,300
            Total tax: 4,75,800
            Net: 30,00,000 - 4,75,800 = 25,24,200
            Monthly: 25,24,200 / 12 = 2,10,350
        """
        result = calculate_tax(3000000, tax_config)
        assert result['taxable_income'] == 2925000
        assert result['tax_before_cess'] == 457500
        assert result['cess'] == 18300
        assert result['total_tax'] == 475800
        assert result['net_annual_income'] == 2524200
        assert result['net_monthly_income'] == 210350

    def test_case4_4l_income_below_first_slab(self, tax_config):
        """₹4L income — entirely within 0% slab after std deduction.

        Hand calculation:
            Gross: 4,00,000
            Std deduction: 75,000
            Taxable: 3,25,000
            Tax: 3,25,000 @ 0% = 0
            Total tax: 0
            Net: 4,00,000
        """
        result = calculate_tax(400000, tax_config)
        assert result['taxable_income'] == 325000
        assert result['tax_before_cess'] == 0
        assert result['total_tax'] == 0
        assert result['net_annual_income'] == 400000

    def test_case5_12l_income_rebate_boundary(self, tax_config):
        """₹12L income — right at 87A rebate boundary.

        Hand calculation:
            Gross: 12,00,000
            Std deduction: 75,000
            Taxable: 11,25,000
            Tax: 4,00,000 @ 0%  = 0
                 4,00,000 @ 5%  = 20,000
                 3,25,000 @ 10% = 32,500
            Tax before cess: 52,500
            Taxable (11,25,000) ≤ 12,00,000 → rebate applies
            Rebate: min(52,500, 60,000) = 52,500
            Tax after rebate: 0
            Cess: 0
            Total tax: 0
            Net: 12,00,000
        """
        result = calculate_tax(1200000, tax_config)
        assert result['taxable_income'] == 1125000
        assert result['tax_before_cess'] == 52500
        assert result['rebate_87a'] == 52500
        assert result['total_tax'] == 0
        assert result['net_annual_income'] == 1200000

    def test_case6_12_75l_just_at_rebate_cutoff(self, tax_config):
        """₹12.75L income — taxable income exactly ₹12L (boundary of rebate).

        Hand calculation:
            Gross: 12,75,000
            Std deduction: 75,000
            Taxable: 12,00,000
            Tax: 4,00,000 @ 0%  = 0
                 4,00,000 @ 5%  = 20,000
                 4,00,000 @ 10% = 40,000
            Tax before cess: 60,000
            Taxable (12,00,000) ≤ 12,00,000 → rebate applies
            Rebate: min(60,000, 60,000) = 60,000
            Tax after rebate: 0
            Cess: 0
            Total tax: 0
            Net: 12,75,000
        """
        result = calculate_tax(1275000, tax_config)
        assert result['taxable_income'] == 1200000
        assert result['tax_before_cess'] == 60000
        assert result['rebate_87a'] == 60000
        assert result['total_tax'] == 0
        assert result['net_annual_income'] == 1275000

    def test_zero_income(self, tax_config):
        """Edge case: zero income."""
        result = calculate_tax(0, tax_config)
        assert result['taxable_income'] == 0
        assert result['total_tax'] == 0
        assert result['net_annual_income'] == 0
