"""Maximum investable surplus calculator.

Implements the explicit, traceable Step A through Step I surplus pipeline:
Step A: Gross Income -> Tax -> Net Monthly In-hand
Step B: Subtract mandatory payslip deductions (EPF, PT)
Step C: Subtract essential living expenses
Step D: Subtract minimum debt payments (EMIs)
Step E: Subtract irregular-expense sinking fund (annual costs / 12)
Step F: Subtract safety buffer (config %)
Step G: Investable capacity before priorities
Step H: Priority allocations (Emergency Fund -> High-interest Debt -> Goals)
Step I: Discretionary spending what-if scenarios

Produces a structured CalcStep trace for every calculation.
Handles deficit scenarios with explicit recovery levers.
"""

import json
from decimal import Decimal
from typing import Union, List, Dict, Any, Optional
from app.engine.money import to_decimal, round_inr, format_inr
from app.engine.models import (
    CalcStep, UserProfile, Income, Expenses, ExpenseItem,
    DebtItem, TaxDeductions
)
from app.engine.tax import calculate_tax
from app.engine.expenses import calculate_expenses
from app.engine.emergency_fund import calculate_emergency_fund, load_planning_rules


def calculate_surplus(
    gross_income: Union[Decimal, float, int, Income],
    fixed_expenses: Optional[List[Dict]] = None,
    variable_expenses: Optional[List[Dict]] = None,
    expenses_obj: Optional[Expenses] = None,
    debts: Optional[List[DebtItem]] = None,
    monthly_debt_payments: Union[Decimal, float, int] = 0.0,
    existing_emergency_fund: Union[Decimal, float, int] = 0.0,
    emergency_fund_months: Optional[int] = None,
    user_profile: Optional[UserProfile] = None,
    tax_config: Union[str, dict, None] = None,
    rules_config: Union[str, dict, None] = None,
    regime_preference: str = 'auto',
    deductions: Optional[TaxDeductions] = None
) -> Dict[str, Any]:
    """Execute the full deterministic surplus pipeline with traceable CalcSteps."""
    rules = load_planning_rules(rules_config)
    steps: List[CalcStep] = []

    # Parse Income
    if isinstance(gross_income, Income):
        inc = gross_income
    else:
        inc = Income(gross_annual=to_decimal(gross_income))

    # Parse Expenses
    exp_res = calculate_expenses(fixed_expenses, variable_expenses, expenses_obj)
    essential_expenses_m = to_decimal(exp_res['total_essential_monthly'])
    discretionary_expenses_m = to_decimal(exp_res['total_discretionary_monthly'])
    sinking_fund_m = to_decimal(exp_res['total_sinking_fund_monthly'])
    total_expenses_m = to_decimal(exp_res['total_monthly'])

    # Parse Debts
    resolved_debts: List[DebtItem] = debts or []
    if not resolved_debts and monthly_debt_payments:
        resolved_debts = [DebtItem(
            name="Existing EMIs",
            debt_type="other",
            outstanding=to_decimal(monthly_debt_payments) * Decimal('12'),
            interest_rate_pct=Decimal('10.0'),
            emi=to_decimal(monthly_debt_payments)
        )]
    total_debt_emis = sum((d.emi for d in resolved_debts), Decimal('0.00'))

    # Step A: Net In-Hand Income
    tax_res = calculate_tax(
        gross_income=inc.gross_annual,
        config=tax_config,
        regime_preference=regime_preference,
        deductions=deductions
    )
    net_monthly_in_hand = to_decimal(tax_res['net_monthly_income'])
    steps.append(CalcStep(
        step_id="step_a_net_in_hand",
        label="Step A: Net Monthly In-Hand Income",
        formula="Gross Annual Income - Total Tax / 12",
        inputs={"gross_annual": inc.gross_annual, "total_tax": tax_res['total_tax']},
        result=net_monthly_in_hand,
        note=f"Net in-hand under recommended {tax_res.get('recommended_regime', 'new').upper()} regime.",
        category="income"
    ))

    # Step B: Mandatory Payroll Deductions (EPF, PT) if not already deducted
    mandatory_payroll_m = inc.mandatory_payroll_deductions_monthly
    in_hand_after_payroll = max(Decimal('0.00'), net_monthly_in_hand - mandatory_payroll_m)
    if mandatory_payroll_m > Decimal('0.00'):
        steps.append(CalcStep(
            step_id="step_b_mandatory_payroll",
            label="Step B: Mandatory Payslip Deductions",
            formula="Net In-Hand - (EPF + PT)",
            inputs={"net_monthly": net_monthly_in_hand, "payroll_deductions": mandatory_payroll_m},
            result=in_hand_after_payroll,
            note=f"Deducted employee EPF and Professional Tax to prevent double counting.",
            category="income"
        ))

    # Step C: Essential Expenses
    after_essentials = in_hand_after_payroll - essential_expenses_m
    steps.append(CalcStep(
        step_id="step_c_essential_expenses",
        label="Step C: Essential Living Outflows",
        formula="Income after Payroll - Essential Expenses",
        inputs={"remaining": in_hand_after_payroll, "essential_expenses": essential_expenses_m},
        result=after_essentials,
        note="Subtracted non-negotiable living costs (rent, groceries, utilities, school).",
        category="expense"
    ))

    # Step D: Minimum Debt EMIs
    after_debt = after_essentials - total_debt_emis
    steps.append(CalcStep(
        step_id="step_d_debt_payments",
        label="Step D: Minimum Debt Payments (EMIs)",
        formula="Remaining - Total Loan EMIs",
        inputs={"remaining": after_essentials, "total_emis": total_debt_emis},
        result=after_debt,
        note="Subtracted contracted monthly debt repayments.",
        category="debt"
    ))

    # Step E: Irregular Sinking Fund
    after_sinking = after_debt - sinking_fund_m
    steps.append(CalcStep(
        step_id="step_e_sinking_fund",
        label="Step E: Irregular Expense Sinking Fund",
        formula="Remaining - Annual Irregular Costs / 12",
        inputs={"remaining": after_debt, "monthly_sinking_fund": sinking_fund_m},
        result=after_sinking,
        note="Reserved monthly provision for annual insurance premiums and irregular expenses.",
        category="expense"
    ))

    # Step F: Safety Buffer (Config %)
    buffer_pct = to_decimal(rules.get('buffer_pct', 0.0))
    buffer_amount = round_inr(net_monthly_in_hand * (buffer_pct / Decimal('100.0')), places=2)
    investable_capacity = round_inr(after_sinking - buffer_amount, places=2)
    steps.append(CalcStep(
        step_id="step_f_safety_buffer",
        label=f"Step F: Safety Contingency Buffer ({buffer_pct}%)",
        formula=f"Net In-Hand * {buffer_pct}%",
        inputs={"net_monthly": net_monthly_in_hand, "buffer_pct": buffer_pct},
        result=buffer_amount,
        note=f"Unallocated buffer for unexpected monthly fluctuations.",
        category="buffer"
    ))

    # Step G: Investable Capacity Before Priorities
    steps.append(CalcStep(
        step_id="step_g_investable_capacity",
        label="Step G: Investable Capacity Before Priorities",
        formula="Step E - Step F",
        inputs={"after_sinking": after_sinking, "buffer": buffer_amount},
        result=investable_capacity,
        note="Total monthly surplus available for emergency fund, debt prepayment, and investing.",
        category="surplus"
    ))

    # Step H: Priority Allocations
    # 1. Emergency Fund Target
    ef_result = calculate_emergency_fund(
        monthly_expenses=total_expenses_m,
        existing_fund=existing_emergency_fund,
        target_months=emergency_fund_months,
        profile=user_profile,
        rules_config=rules_config
    )
    ef_monthly_contrib = to_decimal(ef_result['monthly_contribution'])

    # Standard monthly surplus
    monthly_surplus = round_inr(
        net_monthly_in_hand
        - total_expenses_m
        - total_debt_emis
        - ef_monthly_contrib
        - buffer_amount,
        places=2
    )

    # Debt Prepayment Assessment (Avalanche)
    debt_rules = rules.get('debt_rules', {})
    high_rate_threshold = to_decimal(debt_rules.get('high_interest_threshold_pct', 12.0))
    has_credit_card_debt = any(d.debt_type == 'credit_card' and d.outstanding > 0 for d in resolved_debts)

    high_interest_debts = [d for d in resolved_debts if d.interest_rate_pct >= high_rate_threshold or d.debt_type == 'credit_card']
    debt_prepayment_allocation = Decimal('0.00')
    debt_warning = None

    if has_credit_card_debt and debt_rules.get('disallow_investing_with_credit_card_debt', True):
        debt_prepayment_allocation = max(Decimal('0.00'), monthly_surplus)
        debt_warning = "CRITICAL: You are carrying revolving credit card debt. All investment surplus should be directed to extinguish this debt immediately."
    elif high_interest_debts and monthly_surplus > Decimal('0.00'):
        debt_prepayment_allocation = round_inr(monthly_surplus * Decimal('0.5'), places=2)

    monthly_surplus_for_goals = max(Decimal('0.00'), monthly_surplus - debt_prepayment_allocation)

    steps.append(CalcStep(
        step_id="step_h_final_surplus",
        label="Step H: Final Monthly Investable Surplus",
        formula="Investable Capacity - Emergency Contribution - Debt Prepayment",
        inputs={
            "capacity": investable_capacity,
            "emergency_contribution": ef_monthly_contrib,
            "debt_prepayment": debt_prepayment_allocation
        },
        result=monthly_surplus_for_goals,
        note="Funds deployed into wealth creation asset classes via the optimizer.",
        category="allocation"
    ))

    # Step I: Discretionary Spending What-Ifs
    what_if_cuts = {
        'cut_20_pct': float(round_inr(discretionary_expenses_m * Decimal('0.20'), 2)),
        'cut_50_pct': float(round_inr(discretionary_expenses_m * Decimal('0.50'), 2)),
        'cut_100_pct': float(round_inr(discretionary_expenses_m, 2))
    }

    # Deficit Analysis
    is_positive = monthly_surplus > Decimal('0.00')
    deficit_plan = None
    if not is_positive:
        gap = abs(monthly_surplus)
        levers = []
        if discretionary_expenses_m > Decimal('0.00'):
            levers.append(f"Cut discretionary spending by up to ₹{discretionary_expenses_m:,.0f}/month")
        if total_debt_emis > Decimal('0.00'):
            levers.append(f"Explore debt restructuring to lower monthly EMIs of ₹{total_debt_emis:,.0f}")
        if buffer_amount > Decimal('0.00'):
            levers.append(f"Temporarily suspend contingency buffer of ₹{buffer_amount:,.0f}/month")
        levers.append("Identify auxiliary income streams to bridge the shortfall")

        deficit_plan = {
            'gap_amount': float(gap),
            'formatted_gap': format_inr(gap),
            'break_even_minimum': float(gap),
            'top_levers': levers[:3]
        }

    # Tax comparison formatted for UI
    reg_comp = tax_res.get('regime_comparison')
    if reg_comp:
        tax_comparison = {
            'recommended': tax_res.get('recommended_regime', 'new'),
            'new': {'tax': float(reg_comp.get('new_tax', tax_res['total_tax']))},
            'old': {'tax': float(reg_comp.get('old_tax', tax_res['total_tax']))},
            'savings': float(reg_comp.get('tax_savings', 0.0)),
            'recommendation_note': reg_comp.get('recommendation_note', '')
        }
    else:
        tax_comparison = {
            'recommended': tax_res.get('recommended_regime', 'new'),
            'new': {'tax': float(tax_res['total_tax'])},
            'old': {'tax': float(tax_res['total_tax'])},
            'savings': 0.0,
            'recommendation_note': 'Both regimes result in identical tax outgo.'
        }

    cc_outstanding = sum((d.outstanding for d in resolved_debts if d.debt_type == 'credit_card'), Decimal('0.00'))

    calc_trace = [s.to_dict() for s in steps]

    return {
        'tax_result': tax_res,
        'tax_comparison': tax_comparison,
        'expense_result': exp_res,
        'emergency_fund_result': ef_result,
        'emergency_fund_allocation': float(ef_monthly_contrib),
        'debt_prepayment_allocation': float(debt_prepayment_allocation),
        'debt_warning': debt_warning,
        'discretionary_what_ifs': what_if_cuts,
        'deficit_plan': deficit_plan,
        'summary': {
            'gross_monthly_income': float(inc.gross_monthly),
            'gross_annual_income': float(inc.gross_annual),
            'net_monthly_income': float(net_monthly_in_hand),
            'mandatory_payroll_deductions': float(mandatory_payroll_m),
            'tax_monthly': float(round_inr(to_decimal(tax_res['total_tax']) / Decimal('12'), 2)),
            'tax_annual': float(tax_res['total_tax']),
            'effective_tax_rate_pct': float(tax_res.get('effective_rate_pct', 0.0)),
            'marginal_tax_rate_pct': float(tax_res.get('marginal_rate_pct', 0.0)),
            'total_essential_expenses': float(essential_expenses_m),
            'total_discretionary_expenses': float(discretionary_expenses_m),
            'total_monthly_expenses': float(total_expenses_m),
            'monthly_debt_payments': float(total_debt_emis),
            'emergency_fund_monthly': float(ef_monthly_contrib),
            'emergency_fund_target': float(ef_result['target']),
            'emergency_fund_shortfall': float(ef_result['shortfall']),
            'emergency_fund_existing': float(ef_result['existing']),
            'emergency_fund_target_months': int(ef_result['target_months']),
            'emergency_fund_months_to_target': int(ef_result['months_to_target']),
            'safety_buffer_monthly': float(buffer_amount),
            'credit_card_balance': float(cc_outstanding),
            'investable_capacity_before_priorities': float(investable_capacity),
            'monthly_surplus': float(monthly_surplus),
            'monthly_surplus_for_goals': float(monthly_surplus_for_goals),
            'annual_surplus': float(round_inr(monthly_surplus * Decimal('12'), 2)),
            'surplus_is_positive': is_positive
        },
        'trace': calc_trace,
        'calculation_trace': calc_trace
    }
