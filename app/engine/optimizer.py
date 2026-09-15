"""Investment allocation optimizer.

Allocates surplus across financial products (Savings, RD, FD, Debt Fund, Equity Fund)
into Safe, Balanced, and Growth strategies using linear programming.
"""

import json
from typing import Union
import numpy as np
from scipy.optimize import linprog


def load_config(config_source: Union[str, dict]) -> dict:
    """Load config from file path or return dict as-is."""
    if isinstance(config_source, dict):
        return config_source
    with open(config_source, 'r') as f:
        return json.load(f)


def optimize_allocation(
    monthly_surplus: float,
    risk_score: int = 5,
    liquidity_need: str = 'medium',
    goal_horizons: list[int] | None = None,
    product_config: Union[str, dict] = None
) -> dict:
    """Optimize allocation across financial products.

    Args:
        monthly_surplus: Amount to invest monthly.
        risk_score: User's risk tolerance (1-10).
        liquidity_need: User's liquidity requirement ('low', 'medium', 'high').
        goal_horizons: List of years until goals.
        product_config: Path to product config JSON or dict.

    Returns:
        Dict with safe, balanced, growth allocation strategies.
    """
    if monthly_surplus <= 0:
        return {
            'safe': {},
            'balanced': {},
            'growth': {}
        }

    cfg = load_config(product_config)
    products = cfg.get('products', [])
    
    if not products:
        return {}

    names = [p['name'] for p in products]
    returns = np.array([p['return_pct'] / 100.0 for p in products])
    
    # Map risk strings to numerical values (lower is safer)
    risk_map = {'very_low': 1, 'low': 2, 'moderate': 3, 'high': 4}
    risks = np.array([risk_map.get(p.get('risk', 'moderate'), 3) for p in products])
    
    # Objective: Maximize return -> Minimize negative return
    c = -returns
    
    # Equality constraint: sum of weights = 1
    A_eq = np.ones((1, len(products)))
    b_eq = np.array([1.0])
    
    # Helper to run linprog with specific risk constraints
    def solve_for_strategy(max_avg_risk, max_equity_weight):
        # Inequality constraint 1: Average risk <= max_avg_risk
        # sum(w_i * risk_i) <= max_avg_risk -> A_ub * w <= b_ub
        A_ub = [risks]
        b_ub = [max_avg_risk]
        
        # Bounds for each weight: 0 to 1, but equity is capped
        bounds = []
        for p in products:
            if p.get('risk') == 'high':
                bounds.append((0, max_equity_weight))
            else:
                bounds.append((0, 1))
                
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        
        if res.success:
            weights = res.x
            # Convert to monetary amounts and percentages
            allocation = {}
            for i, name in enumerate(names):
                weight = float(weights[i])
                if weight > 0.001:  # Ignore tiny allocations
                    allocation[name] = {
                        'percentage': round(weight * 100, 1),
                        'amount': round(weight * monthly_surplus, 2)
                    }
            return allocation
        else:
            # Fallback simple allocation if LP fails
            return {names[0]: {'percentage': 100.0, 'amount': round(monthly_surplus, 2)}}

    # Define constraints for the 3 strategies
    # Safe: max avg risk 2.0, max equity 0%
    safe_allocation = solve_for_strategy(max_avg_risk=2.0, max_equity_weight=0.0)
    
    # Balanced: max avg risk 2.8, max equity 40%
    balanced_allocation = solve_for_strategy(max_avg_risk=2.8, max_equity_weight=0.4)
    
    # Growth: max avg risk 3.5, max equity 80%
    growth_allocation = solve_for_strategy(max_avg_risk=3.5, max_equity_weight=0.8)

    return {
        'safe': safe_allocation,
        'balanced': balanced_allocation,
        'growth': growth_allocation
    }
