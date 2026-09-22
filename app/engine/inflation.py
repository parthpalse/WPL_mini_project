"""Inflation adjustment and financial projection utilities.

Implements standard Indian banking and investment projection formulas:
- Monthly SIP future value (annuity due compounding)
- Step-up SIP (annual % increment)
- Recurring Deposit (RD) with quarterly compounding (Indian banking standard)
- Fixed Deposit (FD) quarterly compounding and post-tax maturity
- Inflation-adjusted real values ("in today's rupees")
- 3 scenarios: Conservative, Base, Optimistic
- Fisher equation real return rate
"""

import json
from decimal import Decimal
from typing import Union, Dict, Any, List, Optional
from app.engine.money import to_decimal, round_inr, format_inr


def load_inflation_config(config_source: Union[str, dict, None] = None) -> dict:
    """Load inflation config from file or dict."""
    if isinstance(config_source, dict):
        return config_source
    if isinstance(config_source, str):
        with open(config_source, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"annual_rate_pct": 6.0}


def adjust_for_inflation(
    amount: Union[Decimal, float, int],
    years: Union[int, float],
    config: Union[str, dict, None] = None
) -> float:
    """Future cost of a today-rupee amount under inflation."""
    cfg = load_inflation_config(config)
    rate = to_decimal(cfg['annual_rate_pct']) / Decimal('100.0')
    amt = to_decimal(amount)
    fv = amt * ((Decimal('1.0') + rate) ** Decimal(str(years)))
    return float(round_inr(fv, places=2))


def real_value_in_todays_rupees(
    future_amount: Union[Decimal, float, int],
    years: Union[int, float],
    config: Union[str, dict, None] = None
) -> float:
    """Discount future rupees back to purchasing power in today's money."""
    cfg = load_inflation_config(config)
    rate = to_decimal(cfg['annual_rate_pct']) / Decimal('100.0')
    fv = to_decimal(future_amount)
    if years <= 0:
        return float(round_inr(fv, 2))
    discount_factor = (Decimal('1.0') + rate) ** Decimal(str(years))
    today_val = fv / discount_factor
    return float(round_inr(today_val, places=2))


def real_return(nominal_return_pct: float, config: Union[str, dict, None] = None) -> float:
    """Calculate real return using the Fisher equation: (1 + n) / (1 + i) - 1."""
    cfg = load_inflation_config(config)
    nominal = nominal_return_pct / 100.0
    inflation = cfg['annual_rate_pct'] / 100.0
    real = ((1.0 + nominal) / (1.0 + inflation)) - 1.0
    return round(real * 100.0, 4)


def calculate_sip_future_value(
    monthly_investment: Union[Decimal, float, int],
    annual_return_pct: float,
    tenure_months: int,
    step_up_pct: float = 0.0
) -> Dict[str, Any]:
    """Calculate future value of a monthly SIP (Annuity Due: invested at month start).
    
    Supports annual step-up percentage.
    """
    p_base = float(monthly_investment)
    r_monthly = (annual_return_pct / 100.0) / 12.0
    total_invested = 0.0
    future_value = 0.0

    for m in range(1, tenure_months + 1):
        year_index = (m - 1) // 12
        monthly_deposit = p_base * ((1.0 + (step_up_pct / 100.0)) ** year_index)
        total_invested += monthly_deposit
        months_remaining = tenure_months - m + 1
        if r_monthly > 0:
            future_value += monthly_deposit * ((1.0 + r_monthly) ** months_remaining)
        else:
            future_value += monthly_deposit

    wealth_gain = max(0.0, future_value - total_invested)
    return {
        'total_invested': round(total_invested, 2),
        'future_value': round(future_value, 2),
        'wealth_gain': round(wealth_gain, 2)
    }


