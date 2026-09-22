import os
from decimal import Decimal
from flask import Blueprint, render_template, request, session, redirect, url_for, current_app, jsonify
from app.engine.max_investment import calculate_surplus
from app.engine.optimizer import optimize_allocation

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


@dashboard_bp.route('/', methods=['GET'])
def index():
    wizard_data = session.get('wizard_data') or session.get('tier1') or {}
    if not wizard_data:
        return redirect(url_for('wizard.index'))

    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')

    # ── Derive income (monthly in-hand → annual gross for tax engine) ──
    monthly_income = _get_float(wizard_data, 'monthly_income', 'income_amount')
    if wizard_data.get('income_freq') == 'annual':
        monthly_income = monthly_income / 12

    # Gross income for tax engine: use explicit or estimate from in-hand
    gross_annual = _get_float(wizard_data, 'gross_income', 'income')
    if gross_annual == 0:
        gross_annual = monthly_income * 12 * 1.25  # rough gross estimate

    # ── Derive expenses ──
    expense_keys = ['exp_rent', 'exp_food', 'exp_transport', 'exp_utilities', 'exp_health', 'exp_other']
    monthly_expenses = sum(_get_float(wizard_data, k) for k in expense_keys)
    if monthly_expenses == 0:
        monthly_expenses = _get_float(wizard_data, 'expenses', 'monthly_expenses',
                                      'other_expenses', default=0)
        monthly_expenses += _get_float(wizard_data, 'monthly_rent', 'exp_rent', default=0)

    # ── Risk / liquidity ──
    risk_score = int(_get_float(wizard_data, 'risk_attitude', default=5))
    liquidity_need = wizard_data.get('liquidity_need', 'medium')

    # ── Run engine ──
    surplus_data = calculate_surplus(
        gross_income=gross_annual,
        fixed_expenses=[{'name': 'All Expenses', 'amount': monthly_expenses * 12}],
        variable_expenses=[],
        tax_config=tax_config
    )

    # Inject credit card balance into summary for template
    cc_bal = _get_float(wizard_data, 'credit_card_balance')
    surplus_data['summary']['credit_card_balance'] = cc_bal

    monthly_surplus = surplus_data['summary']['monthly_surplus']

    # ── Run optimizer ──
    allocations = optimize_allocation(
        monthly_surplus=max(0, monthly_surplus),
        risk_score=risk_score,
        liquidity_need=liquidity_need,
        product_config=product_config
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

    income = float(data.get('income', 0))
    expenses = float(data.get('expenses', 0))
    risk_score = int(data.get('risk_score', 5))

    surplus_data = calculate_surplus(
        gross_income=income * 12 * 1.25,
        fixed_expenses=[{'name': 'Fixed', 'amount': expenses * 12}],
        variable_expenses=[],
        tax_config=tax_config
    )
    monthly_surplus = surplus_data['summary']['monthly_surplus']

    allocations = optimize_allocation(
        monthly_surplus=max(0, monthly_surplus),
        risk_score=risk_score,
        liquidity_need='medium',
        product_config=product_config
    )

    return jsonify({
        'surplus': float(monthly_surplus),
        'surplus_fmt': f"₹{abs(int(monthly_surplus)):,}",
        'allocations': allocations
    })
