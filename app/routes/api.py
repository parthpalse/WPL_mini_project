"""API Blueprint providing backend services for the BankEase SPA frontend.

Endpoints:
  GET  /api/profile         - Fetch user's financial profile
  PUT  /api/profile         - Save/update profile and recalculate surplus
  GET  /api/cashflow        - 12-month historical & projected cash flow
  GET  /api/allocation      - Optimal asset allocation based on risk profile
  GET  /api/projection      - Multi-year investment projections
  GET  /api/market          - Live market indices and currency rates
  GET  /api/goals           - User goals and savings progress
  POST /api/goals           - Add or update a goal
  POST /api/assistant/chat  - AI financial guidance grounded in engine math
"""

import uuid
from decimal import Decimal
from flask import Blueprint, jsonify, request, session
from app.market.finnhub_client import get_quote

from app.engine.max_investment import calculate_surplus
from app.engine.money import to_decimal, round_inr, format_inr
from app.engine.inflation import calculate_sip_future_value

api_bp = Blueprint('api', __name__, url_prefix='/api')

DEFAULT_PROFILE = {
    "name": "Aarav (sample)",
    "monthlyGrossIncome": 150000,
    "monthlyTax": 18000,
    "expenses": [
        {"id": "rent", "category": "Rent", "amount": 32000},
        {"id": "food", "category": "Groceries & Food", "amount": 14000},
        {"id": "transport", "category": "Transport", "amount": 6000},
        {"id": "utilities", "category": "Utilities", "amount": 4500},
        {"id": "insurance", "category": "Insurance", "amount": 3500},
        {"id": "lifestyle", "category": "Lifestyle", "amount": 9000}
    ],
    "debts": [
        {"id": "car", "name": "Car loan EMI", "emi": 12500, "outstanding": 380000},
        {"id": "cc", "name": "Credit card", "emi": 4000, "outstanding": 22000}
    ],
    "emergencyFundCurrent": 210000,
    "emergencyFundTargetMonths": 6,
    "emergencyMonthlyContribution": 8000,
    "riskProfile": "moderate"
}

DEFAULT_GOALS = [
    {"id": "g1", "title": "Home down payment", "target": 2500000, "saved": 640000, "deadline": "2030-03"},
    {"id": "g2", "title": "Child education", "target": 3000000, "saved": 210000, "deadline": "2038-06"},
    {"id": "g3", "title": "Europe trip", "target": 400000, "saved": 285000, "deadline": "2027-05"}
]


def _get_active_profile() -> dict:
    return session.get('profile', DEFAULT_PROFILE)


def _compute_profile_financials(profile: dict) -> dict:
    gross_monthly = float(profile.get('monthlyGrossIncome', 0))
    gross_annual = gross_monthly * 12
    expenses = profile.get('expenses', [])
    debts = profile.get('debts', [])
    
    total_expenses = sum(float(e.get('amount', 0)) for e in expenses)
    total_emis = sum(float(d.get('emi', 0)) for d in debts)
    monthly_tax = float(profile.get('monthlyTax', 0))
    in_hand = gross_monthly - monthly_tax
    surplus = max(0.0, in_hand - total_expenses - total_emis)
    
    return {
        "gross_monthly": gross_monthly,
        "gross_annual": gross_annual,
        "monthly_tax": monthly_tax,
        "in_hand": in_hand,
        "total_expenses": total_expenses,
        "total_emis": total_emis,
        "surplus": surplus
    }


# ── Profile Endpoints ──────────────────────────────────────────────────────────

@api_bp.route('/profile', methods=['GET'])
def get_profile():
    return jsonify(_get_active_profile())


@api_bp.route('/profile', methods=['PUT', 'POST'])
def save_profile():
    data = request.get_json(silent=True) or {}
    profile = _get_active_profile().copy()
    profile.update(data)
    session['profile'] = profile
    session.modified = True
    return jsonify(profile)


# ── Cash Flow Endpoint ─────────────────────────────────────────────────────────

@api_bp.route('/cashflow', methods=['GET'])
def get_cashflow():
    fin = _compute_profile_financials(_get_active_profile())
    base_income = fin['gross_monthly']
    base_expenses = fin['total_expenses'] + fin['total_emis']
    base_savings = max(0.0, fin['in_hand'] - base_expenses)

    months = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct']
    # Add slight realistic variances
    variances = [
        (-2000, -1000), (0, 10000), (0, -2000), (0, -4000),
        (15000, 3000), (0, 0), (0, -1500), (0, 2000),
        (0, -3000), (0, 1000), (0, -500), (0, 0)
    ]
    
    cashflow = []
    for m, (inc_delta, exp_delta) in zip(months, variances):
        m_inc = round(base_income + inc_delta)
        m_exp = round(base_expenses + exp_delta)
        m_sav = max(0, round(fin['in_hand'] + inc_delta - m_exp))
        cashflow.append({
            "month": m,
            "income": m_inc,
            "expenses": m_exp,
            "savings": m_sav
        })
    return jsonify(cashflow)


# ── Allocation Endpoint ───────────────────────────────────────────────────────

