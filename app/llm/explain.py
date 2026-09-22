"""AI explanation layer backed by local Ollama with strict verification and deterministic fallback.

Principles:
1. Input is strictly structured JSON (CalcStep trace, summary metrics, goals, allocations).
2. All numbers in AI responses are verified against input data (zero hallucinated numbers).
3. If Ollama is offline, times out (>20s), or fails validation, fall back to a deterministic template.
4. Explanations are educational and illustrative — no specific securities advised.
"""

import os
import re
import json
import hashlib
import requests
from typing import Dict, Any, List, Set, Optional

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "20"))

# Simple in-memory response cache
_CACHE: Dict[str, Dict[str, Any]] = {}


def _collect_all_numbers(data: Any, result: Optional[Set[float]] = None) -> Set[float]:
    """Recursively collect all numeric values present in input data."""
    if result is None:
        result = set()
    if isinstance(data, (int, float)):
        result.add(round(float(data), 2))
    elif isinstance(data, str):
        # Extract plain numbers from strings
        clean = data.replace(',', '').replace('₹', '').replace('%', '').strip()
        try:
            val = float(clean)
            result.add(round(val, 2))
        except ValueError:
            pass
    elif isinstance(data, dict):
        for v in data.values():
            _collect_all_numbers(v, result)
    elif isinstance(data, (list, tuple)):
        for item in data:
            _collect_all_numbers(item, result)
    return result


def extract_numbers_from_text(text: str) -> List[float]:
    """Extract numbers, currency values, and percentages from generated text."""
    numbers = []
    # Match standard numbers and Indian comma notation: e.g. 15,00,000 or 15000 or 12.5
    raw_matches = re.findall(r'₹?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', text)
    for m in raw_matches:
        clean = m.replace(',', '').strip()
        try:
            val = float(clean)
            # Skip trivial years/indices like 1, 2, 3, 2026, 2027
            if val not in {1.0, 2.0, 3.0, 4.0, 5.0, 2026.0, 2027.0}:
                numbers.append(round(val, 2))
        except ValueError:
            pass
    return numbers


def verify_numbers(text: str, source_data: Dict[str, Any]) -> bool:
    """Verify that every number mentioned in the generated text exists in the source data."""
    extracted = extract_numbers_from_text(text)
    if not extracted:
        return True

    allowed = _collect_all_numbers(source_data)
    for num in extracted:
        # Check if number matches any allowed number within small rounding tolerance
        matched = any(abs(num - a) <= 0.05 or abs(num - (a / 100.0)) <= 0.05 or abs((num * 100.0) - a) <= 0.05 for a in allowed)
        if not matched:
            return False
    return True


def generate_deterministic_explanation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a reliable, structured explanation using deterministic rules."""
    summary = data.get('summary', {})
    surplus = summary.get('monthly_surplus', 0)
    net_monthly = summary.get('net_monthly_income', 0)
    expenses = summary.get('total_monthly_expenses', 0)
    ef_monthly = summary.get('emergency_fund_monthly', 0)
    buffer_amt = summary.get('safety_buffer_monthly', 0)
    is_positive = summary.get('surplus_is_positive', surplus > 0)
    deficit_plan = data.get('deficit_plan')

    if is_positive:
        headline = f"You can safely invest ₹{surplus:,.0f} per month."
        what_this_means = (
            f"From your net in-hand income of ₹{net_monthly:,.0f}/month, after paying ₹{expenses:,.0f} in living expenses, "
            f"setting aside ₹{buffer_amt:,.0f} as a safety reserve, and funding your emergency safety net with ₹{ef_monthly:,.0f}, "
            f"you have a dependable surplus of ₹{surplus:,.0f} every month for wealth generation."
        )
        actions = [
            f"Continue prioritizing your emergency fund contribution (₹{ef_monthly:,.0f}/month) until fully funded.",
            f"Deploy your ₹{surplus:,.0f} monthly surplus across diversified asset classes matching your horizon.",
            "Review discretionary spending periodically to direct any additional savings into goals."
        ]
        watch_outs = "Market returns fluctuate over short periods; maintain your emergency fund in liquid options."
    else:
        gap = deficit_plan.get('gap_amount', abs(surplus)) if deficit_plan else abs(surplus)
        headline = f"Monthly shortfall of ₹{gap:,.0f} detected."
        what_this_means = (
            f"Your current outflows (₹{expenses:,.0f} in expenses plus commitments) exceed your net in-hand income "
            f"of ₹{net_monthly:,.0f}. Building wealth requires establishing a positive monthly surplus first."
        )
        actions = deficit_plan.get('top_levers', [
            "Review and reduce non-essential discretionary expenses.",
            "Restructure high-cost debt to lower monthly outflows.",
            "Explore opportunities to increase monthly take-home income."
        ]) if deficit_plan else ["Trim discretionary spending to restore balance."]
        watch_outs = "Avoid taking on additional debt or investing in volatile products while in a deficit."

    return {
        "source": "deterministic",
        "headline": headline,
        "what_this_means": what_this_means,
        "three_key_actions": actions[:3],
        "watch_outs": watch_outs
    }


def explain_plan(engine_output: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a plain-language financial explanation with Ollama and deterministic fallback."""
    # Check cache
    cache_key = hashlib.sha256(json.dumps(engine_output, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    # Construct strict structured prompt
    prompt = f"""You are a professional, helpful financial planner in India.
Explain the following pre-calculated financial plan strictly using the provided numbers.
CRITICAL RULES:
1. Use ONLY numbers present in the provided JSON. Do NOT calculate, estimate, or invent ANY new numbers.
2. Return ONLY a valid JSON object with EXACTLY these keys:
   - "headline": Short 1-sentence summary.
   - "what_this_means": 2-3 sentences explaining net income, expenses, and surplus.
   - "three_key_actions": Array of 3 specific actions with amounts.
   - "watch_outs": 1 sentence on risks or precautions.
3. No investment advice on specific company stocks or mutual fund schemes.

PLAN DATA:
{json.dumps(engine_output, default=str)}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "seed": 42},
        "format": "json"
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        raw_text = response.json().get('response', '')

        # Parse JSON
        parsed = json.loads(raw_text)

        # Verify that parsed output contains no hallucinated numbers
        full_text_to_check = f"{parsed.get('headline', '')} {parsed.get('what_this_means', '')} {' '.join(parsed.get('three_key_actions', []))} {parsed.get('watch_outs', '')}"
        if not verify_numbers(full_text_to_check, engine_output):
            # Hallucination detected! Fall back to deterministic template
            result = generate_deterministic_explanation(engine_output)
            result['note'] = "Standard explanation used (AI number verification rejected invalid numbers)."
        else:
            result = {
                "source": "ai",
                "headline": parsed.get("headline", ""),
                "what_this_means": parsed.get("what_this_means", ""),
                "three_key_actions": parsed.get("three_key_actions", []),
                "watch_outs": parsed.get("watch_outs", "")
            }
    except Exception:
        # Ollama offline, timeout, or JSON parse failure -> deterministic fallback
        result = generate_deterministic_explanation(engine_output)

    _CACHE[cache_key] = result
    return result


def explain_step(step_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a focused explanation for a single CalcStep."""
    label = step_data.get('label', 'Calculation')
    formula = step_data.get('formula', '')
    result = step_data.get('formatted_result', step_data.get('result', ''))
    note = step_data.get('note', '')

    explanation = f"{label}: {result}. Calculated as '{formula}'. {note}"
    return {
        "step_id": step_data.get('step_id'),
        "explanation": explanation
    }
