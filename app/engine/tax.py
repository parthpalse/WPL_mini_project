"""Indian income tax calculator — Supports both New and Old Tax Regimes.

Config-driven, deterministic, pure Python using Decimal.
Handles:
- Slab calculation
- Section 87A rebate WITH marginal relief (no cliff edges)
- Surcharge tiers WITH marginal relief
- Health & Education Cess (4%)
- Old vs. New regime comparison and recommendation
- Marginal tax rate calculation for optimizer
- Traceable CalcStep generation
"""

import json
from decimal import Decimal
from typing import Union, Dict, Any, List, Optional
from app.engine.money import to_decimal, round_inr
from app.engine.models import CalcStep, TaxDeductions


def load_config(config_source: Union[str, dict]) -> dict:
    """Load config from file path or return dict as-is."""
    if isinstance(config_source, dict):
        return config_source
    with open(config_source, 'r', encoding='utf-8') as f:
        return json.load(f)


def _compute_slab_tax(taxable_income: Decimal, slabs: List[Dict[str, Any]]) -> tuple[Decimal, List[Dict[str, Any]], Decimal]:
    """Compute base slab tax and marginal slab rate."""
    tax_before_cess = Decimal('0.00')
    slab_breakdown = []
    remaining = taxable_income
    prev_limit = Decimal('0.00')
    marginal_slab_rate = Decimal('0.00')

    for slab in slabs:
        upper = to_decimal(slab['upto']) if slab['upto'] is not None else None
        rate = to_decimal(slab['rate'])

        if upper is None:
            taxable_in_slab = max(Decimal('0.00'), remaining)
        else:
            slab_width = max(Decimal('0.00'), upper - prev_limit)
            taxable_in_slab = min(remaining, slab_width)

        if taxable_in_slab > Decimal('0.00'):
            tax_in_slab = round_inr(taxable_in_slab * rate, places=2)
            tax_before_cess += tax_in_slab
            marginal_slab_rate = rate

            slab_range_str = f'{prev_limit:,.0f} and above' if upper is None else f'{prev_limit:,.0f} – {upper:,.0f}'
            slab_breakdown.append({
                'slab_range': slab_range_str,
                'rate_pct': float(rate * 100),
                'taxable_in_slab': float(taxable_in_slab),
                'tax_in_slab': float(tax_in_slab)
            })

            remaining -= taxable_in_slab

        if upper is not None:
            prev_limit = upper

        if remaining <= Decimal('0.00'):
            break

    return tax_before_cess, slab_breakdown, marginal_slab_rate


def _compute_surcharge(
    taxable_income: Decimal,
    base_tax: Decimal,
    surcharge_tiers: List[Dict[str, Any]],
    slabs: List[Dict[str, Any]]
) -> tuple[Decimal, Decimal]:
    """Compute surcharge with marginal relief.
    
    Marginal relief ensures:
    tax + surcharge <= tax_at_threshold + (taxable_income - threshold)
    """
    applicable_tier = None
    # Find highest applicable tier
    for tier in sorted(surcharge_tiers, key=lambda t: to_decimal(t['threshold'])):
        threshold = to_decimal(tier['threshold'])
        if taxable_income > threshold:
            applicable_tier = tier

    if not applicable_tier:
        return Decimal('0.00'), Decimal('0.00')

    rate = to_decimal(applicable_tier['rate'])
    threshold = to_decimal(applicable_tier['threshold'])
    raw_surcharge = round_inr(base_tax * rate, places=2)

    # Calculate tax on threshold income
    tax_at_threshold, _, _ = _compute_slab_tax(threshold, slabs)
    excess_income = taxable_income - threshold

    # Cap: total tax + surcharge cannot exceed tax_at_threshold + excess_income
    max_total_tax_and_surcharge = tax_at_threshold + excess_income
    if (base_tax + raw_surcharge) > max_total_tax_and_surcharge:
        surcharge = max(Decimal('0.00'), max_total_tax_and_surcharge - base_tax)
    else:
        surcharge = raw_surcharge

    return surcharge, rate


