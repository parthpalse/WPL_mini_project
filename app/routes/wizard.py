from flask import Blueprint, render_template, request, session, redirect, url_for, flash

wizard_bp = Blueprint('wizard', __name__, url_prefix='/wizard')

STEP_FIELDS = {
    1: ['age', 'city_tier', 'household', 'job_type'],
    2: ['income_amount', 'income_freq', 'gross_income'],
    3: ['exp_rent', 'exp_food', 'exp_transport', 'exp_utilities', 'exp_health', 'exp_other',
        'exp_rent_hidden', 'exp_food_hidden', 'exp_transport_hidden',
        'exp_utilities_hidden', 'exp_health_hidden', 'exp_other_hidden'],
    4: ['credit_card_balance', 'personal_loan_emi', 'personal_loan_rate',
        'existing_savings', 'existing_investments'],
    5: ['risk_attitude', 'liquidity_need', 'goal_horizon', 'goal_amount'],
}


@wizard_bp.route('/', methods=['GET'])
def index():
    return render_template('wizard/index.html')


@wizard_bp.route('/step/<int:step_id>', methods=['GET', 'POST'])
def step(step_id):
    if step_id < 1 or step_id > 5:
        return redirect(url_for('wizard.index'))

    if 'wizard_data' not in session:
        session['wizard_data'] = {}

    if request.method == 'POST':
        wizard_data = dict(session['wizard_data'])
        # Merge slider hidden values (they override the range names)
        form = request.form.to_dict()
        # For step 3, prefer the _hidden fields (synced via JS) but fall back to range
        for k, v in form.items():
            if k != 'csrf_token':
                clean_key = k.replace('_hidden', '')
                wizard_data[clean_key] = v
        session['wizard_data'] = wizard_data
        session.modified = True

        if step_id < 5:
            return redirect(url_for('wizard.step', step_id=step_id + 1))
        else:
            return redirect(url_for('dashboard.index'))

    return render_template(
        f'wizard/step{step_id}.html',
        step=step_id,
        data=session.get('wizard_data', {})
    )


@wizard_bp.route('/quick', methods=['GET', 'POST'])
def quick():
    if request.method == 'POST':
        form = {k: v for k, v in request.form.items() if k != 'csrf_token'}
        # Derive a unified expense total
        exp = (float(form.get('monthly_rent', 0) or 0) +
               float(form.get('other_emis', 0) or 0) +
               float(form.get('other_expenses', 0) or 0))
        inc = float(form.get('monthly_income', 0) or 0)

        # Warn if expenses > 150% income (check but don't block)
        session['wizard_data'] = {
            'income_amount': form.get('monthly_income', 0),
            'income_freq': 'monthly',
            'exp_rent': form.get('monthly_rent', 0),
            'exp_other': form.get('other_expenses', 0),
            'personal_loan_emi': form.get('other_emis', 0),
            'risk_attitude': '5',
            'liquidity_need': 'medium',
            'goal_horizon': 'medium',
            'quick_mode': True,
        }
        session.modified = True
        return redirect(url_for('dashboard.index'))

    return render_template('wizard/quick.html', data=session.get('wizard_data', {}))


@wizard_bp.route('/reset', methods=['POST'])
def reset():
    session.pop('wizard_data', None)
    flash('Your plan data has been cleared.', 'success')
    return redirect(url_for('wizard.index'))
