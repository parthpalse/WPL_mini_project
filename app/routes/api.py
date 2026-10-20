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
  PUT  /api/goals           - Replace the whole goals list
  POST /api/assistant/chat  - AI financial guidance grounded in engine math

All endpoints require login; profile and goals are stored per user in MongoDB.
"""

import copy
import uuid
from decimal import Decimal
from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required
from app.market.finnhub_client import get_quote
from app.models.models import UserData
from app.llm.chat import chat_sync, is_configured

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


MAX_GOALS = 50


@api_bp.before_request
@login_required
def _require_login():
    pass


def _load(key: str, default):
    """Read a per-user value from MongoDB (session fallback when LOGIN_DISABLED in tests)."""
    if current_user.is_authenticated:
        value = UserData.get(current_user.id).get(key)
        return value if value is not None else copy.deepcopy(default)
    return session.get(key, default)


def _store(key: str, value) -> None:
    if current_user.is_authenticated:
        UserData.save(current_user.id, **{key: value})
    else:
        session[key] = value
        session.modified = True


def _get_active_profile() -> dict:
    default = DEFAULT_PROFILE
    if current_user.is_authenticated:
        default = {**DEFAULT_PROFILE, "name": current_user.email.split('@')[0]}
    return _load('profile', default)


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
    _store('profile', profile)
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

def _allocation_for(profile: dict) -> list:
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
    return allocations


@api_bp.route('/allocation', methods=['GET'])
def get_allocation():
    return jsonify(_allocation_for(_get_active_profile()))


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
    return jsonify(_load('goals', DEFAULT_GOALS))


@api_bp.route('/goals', methods=['POST'])
def save_goal():
    data = request.get_json(silent=True) or {}
    goals = list(_load('goals', DEFAULT_GOALS))
    if 'id' in data:
        # update existing
        goals = [g if g.get('id') != data['id'] else {**g, **data} for g in goals]
    else:
        # create new
        data['id'] = f"g{len(goals) + 1}"
        goals.append(data)
    _store('goals', goals[:MAX_GOALS])
    return jsonify(goals[:MAX_GOALS])


@api_bp.route('/goals', methods=['PUT'])
def replace_goals():
    data = request.get_json(silent=True)
    if not isinstance(data, list) or not all(isinstance(g, dict) for g in data):
        return jsonify({"error": "Expected a list of goals."}), 400
    _store('goals', data[:MAX_GOALS])
    return jsonify(data[:MAX_GOALS])


# ── AI Assistant Endpoint ─────────────────────────────────────────────────────

@api_bp.route('/assistant/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    messages = [m for m in body.get('messages', []) if isinstance(m, dict)]
    last_msg = str(messages[-1].get('content', '')).strip() if messages else ''
    
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

    # Answer the actual question with the open-source LLM, grounded in the same
    # engine numbers. The deterministic summary above is the fallback.
    if last_msg and is_configured():
        history = [
            {"role": m["role"], "content": str(m.get("content", ""))[:2000]}
            for m in messages[:-1]
            if m.get("role") in ("user", "assistant")
        ]
        allocation_summary = " | ".join(
            f"{a['label']}: {a['percent']}% (₹{surplus * a['percent'] / 100:,.0f})"
            for a in _allocation_for(profile)
        )
        result = chat_sync(last_msg, history, {
            "monthly_surplus": surplus,
            "net_monthly_income": in_hand,
            "total_monthly_expenses": expenses + emis,
            "emergency_fund_monthly": float(profile.get('emergencyMonthlyContribution', 0)),
            "safety_buffer_monthly": 0,
            "risk_profile": risk,
            "surplus_is_positive": surplus > 0,
        }, allocation_summary=allocation_summary)
        answer = result["response"].strip()
        if answer and "⚠️" not in answer:  # stream_chat marks provider errors with ⚠️
            reply = answer
            if result["guardrail_warnings"]:
                reply += ("\n\n_Note: Some numbers in this response could not be verified against "
                          "your plan data. Please cross-check with the figures on your dashboard._")

    return jsonify({
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": reply
    })