def calculate_rd_maturity(
    monthly_deposit: Union[Decimal, float, int],
    annual_interest_pct: float,
    tenure_months: int
) -> Dict[str, Any]:
    """Calculate RD maturity value with quarterly compounding as per Indian banking rules."""
    p = float(monthly_deposit)
    r = annual_interest_pct / 100.0
    total_invested = p * tenure_months
    maturity_value = 0.0

    # Indian bank quarterly compounding for RD:
    # Each monthly deposit earns interest compounded quarterly for remaining quarters
    for m in range(1, tenure_months + 1):
        months_left = tenure_months - m + 1
        quarters = months_left / 3.0
        maturity_value += p * ((1.0 + (r / 4.0)) ** quarters)

    interest = max(0.0, maturity_value - total_invested)
    return {
        'total_invested': round(total_invested, 2),
        'maturity_value': round(maturity_value, 2),
        'interest_earned': round(interest, 2)
    }


def calculate_fd_maturity(
    principal: Union[Decimal, float, int],
    annual_interest_pct: float,
    tenure_months: int,
    marginal_tax_rate_pct: float = 0.0
) -> Dict[str, Any]:
    """Calculate FD maturity value with quarterly compounding and post-tax return."""
    p = float(principal)
    r = annual_interest_pct / 100.0
    years = tenure_months / 12.0
    quarters = tenure_months / 3.0

    pre_tax_maturity = p * ((1.0 + (r / 4.0)) ** quarters)
    gross_interest = pre_tax_maturity - p

    tax_on_interest = gross_interest * (marginal_tax_rate_pct / 100.0)
    post_tax_maturity = p + (gross_interest - tax_on_interest)

    return {
        'principal': round(p, 2),
        'pre_tax_maturity': round(pre_tax_maturity, 2),
        'gross_interest': round(gross_interest, 2),
        'tax_on_interest': round(tax_on_interest, 2),
        'post_tax_maturity': round(post_tax_maturity, 2)
    }


def project_goal(
    monthly_allocation: Union[Decimal, float, int],
    target_amount: Union[Decimal, float, int],
    horizon_months: int,
    product_type: str = "Equity Fund",
    marginal_tax_rate_pct: float = 0.0,
    inflation_config: Union[str, dict, None] = None
) -> Dict[str, Any]:
    """Project a financial goal under Conservative, Base, and Optimistic scenarios."""
    alloc = float(monthly_allocation)
    target = float(target_amount)
    years = horizon_months / 12.0

    # Rate bands per product
    rates = {
        "Equity Fund": {"conservative": 9.0, "base": 12.0, "optimistic": 15.0},
        "Debt Fund": {"conservative": 6.5, "base": 7.5, "optimistic": 8.5},
        "FD": {"conservative": 6.5, "base": 7.0, "optimistic": 7.5},
        "RD": {"conservative": 6.0, "base": 6.5, "optimistic": 7.0},
        "Savings": {"conservative": 3.0, "base": 3.5, "optimistic": 4.0},
    }.get(product_type, {"conservative": 7.0, "base": 10.0, "optimistic": 12.0})

    scenarios = {}
    for scenario_name, rate in rates.items():
        proj = calculate_sip_future_value(alloc, rate, horizon_months)
        nominal_fv = proj['future_value']
        real_fv = real_value_in_todays_rupees(nominal_fv, years, inflation_config)
        shortfall_nominal = target - nominal_fv
        shortfall_real = target - real_fv

        scenarios[scenario_name] = {
            'expected_return_pct': rate,
            'total_invested': proj['total_invested'],
            'nominal_future_value': nominal_fv,
            'real_future_value_in_todays_rupees': real_fv,
            'nominal_shortfall': max(0.0, shortfall_nominal),
            'real_shortfall': max(0.0, shortfall_real),
            'target_met_nominal': nominal_fv >= target,
            'target_met_real': real_fv >= target
        }

    return {
        'disclaimer': 'Illustrative projections based on historical return bands; not guaranteed financial advice.',
        'target_amount': target,
        'horizon_months': horizon_months,
        'horizon_years': round(years, 1),
        'product_type': product_type,
        'scenarios': scenarios
    }
