"""Indian income tax calculator — New Tax Regime FY 2026-27.

Reads tax slab configuration from a versioned JSON config file.
All tax figures are deterministic — no AI involvement.
"""

import json
import os
from typing import Union


def load_config(config_source: Union[str, dict]) -> dict:
    """Load config from file path or return dict as-is."""
    if isinstance(config_source, dict):
        return config_source
    with open(config_source, 'r') as f:
        return json.load(f)


def calculate_tax(gross_income: float, config: Union[str, dict]) -> dict:
    """Calculate income tax under the New Tax Regime.

    Pipeline:
        gross_income
        → subtract standard_deduction → taxable_income
        → apply slabs → tax_before_cess
        → apply 87A rebate if eligible → tax_after_rebate
        → add 4% health & education cess → total_tax
        → gross_income - total_tax → net_income

    Args:
        gross_income: Annual gross income in INR.
        config: Path to tax config JSON or a config dict.

    Returns:
        Dict with keys: gross_income, standard_deduction, taxable_income,
        slab_breakdown (list of dicts with slab_range, taxable_in_slab, tax_in_slab),
        tax_before_cess, rebate_87a, tax_after_rebate, cess, total_tax,
        effective_rate_pct, net_annual_income, net_monthly_income.
    """
    cfg = load_config(config)
    slabs = cfg['slabs']
    std_ded = cfg['standard_deduction']
    cess_rate = cfg['cess_rate']
    rebate_cfg = cfg['rebate_87a']

    # Step 1: Taxable income
    taxable_income = max(0, gross_income - std_ded)

    # Step 2: Slab-wise tax calculation
    slab_breakdown = []
    remaining = taxable_income
    prev_limit = 0
    tax_before_cess = 0.0

    for slab in slabs:
        upper = slab['upto']  # None means unlimited
        rate = slab['rate']

        if upper is None:
            taxable_in_slab = remaining
        else:
            slab_width = upper - prev_limit
            taxable_in_slab = min(remaining, slab_width)

        tax_in_slab = taxable_in_slab * rate
        tax_before_cess += tax_in_slab

        if taxable_in_slab > 0:
            slab_range_str = f'{prev_limit:,.0f} and above' if upper is None else f'{prev_limit:,.0f} – {upper:,.0f}'
            slab_breakdown.append({
                'slab_range': slab_range_str,
                'rate_pct': rate * 100,
                'taxable_in_slab': round(taxable_in_slab, 2),
                'tax_in_slab': round(tax_in_slab, 2)
            })

        remaining -= taxable_in_slab
        if upper is not None:
            prev_limit = upper

        if remaining <= 0:
            break

    # Step 3: Section 87A rebate
    rebate_87a = 0.0
    if taxable_income <= rebate_cfg['max_taxable_income']:
        rebate_87a = min(tax_before_cess, rebate_cfg['max_rebate'])

    tax_after_rebate = max(0, tax_before_cess - rebate_87a)

    # Step 4: Health & Education Cess
    cess = round(tax_after_rebate * cess_rate, 2)
    total_tax = round(tax_after_rebate + cess, 2)

    # Step 5: Net income
    net_annual = round(gross_income - total_tax, 2)
    net_monthly = round(net_annual / 12, 2)

    effective_rate = round((total_tax / gross_income * 100), 2) if gross_income > 0 else 0.0

    return {
        'gross_income': gross_income,
        'standard_deduction': std_ded,
        'taxable_income': round(taxable_income, 2),
        'slab_breakdown': slab_breakdown,
        'tax_before_cess': round(tax_before_cess, 2),
        'rebate_87a': round(rebate_87a, 2),
        'tax_after_rebate': round(tax_after_rebate, 2),
        'cess': cess,
        'total_tax': total_tax,
        'effective_rate_pct': effective_rate,
        'net_annual_income': net_annual,
        'net_monthly_income': net_monthly
    }
