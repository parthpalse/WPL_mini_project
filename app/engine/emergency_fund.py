"""Emergency fund calculator.

Computes target emergency fund (default 6 months of expenses),
current shortfall, and required monthly contribution to reach target.
"""

import math


def calculate_emergency_fund(
    monthly_expenses: float,
    existing_fund: float = 0.0,
    target_months: int = 6,
    contribution_period_months: int = 12
) -> dict:
    """Calculate emergency fund target, shortfall, and monthly contribution.

    Args:
        monthly_expenses: Total monthly expenses in INR.
        existing_fund: Current emergency fund balance.
        target_months: Number of months of expenses to target (default 6).
        contribution_period_months: Period over which to build up shortfall (default 12).

    Returns:
        Dict with keys: target, existing, shortfall,
        monthly_contribution, months_to_target, fully_funded.
    """
    target = round(monthly_expenses * target_months, 2)
    shortfall = round(max(0, target - existing_fund), 2)
    fully_funded = shortfall <= 0

    if fully_funded:
        monthly_contribution = 0.0
        months_to_target = 0
    else:
        monthly_contribution = round(shortfall / contribution_period_months, 2)
        months_to_target = contribution_period_months

    return {
        'target': target,
        'existing': existing_fund,
        'shortfall': shortfall,
        'monthly_contribution': monthly_contribution,
        'months_to_target': months_to_target,
        'fully_funded': fully_funded
    }
