import os
from decimal import Decimal
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app, jsonify
from flask_login import login_required
from app.engine.max_investment import calculate_surplus
from app.engine.optimizer import optimize_allocation
from app.engine.tax import calculate_tax_regime
from app.engine.models import UserProfile, DebtItem

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


def _get_float(d, *keys, default=0.0):
    """Get a float from a dict, trying multiple keys."""
    for k in keys:
        v = d.get(k)
        if v not in (None, '', 'None'):
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
    return default


def _estimate_gross_from_net(target_net_annual: float, tax_config: str) -> float:
    """Find the exact gross annual income that produces target_net_annual under New Regime."""
    if target_net_annual <= 0:
        return 0.0
    # Under FY 2026-27 New Regime, income up to 12,75,000 has zero tax
    if target_net_annual <= 1275000:
        return target_net_annual

    # Bisection search for incomes in taxable brackets
    low = float(target_net_annual)
    high = float(target_net_annual) * 2.0
    for _ in range(25):
        mid = (low + high) / 2.0
        tax = calculate_tax_regime(mid, 'new', tax_config)['total_tax']
        net = mid - tax
        if net < target_net_annual:
            low = mid
        else:
            high = mid
    return round(high, 2)


@dashboard_bp.route('/', methods=['GET'])
@login_required
def index():
    wizard_data = session.get('wizard_data') or session.get('tier1') or {}
    if not wizard_data:
        return redirect(url_for('wizard.index'))

    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')
    rules_config = os.path.join(config_dir, 'planning_rules.json')

    # ── Income Handling ──
    explicit_gross = _get_float(wizard_data, 'gross_income', 'income', default=0.0)
    monthly_in_hand = _get_float(wizard_data, 'monthly_income', 'income_amount', default=0.0)
    if wizard_data.get('income_freq') == 'annual' and monthly_in_hand > 0:
        monthly_in_hand = monthly_in_hand / 12

    if explicit_gross > 0:
        gross_annual = explicit_gross
    elif monthly_in_hand > 0:
        # User gave take-home: calculate exact gross so net take-home matches user input
        gross_annual = _estimate_gross_from_net(monthly_in_hand * 12, tax_config)
    else:
        gross_annual = 0.0

    # ── Expense Handling (Monthly amounts, split essential vs discretionary) ──
    fixed_items = []
    variable_items = []

    exp_map = [
        ('exp_rent', 'Rent & Housing', 'essential'),
        ('exp_food', 'Food & Groceries', 'essential'),
        ('exp_transport', 'Transportation', 'essential'),
        ('exp_utilities', 'Utilities & Bills', 'essential'),
        ('exp_health', 'Healthcare', 'essential'),
        ('exp_other', 'Lifestyle & Discretionary', 'discretionary'),
    ]
    has_breakdown = False
    for key, name, cat in exp_map:
        amt = _get_float(wizard_data, key, default=0.0)
        if amt > 0:
            has_breakdown = True
            item = {'name': name, 'amount': amt, 'category': cat}
            if cat == 'essential':
                fixed_items.append(item)
            else:
                variable_items.append(item)

    if not has_breakdown:
        rent = _get_float(wizard_data, 'monthly_rent', 'exp_rent', default=0.0)
        other = _get_float(wizard_data, 'expenses', 'monthly_expenses', 'other_expenses', default=0.0)
        if rent > 0:
            fixed_items.append({'name': 'Rent & Housing', 'amount': rent, 'category': 'essential'})
        if other > 0:
            fixed_items.append({'name': 'Living Expenses', 'amount': other, 'category': 'essential'})

    # ── Debts & Liabilities ──
    debts = []
    cc_balance = _get_float(wizard_data, 'credit_card_balance', default=0.0)
    if cc_balance > 0:
        debts.append(DebtItem(
            name="Credit Card",
            debt_type="credit_card",
            outstanding=Decimal(str(cc_balance)),
            interest_rate_pct=Decimal('36.0'),
            emi=Decimal(str(round(cc_balance * 0.05, 2)))
        ))

    loan_emi = _get_float(wizard_data, 'personal_loan_emi', 'other_emis', default=0.0)
    loan_rate = _get_float(wizard_data, 'personal_loan_rate', default=14.0)
    if loan_emi > 0:
        debts.append(DebtItem(
            name="Personal Loan",
            debt_type="personal_loan",
            outstanding=Decimal(str(round(loan_emi * 24, 2))),
            interest_rate_pct=Decimal(str(loan_rate if loan_rate > 0 else 14.0)),
            emi=Decimal(str(loan_emi))
        ))

    # ── User Profile ──
    age = int(_get_float(wizard_data, 'age', default=30))
    if age < 18 or age > 100:
        age = 30
    city_tier = wizard_data.get('city_tier', 'tier_1')
    if city_tier not in {'tier_1', 'tier_2', 'tier_3'}:
        city_tier = 'tier_1'
    household = int(_get_float(wizard_data, 'household', default=1))
    dependents = max(0, household - 1)
    job_type = wizard_data.get('job_type', 'salaried')
    if job_type not in {'salaried', 'self_employed', 'variable'}:
        job_type = 'salaried'
    stability = wizard_data.get('income_stability', 'stable')
    if stability not in {'stable', 'moderate', 'variable'}:
        stability = 'stable'
    risk_score = int(_get_float(wizard_data, 'risk_attitude', default=5))
    risk_profile = 'conservative' if risk_score <= 3 else ('growth' if risk_score >= 8 else 'balanced')
    regime_pref = wizard_data.get('tax_regime_preference', 'auto')
    if regime_pref not in {'auto', 'new', 'old'}:
        regime_pref = 'auto'

    profile = UserProfile(
        age=age,
        city_tier=city_tier,
        adults=max(1, household - dependents),
        dependents=dependents,
        employment_type=job_type,
        income_stability=stability,
        risk_profile=risk_profile,
        tax_regime_preference=regime_pref
    )

    # ── Existing Savings & Horizon ──
    existing_savings = _get_float(wizard_data, 'existing_savings', default=0.0)

    horizon_val = wizard_data.get('goal_horizon', 'medium')
    if isinstance(horizon_val, (int, float)):
        goal_months = int(horizon_val * 12) if horizon_val <= 30 else int(horizon_val)
    elif horizon_val == 'short':
        goal_months = 12
    elif horizon_val == 'long':
        goal_months = 60
    else:
        goal_months = 36
    goal_horizons = [goal_months]
    liquidity_need = wizard_data.get('liquidity_need', 'medium')

    # ── Run Engine ──
    surplus_data = calculate_surplus(
        gross_income=gross_annual,
        fixed_expenses=fixed_items,
        variable_expenses=variable_items,
        debts=debts,
        existing_emergency_fund=existing_savings,
        user_profile=profile,
        tax_config=tax_config,
        rules_config=rules_config,
        regime_preference=regime_pref
    )

    monthly_surplus = surplus_data['summary']['monthly_surplus']
    marginal_tax_rate = surplus_data['summary'].get('marginal_tax_rate_pct', 0.0)

    # ── Run Optimizer ──
    allocations = optimize_allocation(
        monthly_surplus=max(0, monthly_surplus),
        risk_score=risk_score,
        liquidity_need=liquidity_need,
        goal_horizons=goal_horizons,
        marginal_tax_rate_pct=marginal_tax_rate,
        product_config=product_config,
        rules_config=rules_config
    )

    return render_template(
        'dashboard/index.html',
        surplus_data=surplus_data,
        allocations=allocations,
        wizard_data=wizard_data
    )


