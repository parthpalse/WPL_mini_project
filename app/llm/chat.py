"""Claude Haiku chat layer for BankEase financial assistant.

Design constraints (speed-first):
  • Model: Claude 3.5 Haiku — low-latency, high-throughput, $5-friendly.
  • Context: lean structured block each turn, NOT full history + full profile.
  • Streaming: yields tokens via Anthropic's streaming API so the UI shows
    first tokens immediately via SSE.
  • Separation: this module handles conversational chat only; explain.py
    (Ollama) stays untouched for deterministic number explanations.

Anti-hallucination:
  • All financial numbers come from the engine, never from the LLM.
  • Market data comes from cached Finnhub quotes.
  • Post-generation guardrail cross-checks numeric claims.
"""

import os
import re
import json
import logging
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_CHAT_MODEL", "claude-3-5-haiku-20241022")
MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "512"))

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
5. Format currency in Indian notation (₹1,50,000 / ₹1.5 L).
6. If asked about something outside [CONTEXT], say you don't have that data rather than guessing.
7. Be warm and educational, not salesy.
"""


def _build_context_block(
    user_financials: dict[str, Any],
    market_context: str,
    allocation_summary: str,
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
        f"Monthly surplus: ₹{abs(surplus):,.0f}/mo ({'investable' if is_positive else 'shortfall'})",
        f"Risk profile: {risk}",
    ]

    if allocation_summary:
        lines.append(f"Allocation: {allocation_summary}")

    if market_context:
        lines.append(f"Live: {market_context}")

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


def validate_response_numbers(response_text: str, context_block: str) -> list[str]:
    """Cross-check numeric claims in the response against context ground truth.

    Returns a list of warning strings for any numbers that appear fabricated.
    Does NOT block the response — used for logging/flagging.
    """
    allowed = _collect_context_numbers(context_block)
    if not allowed:
        return []

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
) -> Generator[str, None, Optional[dict]]:
    """Stream Claude Haiku response token-by-token.

    Yields:
        str chunks (partial tokens) as they arrive from Anthropic.

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
    if not ANTHROPIC_API_KEY:
        yield "⚠️ Chat unavailable — ANTHROPIC_API_KEY not configured."
        return

    try:
        import anthropic
    except ImportError:
        yield "⚠️ Chat unavailable — `anthropic` package not installed. Run: pip install anthropic"
        return

    # Build the lean context block
    context_block = _build_context_block(user_financials, market_context, allocation_summary)

    # Trim history
    trimmed = _trim_history(history)

    # Assemble messages: inject context into the first user message of this turn
    messages = list(trimmed)  # shallow copy
    messages.append({
        "role": "user",
        "content": f"{context_block}\n\n{user_message}",
    })

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    full_response = ""
    try:
        with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text

    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        yield f"\n\n⚠️ Chat error: {e.message if hasattr(e, 'message') else str(e)}"
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
) -> dict[str, Any]:
    """Non-streaming variant — collects the full response and returns it.

    Useful for testing or non-SSE contexts.
    """
    full = ""
    result = None
    gen = stream_chat(user_message, history, user_financials, market_context, allocation_summary)
    for chunk in gen:
        full += chunk
    # Generator return value isn't accessible via for-loop, so we reconstruct
    context_block = _build_context_block(user_financials, market_context, allocation_summary)
    warnings = validate_response_numbers(full, context_block)

    return {
        "response": full,
        "guardrail_warnings": warnings,
        "model": CLAUDE_MODEL,
    }
