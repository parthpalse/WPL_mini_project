"""Open-source LLM chat layer for BankEase financial assistant.

Design constraints (speed-first):
  • Provider: any OpenAI-compatible /chat/completions endpoint serving an
    open-source model — local Ollama (default), Groq, OpenRouter, Hugging Face.
  • Context: lean structured block each turn, NOT full history + full profile.
  • Streaming: yields tokens from the provider's SSE stream so the UI shows
    first tokens immediately via SSE.
  • Separation: this module handles conversational chat only; explain.py
    (Ollama) stays untouched for deterministic number explanations.

Anti-hallucination:
  • All financial numbers come from the engine, never from the LLM.
  • Market data comes from cached Finnhub quotes.
  • Post-generation guardrail cross-checks numeric claims.
"""

from __future__ import annotations


import os
import re
import json
import logging
from typing import Any, Generator, Optional

import requests

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))  # headroom: reasoning models spend tokens thinking
LLM_TIMEOUT = (10, 60)  # (connect, read) seconds


def is_configured() -> bool:
    """Local endpoints (Ollama) need no key; hosted providers do."""
    is_local = "localhost" in LLM_BASE_URL or "127.0.0.1" in LLM_BASE_URL
    return is_local or bool(LLM_API_KEY)

# Maximum chat history turns retained (user + assistant pairs)
MAX_HISTORY_TURNS = 6

# System prompt — kept short to minimize per-turn cost
SYSTEM_PROMPT = """\
You are BankEase AI, a helpful Indian personal finance assistant.

RULES:
1. Use ONLY the numbers provided in the [CONTEXT] block. Never invent, estimate, or calculate new financial numbers.
2. Refer to the user's actual surplus, allocations, and live market data from [CONTEXT].
3. Be concise — aim for 2–4 sentences per response unless the user asks for detail.
4. No specific stock picks or mutual fund scheme recommendations. Discuss asset classes only.
5. Format currency in Indian notation with commas (₹1,50,000 / ₹1.5 L), never with spaces between digit groups.
6. If asked about something outside [CONTEXT], say you don't have that data rather than guessing.
7. Be warm and educational, not salesy.
8. For tax questions, answer directly from [TAX RULES] and [TAX CALC] in [CONTEXT]: state the regime, the taxable income, and the tax payable, and say clearly when the tax is zero. Salary is gross income, not taxable income. Never say you need the slabs, they are provided. If the user asks about a different or hypothetical income (a raise), use the take-home and monthly surplus from [TAX CALC], not the current surplus, and give the savings for the number of months asked. Give one clean answer; do not second-guess or restate figures. Do not apply deductions beyond those listed there; mention that the old regime needs 80C/80D etc. to be worth comparing.
9. Formatting: short paragraphs plus Markdown bullet lists, one bullet per line starting with "- ", with a **bold** label at the start of each bullet. NEVER use tables, headings or code blocks.
"""


def _build_context_block(
    user_financials: dict[str, Any],
    market_context: str,
    allocation_summary: str,
    tax_context: str = "",
) -> str:
    """Build the compact [CONTEXT] block injected at the top of each turn.

    This is the single biggest lever for speed and cost — kept to ~200 tokens.
    """
    surplus = user_financials.get("monthly_surplus", 0)
    income = user_financials.get("net_monthly_income", 0)
    expenses = user_financials.get("total_monthly_expenses", 0)
    ef = user_financials.get("emergency_fund_monthly", 0)
    buffer = user_financials.get("safety_buffer_monthly", 0)
    risk = user_financials.get("risk_profile", "balanced")
    is_positive = user_financials.get("surplus_is_positive", surplus > 0)

    status = "SURPLUS" if is_positive else "DEFICIT"

    lines = [
        "[CONTEXT]",
        f"Status: {status}",
        f"Net income: ₹{income:,.0f}/mo | Expenses: ₹{expenses:,.0f}/mo",
        f"Emergency fund: ₹{ef:,.0f}/mo | Buffer: ₹{buffer:,.0f}/mo",
        f"Current monthly surplus (at the saved profile income): ₹{abs(surplus):,.0f}/mo ({'investable' if is_positive else 'shortfall'})",
        f"Risk profile: {risk}",
    ]

    if allocation_summary:
        lines.append(f"Allocation: {allocation_summary}")

    if market_context:
        lines.append(f"Live: {market_context}")

    if tax_context:
        lines.append(tax_context)

    lines.append("[/CONTEXT]")
    return "\n".join(lines)


def build_allocation_summary(allocations: dict) -> str:
    """Compress allocations dict into a one-line summary for the context block."""
    if not allocations:
        return ""

    strat = (
        allocations.get("balanced")
        or allocations.get("safe")
        or allocations.get("growth")
        or {}
    )

    parts = []
    for product, detail in strat.items():
        amt = detail.get("amount", 0) if isinstance(detail, dict) else 0
        if amt > 0:
            name = product.replace("_", " ").title()
            parts.append(f"{name}: ₹{amt:,.0f}")

    return " | ".join(parts) if parts else ""


def _trim_history(history: list[dict], max_turns: int = MAX_HISTORY_TURNS) -> list[dict]:
    """Keep only the last N user+assistant turn pairs to bound context size."""
    if len(history) <= max_turns * 2:
        return history
    return history[-(max_turns * 2):]


