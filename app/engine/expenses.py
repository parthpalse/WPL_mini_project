"""Expense aggregation — fixed and variable expenses.

Aggregates user-provided expense items into monthly and annual totals.
"""


def calculate_expenses(
    fixed: list[dict] | None = None,
    variable: list[dict] | None = None
) -> dict:
    """Aggregate fixed and variable expenses.

    Each expense item is a dict with:
        - 'name': str (e.g., 'Rent', 'Groceries')
        - 'amount': float (monthly amount in INR)

    Args:
        fixed: List of fixed expense dicts (rent, EMIs, insurance, etc.).
        variable: List of variable expense dicts (food, transport, etc.).

    Returns:
        Dict with keys: fixed_expenses (list), variable_expenses (list),
        total_fixed_monthly, total_variable_monthly, total_monthly, total_annual.
    """
    fixed = fixed or []
    variable = variable or []

    total_fixed = sum(item.get('amount', 0) for item in fixed)
    total_variable = sum(item.get('amount', 0) for item in variable)
    total_monthly = total_fixed + total_variable

    return {
        'fixed_expenses': fixed,
        'variable_expenses': variable,
        'total_fixed_monthly': round(total_fixed, 2),
        'total_variable_monthly': round(total_variable, 2),
        'total_monthly': round(total_monthly, 2),
        'total_annual': round(total_monthly * 12, 2)
    }
