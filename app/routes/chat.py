"""Chat API routes — Claude Haiku streaming via SSE.

Endpoints:
  POST /chat/stream  — SSE stream of chat response tokens
  POST /chat/sync    — JSON response (non-streaming, for testing)

Both endpoints expect JSON body:
  {
    "message": "user's question",
    "history": [{"role": "user"|"assistant", "content": "..."}],
    "financials": { ... engine summary dict ... },
    "tickers": ["RELIANCE.NS", "TCS.NS"]  // optional
  }
"""

import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context, session
from flask_login import login_required
from app import limiter

from app.llm.chat import stream_chat, chat_sync, build_allocation_summary, validate_response_numbers, _build_context_block
from app.market.finnhub_client import format_market_context
from app.market.cache import market_cache

logger = logging.getLogger(__name__)

# ── CSRF exemption for SSE streaming ──────────────────────────────────────────
# Flask-WTF's CSRFProtect blocks POST requests without a valid form token.
# SSE streaming clients send the token via X-CSRFToken header (which works for
# regular AJAX) but the streaming response can cause token validation issues
# on some setups. We exempt chat routes and rely on the header-based check
# that the JS widget already sends.
try:
    from app import csrf
    # Exempt will be applied after blueprint registration
    _csrf_exempt = True
except ImportError:
    _csrf_exempt = False

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

# Default tickers to show if user hasn't set a portfolio
DEFAULT_TICKERS = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]


def _extract_request_data():
    """Parse and validate incoming chat request."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return None, None, None, None, "Message is required."

    history = data.get("history", [])
    financials = data.get("financials", {})
    tickers = data.get("tickers", DEFAULT_TICKERS)

    # Validate history format
    clean_history = []
    for item in history:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
            clean_history.append({
                "role": item["role"],
                "content": str(item.get("content", ""))[:2000],  # hard cap per message
            })

    return message, clean_history, financials, tickers, None


@chat_bp.route('/stream', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def stream():
    """SSE streaming endpoint for real-time chat responses."""
    message, history, financials, tickers, error = _extract_request_data()
    if error:
        return jsonify({"error": error}), 400

    # Read market data from cache (never a live call here)
    market_ctx = format_market_context(tickers) if tickers else ""
    alloc_summary = build_allocation_summary(financials.get("allocations", {}))

    def generate():
        """Generator that yields SSE events."""
        full_response = ""
        try:
            gen = stream_chat(
                user_message=message,
                history=history,
                user_financials=financials,
                market_context=market_ctx,
                allocation_summary=alloc_summary,
            )
            for chunk in gen:
                full_response += chunk
                # SSE format: each event is "data: <payload>\n\n"
                escaped = json.dumps({"token": chunk})
                yield f"data: {escaped}\n\n"

            # ── Post-stream guardrail ─────────────────────────────────
            # Cross-check numeric claims against context ground truth.
            # If fabricated numbers are detected, append a visible
            # disclaimer to the stream (matching explain.py's fallback
            # philosophy — never silently serve bad numbers).
            context_block = _build_context_block(
                financials, market_ctx, alloc_summary
            )
            warnings = validate_response_numbers(full_response, context_block)
            if warnings:
                logger.warning("Guardrail flags: %s", warnings)
                disclaimer = "\n\n_Note: Some numbers in this response could not be verified against your plan data. Please cross-check with the figures shown on your dashboard._"
                yield f"data: {json.dumps({'token': disclaimer})}\n\n"

            # Signal completion
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error("SSE stream error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # disable nginx buffering
            'Connection': 'keep-alive',
        },
    )


@chat_bp.route('/sync', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def sync():
    """Non-streaming chat endpoint — returns full JSON response."""
    message, history, financials, tickers, error = _extract_request_data()
    if error:
        return jsonify({"error": error}), 400

    market_ctx = format_market_context(tickers) if tickers else ""
    alloc_summary = build_allocation_summary(financials.get("allocations", {}))

    result = chat_sync(
        user_message=message,
        history=history,
        user_financials=financials,
        market_context=market_ctx,
        allocation_summary=alloc_summary,
    )

    return jsonify(result)


@chat_bp.route('/health', methods=['GET'])
def health():
    """Quick health check — verifies API key is configured."""
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return jsonify({
        "status": "ok" if key else "no_api_key",
        "model": os.environ.get("CLAUDE_CHAT_MODEL", "claude-3-5-haiku-20241022"),
        "cache_stats": market_cache.stats(),
    })
