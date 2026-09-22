"""Deterministic investment allocation optimizer.

Allocates monthly investable surplus across financial products
(Savings, RD, FD, Debt Fund, Equity Fund) based on:
- Post-tax expected returns (adjusted by user's marginal tax rate)
- Goal time horizons and glide paths
- Risk profile (Safe, Balanced, Growth or 1-10 numerical score)
- Liquidity requirements
- Diversification caps (prevents single-product 100% collapse)

Provides Scipy linear programming optimization with rule-based fallback
and explains the financial reasoning behind each allocation.
"""

import json
from decimal import Decimal
from typing import Union, Dict, Any, List, Optional
import numpy as np
from scipy.optimize import linprog

from app.engine.money import to_decimal, round_inr, format_inr
from app.engine.emergency_fund import load_planning_rules


def load_product_config(config_source: Union[str, dict, None] = None) -> dict:
    """Load product configuration from file or dict."""
    if isinstance(config_source, dict):
        return config_source
    if isinstance(config_source, str):
        with open(config_source, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Default snapshot
    return {
        "products": [
            {"name": "Savings", "return_pct": 3.5, "risk": "very_low", "liquidity": "high", "tax_treatment": "slab", "min_allocation_pct": 5.0, "max_allocation_pct": 50.0},
            {"name": "RD", "return_pct": 6.5, "risk": "low", "liquidity": "medium", "tax_treatment": "slab", "min_allocation_pct": 0.0, "max_allocation_pct": 50.0},
            {"name": "FD", "return_pct": 7.0, "risk": "low", "liquidity": "low_medium", "tax_treatment": "slab", "min_allocation_pct": 0.0, "max_allocation_pct": 60.0},
            {"name": "Debt Fund", "return_pct": 7.5, "risk": "moderate", "liquidity": "medium_high", "tax_treatment": "slab", "min_allocation_pct": 0.0, "max_allocation_pct": 60.0},
            {"name": "Equity Fund", "return_pct": 12.0, "risk": "high", "liquidity": "high", "tax_treatment": "equity_capital_gains", "min_allocation_pct": 0.0, "max_allocation_pct": 75.0}
        ]
    }


def compute_post_tax_return(
    nominal_return_pct: float,
    tax_treatment: str,
    marginal_tax_rate_pct: float
) -> float:
    """Calculate post-tax expected return based on tax treatment and marginal tax slab."""
    if tax_treatment == "slab":
        # Interest and debt gains taxed at user's marginal slab
        slab_tax = marginal_tax_rate_pct / 100.0
        return max(0.0, nominal_return_pct * (1.0 - slab_tax))
    elif tax_treatment == "equity_capital_gains":
        # Equity LTCG taxed at 12.5% (approx)
        return max(0.0, nominal_return_pct * (1.0 - 0.125))
    return nominal_return_pct


def get_horizon_eligibility(goal_horizon_months: Optional[int]) -> Dict[str, float]:
    """Return max allowable equity and product constraints based on glide path horizon."""
    if goal_horizon_months is None:
        return {'max_equity': 1.0, 'allow_fd': True, 'allow_rd': True}

    if goal_horizon_months < 12:
        # Ultra short term (<1 yr): 0% Equity, liquid/short FD only
        return {'max_equity': 0.0, 'max_fd': 0.50, 'max_debt': 0.0, 'allow_rd': False}
    elif goal_horizon_months <= 36:
        # Short term (1-3 yrs): Max 15% equity, debt & RD/FD focus
        return {'max_equity': 0.15, 'max_fd': 0.60, 'max_debt': 0.50, 'allow_rd': True}
    elif goal_horizon_months <= 60:
        # Medium term (3-5 yrs): Max 40% equity
        return {'max_equity': 0.40, 'max_fd': 0.50, 'max_debt': 0.60, 'allow_rd': True}
    else:
        # Long term (5+ yrs): Full equity participation allowed
        return {'max_equity': 0.80, 'max_fd': 0.50, 'max_debt': 0.50, 'allow_rd': True}


def optimize_allocation(
    monthly_surplus: Union[Decimal, float, int],
    risk_score: int = 5,
    liquidity_need: str = 'medium',
    goal_horizons: Optional[List[int]] = None,
    marginal_tax_rate_pct: float = 0.0,
    product_config: Union[str, dict, None] = None,
    rules_config: Union[str, dict, None] = None
) -> Dict[str, Any]:
    """Optimize monthly surplus allocation across Safe, Balanced, and Growth strategies."""
    surplus_d = to_decimal(monthly_surplus)
    if surplus_d <= Decimal('0.00'):
        return {'safe': {}, 'balanced': {}, 'growth': {}}

    cfg = load_product_config(product_config)
    products = cfg.get('products', [])
    if not products:
        return {'safe': {}, 'balanced': {}, 'growth': {}}

    rules = load_planning_rules(rules_config)
    caps = rules.get('diversification_caps', {})
    max_single_product = caps.get('max_single_product_pct', 60.0) / 100.0

    # Shortest horizon drives liquidity constraints
    min_horizon = min(goal_horizons) if goal_horizons else None
    horizon_rules = get_horizon_eligibility(min_horizon)

    names = [p['name'] for p in products]
    nominal_returns = [p['return_pct'] for p in products]
    post_tax_returns = np.array([
        compute_post_tax_return(p['return_pct'], p.get('tax_treatment', 'slab'), marginal_tax_rate_pct) / 100.0
        for p in products
    ])

    risk_map = {'very_low': 1, 'low': 2, 'moderate': 3, 'high': 4}
    risks = np.array([risk_map.get(p.get('risk', 'moderate'), 3) for p in products])

    # Linear objective: Maximize return -> Minimize negative post-tax return
    c = -post_tax_returns
    A_eq = np.ones((1, len(products)))
    b_eq = np.array([1.0])

    def solve_strategy(max_avg_risk: float, max_equity_weight: float, strategy_name: str) -> Dict[str, Any]:
        # Enforce horizon glide path
        effective_equity_cap = min(max_equity_weight, horizon_rules.get('max_equity', 1.0))

        # Risk constraint
        A_ub = [risks]
        b_ub = [max_avg_risk]

        # Product bounds
        bounds = []
        for p in products:
            p_name = p['name']
            cfg_min = p.get('min_allocation_pct', 0.0) / 100.0
            cfg_max = min(max_single_product, p.get('max_allocation_pct', 100.0) / 100.0)

            if p.get('risk') == 'high' or p_name == 'Equity Fund':
                upper = min(cfg_max, effective_equity_cap)
                bounds.append((0.0, upper))
            elif p_name == 'Savings' and liquidity_need == 'high':
                bounds.append((max(cfg_min, 0.15), cfg_max))
            else:
                bounds.append((cfg_min, cfg_max))

        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

        if not res.success:
            # Rule-based fallback
            if strategy_name == 'safe':
                weights = [0.20, 0.40, 0.40, 0.0, 0.0]
            elif strategy_name == 'balanced':
                weights = [0.10, 0.20, 0.30, 0.20, 0.20]
            else:
                weights = [0.05, 0.05, 0.10, 0.30, 0.50]
        else:
            weights = list(res.x)

        # Normalize weights to exactly 1.0
        total_w = sum(weights)
        if total_w > 0:
            weights = [w / total_w for w in weights]

        # Allocate amounts in Decimal and ensure exact sum == surplus_d
        allocation: Dict[str, Any] = {}
        running_allocated = Decimal('0.00')
        highest_prod = None
        highest_prod_amount = Decimal('0.00')

        for i, name in enumerate(names):
            w = weights[i]
            if w > 0.005:  # Over 0.5%
                pct = round(w * 100.0, 1)
                amt = round_inr(surplus_d * Decimal(str(w)), places=2)
                running_allocated += amt
                if amt > highest_prod_amount:
                    highest_prod_amount = amt
                    highest_prod = name

                # Reason for allocation
                reason = _generate_reason(name, pct, strategy_name, min_horizon, marginal_tax_rate_pct)
                allocation[name] = {
                    'percentage': pct,
                    'amount': float(amt),
                    'formatted_amount': format_inr(amt),
                    'reason': reason
                }

        # Fix rounding difference on highest product to guarantee invariant
        rounding_delta = surplus_d - running_allocated
        if rounding_delta != Decimal('0.00') and highest_prod in allocation:
            adjusted_amt = to_decimal(allocation[highest_prod]['amount']) + rounding_delta
            allocation[highest_prod]['amount'] = float(round_inr(adjusted_amt, 2))
            allocation[highest_prod]['formatted_amount'] = format_inr(adjusted_amt)

        return allocation

    return {
        'safe': solve_strategy(max_avg_risk=2.0, max_equity_weight=0.0, strategy_name='safe'),
        'balanced': solve_strategy(max_avg_risk=2.8, max_equity_weight=0.40, strategy_name='balanced'),
        'growth': solve_strategy(max_avg_risk=3.5, max_equity_weight=0.75, strategy_name='growth')
    }


def _generate_reason(product: str, pct: float, strategy: str, horizon_months: Optional[int], tax_rate: float) -> str:
    """Generate plain-English justification for allocation."""
    if product == "Savings":
        return f"{pct}% allocated for instant liquidity and emergency cash needs."
    elif product == "RD":
        return f"{pct}% allocated for disciplined recurring fixed-income savings."
    elif product == "FD":
        return f"{pct}% allocated for guaranteed capital preservation."
    elif product == "Debt Fund":
        return f"{pct}% allocated for higher post-tax fixed income efficiency."
    elif product == "Equity Fund":
        return f"{pct}% allocated to build long-term wealth and outpace inflation."
    return f"{pct}% allocation in {product}."
