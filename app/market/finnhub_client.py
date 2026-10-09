"""Finnhub REST API client for BankEase market data.

Replaces yfinance with Finnhub's lightweight REST endpoints.
Free tier: 60 calls/min — all calls route through the shared TTL cache
so the chatbot never makes a live API call mid-conversation.

Key endpoints used:
  /quote           — real-time price, day change, high/low
  /stock/metric    — P/E, 52-week high/low, market cap
  /company-news    — recent headlines for context enrichment

Environment:
  FINNHUB_API_KEY  — required, set in .env
"""

from __future__ import annotations


import os
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

import requests

from app.market.cache import market_cache

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
REQUEST_TIMEOUT = 8  # seconds — fast-fail to keep UX snappy


def _get(endpoint: str, params: dict | None = None) -> dict:
    """Low-level GET wrapper with API key injection and error handling."""
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set — returning empty data")
        return {}

    url = f"{FINNHUB_BASE}{endpoint}"
    all_params = {"token": FINNHUB_API_KEY}
    if params:
        all_params.update(params)

    try:
        resp = requests.get(url, params=all_params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("Finnhub timeout on %s", endpoint)
        return {}
    except requests.exceptions.RequestException as e:
        logger.warning("Finnhub request failed: %s", e)
        return {}
    except ValueError:
        logger.warning("Finnhub returned non-JSON on %s", endpoint)
        return {}


# ─── Public API ───────────────────────────────────────────────────────────────


def get_quote(symbol: str) -> dict[str, Any]:
    """Fetch real-time quote for a symbol (e.g. 'RELIANCE.NS').

    Returns dict with keys: current, change, change_pct, high, low, open, prev_close, timestamp.
    All values are floats. Returns empty dict on failure.
    """
    cache_key = f"quote:{symbol}"
    cached = market_cache.get(cache_key)
    if cached is not None:
        return cached

    raw = _get("/quote", {"symbol": symbol})
    if not raw or raw.get("c", 0) == 0:
        return {}

    result = {
        "symbol": symbol,
        "current": raw.get("c", 0),
        "change": raw.get("d", 0),
        "change_pct": raw.get("dp", 0),
        "high": raw.get("h", 0),
        "low": raw.get("l", 0),
        "open": raw.get("o", 0),
        "prev_close": raw.get("pc", 0),
        "timestamp": raw.get("t", 0),
    }
    market_cache.set(cache_key, result, ttl=90)
    return result


def get_metrics(symbol: str) -> dict[str, Any]:
    """Fetch fundamental metrics (P/E, 52-week range, market cap, etc.).

    Uses Finnhub's /stock/metric endpoint with metric=all.
    Returns a flat dict of the most useful metrics. Empty dict on failure.
    """
    cache_key = f"metrics:{symbol}"
    cached = market_cache.get(cache_key)
    if cached is not None:
        return cached

    raw = _get("/stock/metric", {"symbol": symbol, "metric": "all"})
    metrics = raw.get("metric", {})
    if not metrics:
        return {}

    result = {
        "symbol": symbol,
        "pe_ratio": metrics.get("peBasicExclExtraTTM"),
        "pb_ratio": metrics.get("pbAnnual"),
        "week52_high": metrics.get("52WeekHigh"),
        "week52_low": metrics.get("52WeekLow"),
        "market_cap": metrics.get("marketCapitalization"),
        "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
        "beta": metrics.get("beta"),
        "eps_ttm": metrics.get("epsBasicExclExtraItemsTTM"),
    }
    market_cache.set(cache_key, result, ttl=300)  # fundamentals change slowly
    return result


def get_news(symbol: str, days: int = 3, limit: int = 5) -> list[dict]:
    """Fetch recent company news headlines.

    Returns list of dicts with keys: headline, summary, source, url, datetime.
    """
    cache_key = f"news:{symbol}:{days}"
    cached = market_cache.get(cache_key)
    if cached is not None:
        return cached

    today = datetime.utcnow().strftime("%Y-%m-%d")
    from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    raw = _get("/company-news", {"symbol": symbol, "from": from_date, "to": today})
    if not isinstance(raw, list):
        return []

    articles = []
    for item in raw[:limit]:
        articles.append({
            "headline": item.get("headline", ""),
            "summary": item.get("summary", "")[:200],
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "datetime": item.get("datetime", 0),
        })

    market_cache.set(cache_key, articles, ttl=600)  # news: 10-min cache
    return articles


def get_market_snapshot(symbols: list[str]) -> list[dict]:
    """Batch-fetch quotes for a list of symbols.

    Returns a list of quote dicts, skipping any that fail.
    Used by the chat context builder to assemble the lean market block.
    """
    results = []
    for sym in symbols:
        quote = get_quote(sym)
        if quote:
            results.append(quote)
    return results


def format_market_context(symbols: list[str]) -> str:
    """Build a compact, one-line-per-ticker market context string for the chatbot prompt.

    Example output:
      RELIANCE.NS ₹2,847.50 (+1.2%) | TCS.NS ₹3,920.00 (-0.4%)
    """
    quotes = get_market_snapshot(symbols)
    if not quotes:
        return "Live market data unavailable."

    parts = []
    for q in quotes:
        sign = "+" if q["change_pct"] >= 0 else ""
        parts.append(f"{q['symbol']} ₹{q['current']:,.2f} ({sign}{q['change_pct']:.1f}%)")

    return " | ".join(parts)
