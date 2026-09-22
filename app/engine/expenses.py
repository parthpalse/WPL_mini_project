"""Expense aggregation — Essential, Discretionary, and Sinking Fund expenses.

Calculates monthly and annual expense totals with Decimal precision.
Zero external framework dependencies.
"""

from decimal import Decimal
from typing import Union, List, Dict, Optional, Any
from app.engine.money import to_decimal, round_inr
from app.engine.models import Expenses, ExpenseItem


def calculate_expenses(
    fixed: Optional[List[Dict]] = None,
    variable: Optional[List[Dict]] = None,
    expenses_obj: Optional[Expenses] = None
) -> Dict[str, Any]:
    """Aggregate expenses into essential, discretionary, and sinking funds.

    Backward-compatible with original (fixed, variable) inputs.
    """
    if expenses_obj is not None:
        items = expenses_obj.items
    else:
        items = []
        for f in (fixed or []):
            cat = f.get('category', 'essential')
            items.append(ExpenseItem(name=f.get('name', 'Fixed Expense'), amount=to_decimal(f.get('amount', 0)), category=cat))
        for v in (variable or []):
            cat = v.get('category', 'discretionary')
            items.append(ExpenseItem(name=v.get('name', 'Variable Expense'), amount=to_decimal(v.get('amount', 0)), category=cat))

    exp = Expenses(items=items)

    total_essential = exp.total_essential_monthly
    total_discretionary = exp.total_discretionary_monthly
    total_sinking = exp.total_sinking_fund_monthly
    total_monthly = exp.total_monthly
    total_annual = round_inr(total_monthly * Decimal('12'), places=2)

    # Calculate fixed vs variable for backward compatibility
    total_fixed = sum((to_decimal(f.get('amount', 0)) for f in (fixed or [])), Decimal('0.00'))
    total_variable = sum((to_decimal(v.get('amount', 0)) for v in (variable or [])), Decimal('0.00'))
    if not fixed and not variable:
        total_fixed = total_essential
        total_variable = total_discretionary + total_sinking

    return {
        'fixed_expenses': fixed or [],
        'variable_expenses': variable or [],
        'items': [{'name': i.name, 'amount': float(i.amount), 'category': i.category} for i in exp.items],
        'total_essential_monthly': float(round_inr(total_essential, 2)),
        'total_discretionary_monthly': float(round_inr(total_discretionary, 2)),
        'total_sinking_fund_monthly': float(round_inr(total_sinking, 2)),
        'total_fixed_monthly': float(round_inr(total_fixed, 2)),
        'total_variable_monthly': float(round_inr(total_variable, 2)),
        'total_monthly': float(round_inr(total_monthly, 2)),
        'total_annual': float(round_inr(total_annual, 2))
    }