from app.llm.explain import explain_plan, explain_step as _explain_step


@dashboard_bp.route('/explain', methods=['POST'])
def explain():
    data = request.get_json()
    if not data:
        return jsonify({'explanation': 'No data provided.'}), 400
    result = explain_plan(data)
    return jsonify({'explanation': result})


@dashboard_bp.route('/explain_step', methods=['POST'])
def explain_step_route():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    return jsonify(_explain_step(data))


@dashboard_bp.route('/simulate_api', methods=['POST'])
def simulate_api():
    """What-if scenario live recalculation endpoint."""
    data = request.get_json() or {}
    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')
    rules_config = os.path.join(config_dir, 'planning_rules.json')

    income = float(data.get('income', 0))
    expenses = float(data.get('expenses', 0))
    risk_score = int(data.get('risk_score', 5))

    gross_annual = _estimate_gross_from_net(income * 12, tax_config)

    surplus_data = calculate_surplus(
        gross_income=gross_annual,
        fixed_expenses=[{'name': 'Living Expenses', 'amount': expenses, 'category': 'essential'}],
        variable_expenses=[],
        tax_config=tax_config,
        rules_config=rules_config
    )
    monthly_surplus = surplus_data['summary']['monthly_surplus']
    marginal_tax_rate = surplus_data['summary'].get('marginal_tax_rate_pct', 0.0)

    allocations = optimize_allocation(
        monthly_surplus=max(0, monthly_surplus),
        risk_score=risk_score,
        liquidity_need='medium',
        marginal_tax_rate_pct=marginal_tax_rate,
        product_config=product_config,
        rules_config=rules_config
    )

    return jsonify({
        'surplus': float(monthly_surplus),
        'surplus_fmt': f"₹{abs(int(monthly_surplus)):,}",
        'allocations': allocations,
        'summary': surplus_data['summary']
    })


