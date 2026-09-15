"""Inflation adjustment utilities.

Provides future value calculation and real return computation
using a static inflation assumption from config.
"""

import json
from typing import Union


def load_inflation_config(config_source: Union[str, dict]) -> dict:
    """Load inflation config from file path or return dict as-is."""
    if isinstance(config_source, dict):
        return config_source
    with open(config_source, 'r') as f:
        return json.load(f)


def adjust_for_inflation(
    amount: float,
    years: int,
    config: Union[str, dict]
) -> float:
    """Calculate the future value of an amount adjusted for inflation.

    Args:
        amount: Current amount in INR.
        years: Number of years into the future.
        config: Path to inflation config JSON or a config dict.

    Returns:
        Inflation-adjusted future value.
    """
    cfg = load_inflation_config(config)
    rate = cfg['annual_rate_pct'] / 100
    return round(amount * ((1 + rate) ** years), 2)


def real_return(nominal_return_pct: float, config: Union[str, dict]) -> float:
    """Calculate the real (inflation-adjusted) return rate.

    Uses the Fisher equation: (1 + nominal) / (1 + inflation) - 1

    Args:
        nominal_return_pct: Nominal return percentage (e.g., 12.0 for 12%).
        config: Path to inflation config JSON or a config dict.

    Returns:
        Real return as a percentage.
    """
    cfg = load_inflation_config(config)
    nominal = nominal_return_pct / 100
    inflation = cfg['annual_rate_pct'] / 100
    real = ((1 + nominal) / (1 + inflation)) - 1
    return round(real * 100, 4)
