"""Emergency fund calculator.

Determines target emergency fund based on income stability, household dependents,
and essential outflows (essential living expenses + debt EMIs).
Uses Decimal precision and config-driven parameters.
"""

import json
import math
from decimal import Decimal
from typing import Union, Dict, Any, Optional
from app.engine.money import to_decimal, round_inr
from app.engine.models import CalcStep, UserProfile


def load_planning_rules(config_source: Union[str, dict, None] = None) -> dict:
    """Load planning rules config from file or return dict."""
    if isinstance(config_source, dict):
        return config_source
    if isinstance(config_source, str):
        with open(config_source, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Default fallback rules
    return {}


def determine_target_months(
    profile: Optional[UserProfile] = None,
    rules: Optional[Dict] = None,
    target_months_override: Optional[int] = None
) -> int:
    """Determine target months based on employment type, income stability, and dependents."""
    if target_months_override is not None:
        return target_months_override

    ef_rules = (rules or {}).get('emergency_fund', {})
    if not profile:
        return 6

    base_map = ef_rules.get('base_months', {})
    key = f"{profile.employment_type}_{profile.income_stability}"
    base = base_map.get(key, 6)
    
    addon = profile.dependents * ef_rules.get('dependent_addon_months', 1)
    target = base + addon
    min_m = ef_rules.get('min_months', 3)
    max_m = ef_rules.get('max_months', 12)
    return max(min_m, min(max_m, target))


def calculate_emergency_fund(
    monthly_expenses: Union[Decimal, float, int],
    existing_fund: Union[Decimal, float, int] = 0.0,
    target_months: Optional[int] = None,
    monthly_debt_payments: Union[Decimal, float, int] = 0.0,
    contribution_period_months: int = 12,
    profile: Optional[UserProfile] = None,
    rules_config: Union[str, dict, None] = None,
    available_monthly_capacity: Optional[Union[Decimal, float, int]] = None
) -> Dict[str, Any]:
    """Calculate emergency fund target, shortfall, and required monthly allocation.

    Essential monthly commitments = monthly_expenses + monthly_debt_payments.
    """
    rules = load_planning_rules(rules_config)
    resolved_target_months = determine_target_months(profile, rules, target_months)
    
    expenses_d = to_decimal(monthly_expenses)
    debt_d = to_decimal(monthly_debt_payments)
    existing_d = to_decimal(existing_fund)
    
    # Base target on essential monthly commitments (expenses + EMIs)
    monthly_commitment = expenses_d + debt_d
    target = round_inr(monthly_commitment * Decimal(resolved_target_months), places=2)
    shortfall = max(Decimal('0.00'), target - existing_d)
    fully_funded = shortfall <= Decimal('0.00')

    # Monthly contribution planning
    period = max(1, contribution_period_months)
    if fully_funded:
        monthly_contribution = Decimal('0.00')
        months_to_target = 0
    else:
        monthly_contribution = round_inr(shortfall / Decimal(period), places=2)
        if available_monthly_capacity is not None and to_decimal(available_monthly_capacity) > 0:
            months_to_target = math.ceil(float(shortfall / to_decimal(available_monthly_capacity)))
        else:
            months_to_target = period

    step = CalcStep(
        step_id="emergency_fund",
        label=f"Emergency Fund Target ({resolved_target_months} Months)",
        formula="(Monthly Expenses + Debt EMIs) * Target Months",
        inputs={
            "monthly_commitment": monthly_commitment,
            "target_months": resolved_target_months,
            "existing_fund": existing_d
        },
        result=target,
        note=f"Target ₹{target:,.0f} covers {resolved_target_months} months of essential commitments. Shortfall: ₹{shortfall:,.0f}.",
        category="emergency_fund"
    )

    return {
        'target': float(target),
        'existing': float(existing_d),
        'shortfall': float(shortfall),
        'target_months': resolved_target_months,
        'monthly_contribution': float(monthly_contribution),
        'months_to_target': months_to_target,
        'fully_funded': fully_funded,
        'step': step.to_dict()
    }