def _collect_context_numbers(context_block: str) -> set[float]:
    """Extract all numbers from the context block for guardrail validation."""
    numbers = set()
    raw = re.findall(r'₹?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', context_block)
    for m in raw:
        clean = m.replace(',', '').strip()
        try:
            val = float(clean)
            if val > 0:
                numbers.add(round(val, 2))
        except ValueError:
            pass
    # Also add percentages
    pcts = re.findall(r'([+-]?[0-9]+(?:\.[0-9]+)?)\s*%', context_block)
    for p in pcts:
        try:
            numbers.add(round(float(p), 2))
        except ValueError:
            pass
    return numbers


# Models often write Indian grouping with spaces ("₹11 25 000", sometimes narrow no-break
# spaces) instead of commas; rejoin those so they are checked as one number.
_SPACED_GROUPS = re.compile(r"\b\d{1,2}(?:[ ,\u00a0\u202f]\d{2})*[ ,\u00a0\u202f]\d{3}\b")


def _join_spaced_digit_groups(text: str) -> str:
    def _join(m: re.Match) -> str:
        token = m.group(0)
        # leave plain comma-grouped numbers alone; only repair ones containing spaces
        return re.sub(r"[ ,  ]", "", token) if re.search(r"[   ]", token) else token

    return _SPACED_GROUPS.sub(_join, text)


def validate_response_numbers(response_text: str, context_block: str) -> list[str]:
    """Cross-check numeric claims in the response against context ground truth.

    Returns a list of warning strings for any numbers that appear fabricated.
    Does NOT block the response — used for logging/flagging.
    """
    allowed = _collect_context_numbers(context_block)
    if not allowed:
        return []
    response_text = _join_spaced_digit_groups(response_text)

    # Extract numbers from response
    response_nums = re.findall(r'₹?\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)', response_text)
    warnings = []
    for m in response_nums:
        clean = m.replace(',', '').strip()
        try:
            val = float(clean)
        except ValueError:
            continue
        # Skip trivial numbers (1-10, years, percentages under 100)
        if val <= 10 or val in {12, 24, 36, 100, 1000}:
            continue
        # Check against allowed with tolerance
        matched = any(
            abs(val - a) <= 1.0
            or abs(val - a / 12) <= 1.0
            or abs(val * 12 - a) <= 1.0
            for a in allowed
        )
        if not matched:
            warnings.append(f"Possibly fabricated number: {val}")

    return warnings


def stream_chat(
    user_message: str,
    history: list[dict],
    user_financials: dict[str, Any],
    market_context: str = "",
    allocation_summary: str = "",
    tax_context: str = "",
) -> Generator[str, None, Optional[dict]]:
    """Stream the LLM response token-by-token.

    Yields:
        str chunks (partial tokens) as they arrive from the provider.

    Returns (via generator return value):
        dict with {"full_response": str, "guardrail_warnings": list[str]}
        or None on error.

    Usage:
        gen = stream_chat(msg, history, financials, market, allocs)
        full = ""
        for chunk in gen:
            full += chunk
            send_to_client(chunk)
    """
    if not is_configured():
        yield "⚠️ Chat unavailable — LLM_API_KEY not configured."
        return

    # Build the lean context block
    context_block = _build_context_block(user_financials, market_context, allocation_summary, tax_context)

    # Trim history
    trimmed = _trim_history(history)

    # Assemble messages: inject context into the first user message of this turn
    messages = list(trimmed)  # shallow copy
    messages.append({
        "role": "user",
        "content": f"{context_block}\n\n{user_message}",
    })

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
    }
    if "gpt-oss" in LLM_MODEL:
        # Reasoning model: keep thinking short so it can't exhaust max_tokens before answering.
        payload["reasoning_effort"] = "low"

    full_response = ""
    try:
        with requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=LLM_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            resp.encoding = "utf-8"  # text/event-stream has no charset; requests would assume latin-1
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                choices = json.loads(data).get("choices") or [{}]
                text = (choices[0].get("delta") or {}).get("content") or ""
                if text:
                    full_response += text
                    yield text

    except requests.HTTPError as e:
        logger.error("LLM API error: %s", e)
        yield f"\n\n⚠️ Chat error: {e.response.status_code} from LLM provider."
        return
    except requests.RequestException as e:
        logger.error("LLM connection error: %s", e)
        yield "\n\n⚠️ Chat unavailable — could not reach the LLM provider."
        return
    except Exception as e:
        logger.error("Chat stream error: %s", e)
        yield "\n\n⚠️ Unexpected chat error. Please try again."
        return

    # Post-generation guardrail
    warnings = validate_response_numbers(full_response, context_block)
    if warnings:
        logger.warning("Guardrail flags on chat response: %s", warnings)

    return {"full_response": full_response, "guardrail_warnings": warnings}


def chat_sync(
    user_message: str,
    history: list[dict],
    user_financials: dict[str, Any],
    market_context: str = "",
    allocation_summary: str = "",
    tax_context: str = "",
) -> dict[str, Any]:
    """Non-streaming variant — collects the full response and returns it.

    Useful for testing or non-SSE contexts.
    """
    full = ""
    result = None
    gen = stream_chat(user_message, history, user_financials, market_context, allocation_summary, tax_context)
    for chunk in gen:
        full += chunk
    # Generator return value isn't accessible via for-loop, so we reconstruct
    context_block = _build_context_block(user_financials, market_context, allocation_summary, tax_context)
    warnings = validate_response_numbers(full, context_block)

    return {
        "response": full,
        "guardrail_warnings": warnings,
        "model": LLM_MODEL,
    }
