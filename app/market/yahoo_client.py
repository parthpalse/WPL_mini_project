"""Keyless quote fallback for NSE/BSE symbols via Yahoo Finance's public chart endpoint.

Finnhub's free tier does not cover Indian exchanges, so the Market Watch would otherwise
stay empty. This is an unofficial endpoint: it can rate-limit or change without notice,
so failures return {} and the UI shows "unavailable" instead of a made-up number.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_TIMEOUT = 6  # seconds
RETRIES = 2
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BankEase/1.0)", "Accept": "application/json"}


def fetch_quote(symbol: str) -> dict[str, Any]:
    """Return a quote dict in the same shape as finnhub_client.get_quote, or {} on failure."""
    for attempt in range(RETRIES):
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=symbol),
                params={"range": "1d", "interval": "1d"},
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(0.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
            price = float(meta["regularMarketPrice"])
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
            change = price - prev if prev else 0.0
            return {
                "symbol": symbol,
                "current": price,
                "change": change,
                "change_pct": (change / prev * 100) if prev else 0.0,
                "high": float(meta.get("regularMarketDayHigh") or 0),
                "low": float(meta.get("regularMarketDayLow") or 0),
                "open": 0.0,
                "prev_close": prev,
                "timestamp": int(meta.get("regularMarketTime") or 0),
            }
        except (requests.exceptions.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
            logger.warning("Yahoo quote failed for %s: %s", symbol, e)
            return {}
    return {}
