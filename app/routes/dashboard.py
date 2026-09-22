import os
from flask import Blueprint, render_template, session, redirect, url_for, current_app, request
from app.engine.max_investment import calculate_surplus
from app.engine.optimizer import optimize_allocation

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/', methods=['GET'])
def index():
    tier1_data = session.get('tier1')
    if not tier1_data:
        return redirect(url_for('profile.index'))
        
    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')
    
    # Run deterministic engine
    surplus_data = calculate_surplus(
        gross_income=tier1_data['income'],
        fixed_expenses=[{'name': 'Estimated', 'amount': tier1_data['expenses']}],
        variable_expenses=[],
        tax_config=tax_config
    )
    
    monthly_surplus = surplus_data['summary']['monthly_surplus']
    
    # Run optimizer
    allocations = optimize_allocation(
        monthly_surplus=monthly_surplus,
        risk_score=5,  # Default for tier 1
        liquidity_need='medium', # Default for tier 1
        product_config=product_config
    )
    
    return render_template(
        'dashboard/index.html', 
        surplus_data=surplus_data, 
        allocations=allocations,
        tier1=tier1_data
    )

from flask import jsonify
from app.llm.explain import explain_plan, explain_step

@dashboard_bp.route('/explain', methods=['POST'])
def explain():
    data = request.get_json()
    if not data:
        return jsonify({'explanation': 'No data provided.'}), 400
        
    explanation = explain_plan(data)
    return jsonify({'explanation': explanation})

@dashboard_bp.route('/explain_step', methods=['POST'])
def explain_step_route():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    
    explanation = explain_step(data)
    return jsonify(explanation)

@dashboard_bp.route('/simulator', methods=['GET'])
def simulator():
    tier1_data = session.get('tier1', {})
    if not tier1_data:
        return redirect(url_for('profile.index'))
    return render_template('dashboard/simulator.html', initial_data=tier1_data)

@dashboard_bp.route('/simulate_api', methods=['POST'])
def simulate_api():
    data = request.get_json()
    config_dir = current_app.config['CONFIG_DIR']
    tax_config = os.path.join(config_dir, 'tax_rules_fy2026_27.json')
    product_config = os.path.join(config_dir, 'product_rates_2026.json')
    
    surplus_data = calculate_surplus(
        gross_income=float(data.get('income', 0)),
        fixed_expenses=[{'name': 'Fixed', 'amount': float(data.get('expenses', 0))}],
        tax_config=tax_config
    )
    
    allocations = optimize_allocation(
        monthly_surplus=surplus_data['summary']['monthly_surplus'],
        risk_score=int(data.get('risk_score', 5)),
        liquidity_need='medium',
        product_config=product_config
    )
    
    return jsonify({
        'surplus': surplus_data['summary']['monthly_surplus'],
        'allocations': allocations
    })
