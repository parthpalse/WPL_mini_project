from flask import Blueprint, render_template, request, redirect, url_for, session

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')


# ── Root redirect ─────────────────────────────────────────────────────────────
from flask import Blueprint as _RootBP
root_bp = _RootBP('root', __name__)

@root_bp.route('/')
def home():
    return redirect(url_for('wizard.index'))



@profile_bp.route('/', methods=['GET'])
def index():
    return render_template('onboarding/tier1.html')

@profile_bp.route('/tier1_submit', methods=['POST'])
def tier1_submit():
    # Store Tier 1 data in session
    session['tier1'] = {
        'income': float(request.form.get('income', 0)),
        'expenses': float(request.form.get('expenses', 0)),
        'goal_name': request.form.get('goal_name', ''),
        'goal_amount': float(request.form.get('goal_amount', 0)),
        'goal_horizon': int(request.form.get('goal_horizon', 1))
    }
    return redirect(url_for('dashboard.index'))
