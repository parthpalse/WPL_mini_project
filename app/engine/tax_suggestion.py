"""Suggested monthly income tax (TDS) for a given monthly gross salary.

Pure function over the FY 2026-27 rules in config/tax_rules_fy2026_27.json. It assumes a
salaried resident below 60 with no deductions beyond the standard deduction, so it is a
starting point the user can override with the figure on their payslip.
"""

from __future__ import annotations

import os

from app.engine.tax import calculate_tax_regime, load_config

TAX_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "tax_rules_fy2026_27.json")


def suggest_monthly_tax(monthly_gross: float, config: dict | None = None) -> dict:
    cfg = config or load_config(TAX_CONFIG_PATH)
    annual = max(0.0, float(monthly_gross)) * 12
    new = calculate_tax_regime(annual, "new", cfg)
    old = calculate_tax_regime(annual, "old", cfg)
    rebate = cfg["new_regime"]["rebate_87a"]
    zero_tax_annual = rebate["max_taxable_income"] + cfg["new_regime"]["standard_deduction"]
    return {
        "financialYear": cfg["financial_year"],
        "regime": "new",
        "annualGross": round(annual),
        "taxableIncome": round(new["taxable_income"]),
        "annualTax": round(new["total_tax"]),
        "monthlyTax": round(new["total_tax"] / 12),
        "effectiveRatePct": new["effective_rate_pct"],
        "oldRegimeMonthlyTax": round(old["total_tax"] / 12),
        "zeroTaxUpToAnnual": round(zero_tax_annual),
    }