def calculate_tax_regime(
    gross_income: Union[Decimal, float, int],
    regime: str,
    config: Union[str, dict],
    deductions: Optional[TaxDeductions] = None
) -> Dict[str, Any]:
    """Calculate tax for a specific regime ('new' or 'old')."""
    cfg = load_config(config)
    regime_key = 'new_regime' if regime == 'new' else 'old_regime'
    reg_cfg = cfg.get(regime_key)
    
    # Fallback for flat legacy config
    if not reg_cfg and regime == 'new':
        reg_cfg = cfg
    elif not reg_cfg and regime == 'old':
        reg_cfg = {
            'standard_deduction': 50000,
            'slabs': [
                {'upto': 250000, 'rate': 0.0},
                {'upto': 500000, 'rate': 0.05},
                {'upto': 1000000, 'rate': 0.20},
                {'upto': None, 'rate': 0.30}
            ],
            'rebate_87a': {'max_taxable_income': 500000, 'max_rebate': 12500, 'marginal_relief': False},
            'caps': {'sec_80c': 150000, 'sec_80ccd_1b': 50000, 'sec_24b': 200000, 'sec_80d': 25000}
        }

    gross = to_decimal(gross_income)
    std_ded = to_decimal(reg_cfg.get('standard_deduction', 0))
    slabs = reg_cfg['slabs']
    rebate_cfg = reg_cfg.get('rebate_87a', {})
    surcharge_tiers = reg_cfg.get('surcharge', [])
    cess_rate = to_decimal(cfg.get('cess_rate', '0.04'))

    steps: List[CalcStep] = []

    # Step 1: Standard Deduction & Deductions
    total_deductions = std_ded
    deduction_details = {'standard_deduction': float(std_ded)}

    if deductions and regime == 'old':
        caps = reg_cfg.get('caps', {})
        sec_80c = min(deductions.sec_80c, to_decimal(caps.get('sec_80c', 150000)))
        sec_80d = min(deductions.sec_80d, to_decimal(caps.get('sec_80d', 25000)))
        sec_80ccd_1b = min(deductions.sec_80ccd_1b, to_decimal(caps.get('sec_80ccd_1b', 50000)))
        sec_24b = min(deductions.home_loan_interest_24b, to_decimal(caps.get('sec_24b', 200000)))
        hra = deductions.hra_exemption
        employer_nps = deductions.employer_nps_80ccd_2

        additional = sec_80c + sec_80d + sec_80ccd_1b + sec_24b + hra + employer_nps
        total_deductions += additional
        deduction_details.update({
            'sec_80c': float(sec_80c),
            'sec_80d': float(sec_80d),
            'sec_80ccd_1b': float(sec_80ccd_1b),
            'sec_24b': float(sec_24b),
            'hra_exemption': float(hra),
            'employer_nps': float(employer_nps)
        })
    elif deductions and regime == 'new':
        # New regime allows employer NPS contribution (80CCD(2))
        employer_nps = deductions.employer_nps_80ccd_2
        total_deductions += employer_nps
        deduction_details['employer_nps'] = float(employer_nps)

    taxable_income = max(Decimal('0.00'), gross - total_deductions)
    steps.append(CalcStep(
        step_id="taxable_income",
        label=f"Taxable Income ({regime.capitalize()} Regime)",
        formula="Gross Income - Deductions",
        inputs={"gross_income": gross, "deductions": total_deductions},
        result=taxable_income,
        note=f"Computed after standard deduction of ₹{std_ded:,.0f} and applicable chapter VI-A deductions.",
        category="tax"
    ))

    # Step 2: Slabs
    tax_before_cess, slab_breakdown, marginal_slab_rate = _compute_slab_tax(taxable_income, slabs)

    # Step 3: Section 87A Rebate WITH Marginal Relief
    rebate_87a = Decimal('0.00')
    max_taxable_for_rebate = to_decimal(rebate_cfg.get('max_taxable_income', 0))
    max_rebate = to_decimal(rebate_cfg.get('max_rebate', 0))
    marginal_relief_active = False

    if taxable_income <= max_taxable_for_rebate:
        rebate_87a = min(tax_before_cess, max_rebate)
        tax_after_rebate = max(Decimal('0.00'), tax_before_cess - rebate_87a)
    elif rebate_cfg.get('marginal_relief', False):
        # Marginal relief under Section 87A proviso:
        # Tax payable cannot exceed (taxable_income - max_taxable_for_rebate)
        excess_income = taxable_income - max_taxable_for_rebate
        if tax_before_cess > excess_income:
            marginal_relief_active = True
            rebate_87a = tax_before_cess - excess_income
            tax_after_rebate = excess_income
        else:
            tax_after_rebate = tax_before_cess
    else:
        tax_after_rebate = tax_before_cess

    steps.append(CalcStep(
        step_id="rebate_87a",
        label="Section 87A Rebate & Relief",
        formula="min(tax, rebate_limit) or marginal relief cap",
        inputs={"tax_before_cess": tax_before_cess, "taxable_income": taxable_income},
        result=rebate_87a,
        note="Marginal relief applied to eliminate cliff edge." if marginal_relief_active else "Full rebate applied." if rebate_87a > 0 else "Not eligible for Section 87A rebate.",
        category="tax"
    ))

    # Step 4: Surcharge with Marginal Relief
    surcharge, surcharge_rate = _compute_surcharge(taxable_income, tax_after_rebate, surcharge_tiers, slabs)

    # Step 5: Health & Education Cess
    tax_subject_to_cess = tax_after_rebate + surcharge
    cess = round_inr(tax_subject_to_cess * cess_rate, places=2)
    total_tax = tax_subject_to_cess + cess

    # Marginal Tax Rate (Rate applied to the very next rupee)
    if marginal_relief_active:
        marginal_tax_rate = Decimal('1.00') * (Decimal('1.00') + cess_rate)  # 100% of excess + cess
    elif taxable_income <= max_taxable_for_rebate and rebate_87a > 0:
        marginal_tax_rate = Decimal('0.00')
    else:
        marginal_tax_rate = (marginal_slab_rate * (Decimal('1.00') + surcharge_rate)) * (Decimal('1.00') + cess_rate)

    net_annual = max(Decimal('0.00'), gross - total_tax)
    net_monthly = round_inr(net_annual / Decimal('12'), places=2)
    effective_rate = round_inr((total_tax / gross * Decimal('100')) if gross > 0 else Decimal('0.00'), places=2)

    return {
        'regime': regime,
        'gross_income': float(gross),
        'standard_deduction': float(std_ded),
        'deductions': deduction_details,
        'taxable_income': float(taxable_income),
        'slab_breakdown': slab_breakdown,
        'tax_before_cess': float(tax_before_cess),
        'rebate_87a': float(rebate_87a),
        'tax_after_rebate': float(tax_after_rebate),
        'surcharge': float(surcharge),
        'cess': float(cess),
        'total_tax': float(total_tax),
        'effective_rate_pct': float(effective_rate),
        'marginal_rate_pct': float(round_inr(marginal_tax_rate * Decimal('100'), places=2)),
        'net_annual_income': float(net_annual),
        'net_monthly_income': float(net_monthly),
        'steps': [s.to_dict() for s in steps]
    }