def _calc_scenario_summary(wiz_data: dict, tax_config: str, product_config: str, rules_config: str) -> dict:
    """Helper to run engine and compute comprehensive summary metrics for a scenario."""
    from app.engine.inflation import calculate_sip_future_value
    inc = _get_float(wiz_data, 'income_amount', 'monthly_income', 'gross_income', default=0.0)
    freq = wiz_data.get('income_freq', 'monthly')
    if freq == 'annual' and inc > 0:
        inc = inc / 12
    gross_annual = _estimate_gross_from_net(inc * 12, tax_config)

    # Expenses
    exp_rent = _get_float(wiz_data, 'exp_rent', default=0.0)
    exp_food = _get_float(wiz_data, 'exp_food', default=0.0)
    exp_transport = _get_float(wiz_data, 'exp_transport', default=0.0)
    exp_utilities = _get_float(wiz_data, 'exp_utilities', default=0.0)
    exp_health = _get_float(wiz_data, 'exp_health', default=0.0)
    exp_other = _get_float(wiz_data, 'exp_other', default=0.0)

    fixed_items = []
    variable_items = []
    essential_tot = exp_rent + exp_food + exp_transport + exp_utilities + exp_health
    if essential_tot > 0:
        fixed_items.append({'name': 'Essential Living', 'amount': essential_tot, 'category': 'essential'})
    if exp_other > 0:
        variable_items.append({'name': 'Discretionary', 'amount': exp_other, 'category': 'discretionary'})

    # If simple expense field was given instead
    if not fixed_items and not variable_items:
        simple_exp = _get_float(wiz_data, 'expenses', 'monthly_expenses', default=0.0)
        if simple_exp > 0:
            fixed_items.append({'name': 'Living Expenses', 'amount': simple_exp, 'category': 'essential'})

    # Debts
    debts = []
    cc = _get_float(wiz_data, 'credit_card_balance', default=0.0)
    if cc > 0:
        debts.append(DebtItem(name="Credit Card", debt_type="credit_card", outstanding=Decimal(str(cc)), interest_rate_pct=Decimal('36.0'), emi=Decimal(str(round(cc * 0.05, 2)))))
    loan_emi = _get_float(wiz_data, 'personal_loan_emi', 'other_emis', default=0.0)
    loan_rate = _get_float(wiz_data, 'personal_loan_rate', default=14.0)
    if loan_emi > 0:
        debts.append(DebtItem(name="Personal Loan", debt_type="personal_loan", outstanding=Decimal(str(round(loan_emi * 24, 2))), interest_rate_pct=Decimal(str(loan_rate)), emi=Decimal(str(loan_emi))))

    savings = _get_float(wiz_data, 'existing_savings', default=0.0)
    risk_score = int(_get_float(wiz_data, 'risk_attitude', default=5))

    surplus_data = calculate_surplus(
        gross_income=gross_annual,
        fixed_expenses=fixed_items,
        variable_expenses=variable_items,
        debts=debts,
        existing_emergency_fund=savings,
        tax_config=tax_config,
        rules_config=rules_config
    )
    s = surplus_data['summary']
    surplus_amt = float(s['monthly_surplus'])

    # 10 year wealth projection at 10% base return
    proj_10y = 0.0
    if surplus_amt > 0:
        proj_res = calculate_sip_future_value(monthly_investment=surplus_amt, annual_return_pct=10.0, tenure_months=120)
        proj_10y = proj_res['future_value']

    return {
        'net_monthly_income': float(s['net_monthly_income']),
        'total_monthly_expenses': float(s['total_monthly_expenses']),
        'monthly_debt_payments': float(s.get('monthly_debt_payments', 0)),
        'emergency_fund_monthly': float(s['emergency_fund_monthly']),
        'emergency_fund_target': float(s.get('emergency_fund_target', 0)),
        'monthly_surplus': surplus_amt,
        'tax_annual': float(s.get('tax_annual', 0)),
        'projected_wealth_10y': float(proj_10y)
    }