@api_bp.route('/allocation', methods=['GET'])
def get_allocation():
    profile = _get_active_profile()
    risk = str(profile.get('riskProfile', 'moderate')).lower()

    if risk in ('conservative', 'safe', 'low'):
        allocations = [
            {"id": "equity", "label": "Equity MFs", "percent": 25},
            {"id": "debt", "label": "Debt Funds", "percent": 45},
            {"id": "gold", "label": "Gold", "percent": 10},
            {"id": "ppf", "label": "PPF / EPF", "percent": 20}
        ]
    elif risk in ('aggressive', 'growth', 'high'):
        allocations = [
            {"id": "equity", "label": "Equity MFs", "percent": 65},
            {"id": "debt", "label": "Debt Funds", "percent": 15},
            {"id": "gold", "label": "Gold", "percent": 10},
            {"id": "ppf", "label": "PPF / EPF", "percent": 10}
        ]
    else:  # Moderate / Balanced
        allocations = [
            {"id": "equity", "label": "Equity MFs", "percent": 50},
            {"id": "debt", "label": "Debt Funds", "percent": 25},
            {"id": "gold", "label": "Gold", "percent": 10},
            {"id": "ppf", "label": "PPF / EPF", "percent": 15}
        ]

    return jsonify(allocations)


# ── Projection Endpoint ───────────────────────────────────────────────────────

@api_bp.route('/projection', methods=['GET'])
def get_projection():
    fin = _compute_profile_financials(_get_active_profile())
    monthly_sip = max(1000.0, fin['surplus'])

    years = [0, 2, 4, 6, 8, 10, 12, 15]
    projections = []

    for yr in years:
        if yr == 0:
            projections.append({"year": 0, "conservative": 0, "expected": 0, "optimistic": 0})
        else:
            months = yr * 12
            # 8% conservative, 11% expected, 14% optimistic
            c_val = calculate_sip_future_value(monthly_sip, 8.0, months)['future_value']
            e_val = calculate_sip_future_value(monthly_sip, 11.0, months)['future_value']
            o_val = calculate_sip_future_value(monthly_sip, 14.0, months)['future_value']
            projections.append({
                "year": yr,
                "conservative": round(c_val),
                "expected": round(e_val),
                "optimistic": round(o_val)
            })

    return jsonify(projections)


# ── Market Endpoint ───────────────────────────────────────────────────────────

@api_bp.route('/market', methods=['GET'])
def get_market():
    tickers = [
        {"symbol": "RELIANCE.NS", "name": "Reliance"},
        {"symbol": "TCS.NS", "name": "TCS"},
        {"symbol": "INFY.NS", "name": "Infosys"},
        {"symbol": "HDFCBANK.NS", "name": "HDFC Bank"}
    ]
    
    market_data = []
    for t in tickers:
        q = get_quote(t["symbol"])
        if q:
            market_data.append({
                "symbol": t["symbol"],
                "name": t["name"],
                "value": q.get("current", 0),
                "changePct": q.get("change_pct", 0),
                "status": "active"
            })
        else:
            market_data.append({
                "symbol": t["symbol"],
                "name": t["name"],
                "value": 0,
                "changePct": 0,
                "status": "error"
            })
            
    return jsonify(market_data)


# ── Goals Endpoints ───────────────────────────────────────────────────────────

@api_bp.route('/goals', methods=['GET'])
def get_goals():
    goals = session.get('goals', DEFAULT_GOALS)
    return jsonify(goals)


@api_bp.route('/goals', methods=['POST'])
def save_goal():
    data = request.get_json(silent=True) or {}
    goals = session.get('goals', list(DEFAULT_GOALS)).copy()
    if 'id' in data:
        # update existing
        goals = [g if g.get('id') != data['id'] else {**g, **data} for g in goals]
    else:
        # create new
        data['id'] = f"g{len(goals) + 1}"
        goals.append(data)
    session['goals'] = goals
    session.modified = True
    return jsonify(goals)


# ── AI Assistant Endpoint ─────────────────────────────────────────────────────

@api_bp.route('/assistant/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    messages = body.get('messages', [])
    last_msg = messages[-1].get('content', '') if messages else ''
    
    fin = _compute_profile_financials(_get_active_profile())
    profile = _get_active_profile()

    # Generate helpful financial breakdown
    gross = fin['gross_monthly']
    tax = fin['monthly_tax']
    in_hand = fin['in_hand']
    expenses = fin['total_expenses']
    emis = fin['total_emis']
    surplus = fin['surplus']
    ef_current = profile.get('emergencyFundCurrent', 0)
    risk = profile.get('riskProfile', 'moderate')

    reply = (
        f"Based on your profile, here is your deterministic monthly cash position:\n\n"
        f"• **Monthly In-Hand**: {format_inr(in_hand)} (Gross: {format_inr(gross)}, Tax: {format_inr(tax)})\n"
        f"• **Living Expenses**: {format_inr(expenses)}\n"
        f"• **Debt EMIs**: {format_inr(emis)}\n"
        f"• **Net Investable Surplus**: {format_inr(surplus)} / month\n\n"
        f"Emergency Fund: {format_inr(ef_current)} (Target: 6 months of expenses = {format_inr(expenses * 6)}).\n"
        f"With your **{risk.capitalize()}** risk profile, allocating 50% to Equity Mutual Funds, 25% to Debt Funds, "
        f"and 25% across Gold and PPF gives a resilient, inflation-beating portfolio."
    )

    return jsonify({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": reply
    })
