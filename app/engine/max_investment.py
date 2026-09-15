"""Maximum investable surplus calculator.

Orchestrates the full pipeline:
    gross_income → tax → net_income → subtract expenses
    → subtract debt payments → subtract emergency fund contribution
    → investable surplus

This is the core number that feeds into the optimizer (Phase 2).
"""

import os
from typing import Union

from app.engine.tax import calculate_tax
from app.engine.expenses import calculate_expenses
from app.engine.emergency_fund import calculate_emergency_fund


def calculate_surplus(
    gross_income: float,
    fixed_expenses: list[dict] | None = None,
    variable_expenses: list[dict] | None = None,
    monthly_debt_payments: float = 0.0,
    existing_emergency_fund: float = 0.0,
    emergency_fund_months: int = 6,
    tax_config: Union[str, dict] = None
) -> dict:
    """Calculate maximum monthly investable surplus.

    Args:
        gross_income: Annual gross income in INR.
        fixed_expenses: List of fixed expense dicts with 'name' and 'amount'.
        variable_expenses: List of variable expense dicts.
        monthly_debt_payments: Total monthly debt/EMI payments.
        existing_emergency_fund: Current emergency fund balance.
        emergency_fund_months: Target months of expenses for emergency fund.
        tax_config: Path to tax config JSON or dict.

    Returns:
        Dict with full breakdown: tax_result, expense_result,
        emergency_fund_result, monthly/annual summaries, investable_surplus.
    """
    # Step 1: Tax
    tax_result = calculate_tax(gross_income, tax_config)
    net_monthly_income = tax_result['net_monthly_income']

    # Step 2: Expenses
    expense_result = calculate_expenses(fixed_expenses, variable_expenses)
    total_monthly_expenses = expense_result['total_monthly']

    # Step 3: Emergency fund
    ef_result = calculate_emergency_fund(
        monthly_expenses=total_monthly_expenses,
        existing_fund=existing_emergency_fund,
        target_months=emergency_fund_months
    )
    emergency_monthly = ef_result['monthly_contribution']

    # Step 4: Surplus
    monthly_surplus = round(
        net_monthly_income
        - total_monthly_expenses
        - monthly_debt_payments
        - emergency_monthly,
        2
    )
    annual_surplus = round(monthly_surplus * 12, 2)

    return {
        'tax_result': tax_result,
        'expense_result': expense_result,
        'emergency_fund_result': ef_result,
        'summary': {
            'net_monthly_income': net_monthly_income,
            'total_monthly_expenses': total_monthly_expenses,
            'monthly_debt_payments': monthly_debt_payments,
            'emergency_fund_monthly': emergency_monthly,
            'monthly_surplus': monthly_surplus,
            'annual_surplus': annual_surplus,
            'surplus_is_positive': monthly_surplus > 0
        }
    }