def calculate_tax(
    gross_income: Union[Decimal, float, int],
    config: Union[str, dict],
    regime_preference: str = 'new',
    deductions: Optional[TaxDeductions] = None
) -> Dict[str, Any]:
    """Calculate tax under requested regime, or compare both if 'auto'."""
    cfg = load_config(config)
    
    if regime_preference in ('new', 'old'):
        result = calculate_tax_regime(gross_income, regime_preference, cfg, deductions)
        result['recommended_regime'] = regime_preference
        result['regime_comparison'] = None
        return result

    # Auto mode: calculate both and recommend lower
    new_res = calculate_tax_regime(gross_income, 'new', cfg, deductions)
    old_res = calculate_tax_regime(gross_income, 'old', cfg, deductions)

    if new_res['total_tax'] <= old_res['total_tax']:
        recommended = new_res
        lower_regime = 'new'
        diff = old_res['total_tax'] - new_res['total_tax']
    else:
        recommended = old_res
        lower_regime = 'old'
        diff = new_res['total_tax'] - old_res['total_tax']

    recommended['recommended_regime'] = lower_regime
    recommended['regime_comparison'] = {
        'new_tax': new_res['total_tax'],
        'old_tax': old_res['total_tax'],
        'tax_savings': float(diff),
        'recommendation_note': f"Save ₹{diff:,.0f} by choosing the {lower_regime.upper()} regime." if diff > 0 else "Both regimes result in the same tax."
    }
    return recommended