@dashboard_bp.route('/save_scenario', methods=['POST'])
def save_scenario():
    """Save a scenario by name into the session."""
    data = request.get_json() or {}
    name = (data.get('name') or 'Scenario').strip()[:40]
    wiz_data = session.get('wizard_data') or session.get('tier1') or {}
    
    if not wiz_data:
        return jsonify({'error': 'No active plan data to save.'}), 400

    if 'saved_scenarios' not in session:
        session['saved_scenarios'] = {}

    session['saved_scenarios'][name] = dict(wiz_data)
    session.modified = True
    return jsonify({'success': True, 'name': name, 'count': len(session['saved_scenarios'])})


@dashboard_bp.route('/list_scenarios', methods=['GET'])
def list_scenarios():
    """Return all saved scenarios for this user/session."""
    scenarios = session.get('saved_scenarios') or {}
    return jsonify({'scenarios': list(scenarios.keys()), 'count': len(scenarios)})


@dashboard_bp.route('/load_scenario', methods=['POST'])
def load_scenario():
    """Load a previously saved scenario into the current session."""
    data = request.get_json() or {}
    name = data.get('name')
    scenarios = session.get('saved_scenarios') or {}

    if name not in scenarios:
        return jsonify({'error': f'Scenario "{name}" not found.'}), 404

    session['wizard_data'] = dict(scenarios[name])
    session.modified = True
    return jsonify({'success': True, 'redirect': url_for('dashboard.index')})


@dashboard_bp.route('/delete_scenario', methods=['POST'])
def delete_scenario():
    """Delete a saved scenario."""
    data = request.get_json() or {}
    name = data.get('name')
    scenarios = session.get('saved_scenarios') or {}

    if name in scenarios:
        del scenarios[name]
        session['saved_scenarios'] = scenarios
        session.modified = True
    return jsonify({'success': True, 'count': len(scenarios)})


@dashboard_bp.route('/compare_api', methods=['POST'])
def compare_api():
    """Compares current scenario against a saved scenario and returns side-by-side metrics."""
    data = request.get_json() or {}
    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')
    rules_config = os.path.join(config_dir, 'planning_rules.json')

    # Current scenario
    curr_data = session.get('wizard_data') or session.get('tier1') or {}
    target_name = data.get('target_scenario_name')
    scenarios = session.get('saved_scenarios') or {}

    if target_name not in scenarios:
        # Default scenario B if none selected: compare with 15% lower expenses
        target_data = dict(curr_data)
        for k in ['exp_other', 'expenses', 'monthly_expenses']:
            if k in target_data:
                try:
                    target_data[k] = str(float(target_data[k]) * 0.8)
                except (ValueError, TypeError):
                    pass
        target_name = "Optimized Expenses (-20%)"
    else:
        target_data = scenarios[target_name]

    metrics_a = _calc_scenario_summary(curr_data, tax_config, product_config, rules_config)
    metrics_b = _calc_scenario_summary(target_data, tax_config, product_config, rules_config)

    # Format side-by-side comparison items
    items = [
        {
            'label': 'Net Monthly In-Hand Income',
            'val_a': metrics_a['net_monthly_income'],
            'val_b': metrics_b['net_monthly_income'],
            'delta': metrics_b['net_monthly_income'] - metrics_a['net_monthly_income']
        },
        {
            'label': 'Monthly Living Expenses',
            'val_a': metrics_a['total_monthly_expenses'],
            'val_b': metrics_b['total_monthly_expenses'],
            'delta': metrics_b['total_monthly_expenses'] - metrics_a['total_monthly_expenses']
        },
        {
            'label': 'Monthly Debt Payments',
            'val_a': metrics_a['monthly_debt_payments'],
            'val_b': metrics_b['monthly_debt_payments'],
            'delta': metrics_b['monthly_debt_payments'] - metrics_a['monthly_debt_payments']
        },
        {
            'label': 'Emergency Fund Monthly',
            'val_a': metrics_a['emergency_fund_monthly'],
            'val_b': metrics_b['emergency_fund_monthly'],
            'delta': metrics_b['emergency_fund_monthly'] - metrics_a['emergency_fund_monthly']
        },
        {
            'label': 'Monthly Investable Surplus',
            'val_a': metrics_a['monthly_surplus'],
            'val_b': metrics_b['monthly_surplus'],
            'delta': metrics_b['monthly_surplus'] - metrics_a['monthly_surplus']
        },
        {
            'label': '10-Year Projected Wealth (10% p.a.)',
            'val_a': metrics_a['projected_wealth_10y'],
            'val_b': metrics_b['projected_wealth_10y'],
            'delta': metrics_b['projected_wealth_10y'] - metrics_a['projected_wealth_10y']
        }
    ]

    return jsonify({
        'name_a': 'Current Plan',
        'name_b': target_name,
        'items': items
    })

