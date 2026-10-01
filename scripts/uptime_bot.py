#!/usr/bin/env python3
"""
BankEase Uptime Bot
-------------------
A lightweight uptime monitoring bot that periodically pings the BankEase healthcheck
endpoint, logs latency, keeps cloud services (e.g. Render free tier) awake,
and optionally triggers alerts if the service is down.

Usage:
    python scripts/uptime_bot.py --url https://<your-app>.onrender.com/health --interval 300
"""

import argparse
import os
import sys
import time
from datetime import datetime
import urllib.request
import urllib.error


def ping(url: str, timeout: int = 15) -> tuple[bool, int, float, str]:
    """Pings the target URL and returns (success, status_code, elapsed_seconds, message)."""
    start = time.time()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BankEase-UptimeBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.time() - start
            return True, resp.status, elapsed, resp.reason
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return False, e.code, elapsed, e.reason
    except urllib.error.URLError as e:
        elapsed = time.time() - start
        return False, 0, elapsed, str(e.reason)
    except Exception as e:
        elapsed = time.time() - start
        return False, 0, elapsed, str(e)


def run_bot(url: str, interval: int = 300, webhook_url: str | None = None):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 BankEase Uptime Bot started")
    print(f"Target URL: {url}")
    print(f"Ping interval: {interval} seconds ({interval // 60} mins)\n")

    consecutive_failures = 0

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success, code, elapsed, reason = ping(url)

        if success:
            consecutive_failures = 0
            print(f"[{timestamp}] ✅ [OK] HTTP {code} - Latency: {elapsed:.2f}s")
        else:
            consecutive_failures += 1
            print(f"[{timestamp}] ❌ [DOWN] HTTP {code or 'ERR'} ({reason}) - Failures: {consecutive_failures}")

            if webhook_url and consecutive_failures == 1:
                # Optional: Send alert to webhook (Discord / Slack)
                try:
                    payload = f'{{"text": "🚨 BankEase Alert: Service at {url} appears DOWN! ({reason})"}}'.encode("utf-8")
                    alert_req = urllib.request.Request(
                        webhook_url,
                        data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "BankEase-UptimeBot/1.0"}
                    )
                    urllib.request.urlopen(alert_req, timeout=10)
                except Exception as ex:
                    print(f"[{timestamp}] ⚠️ Failed to send webhook alert: {ex}")

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BankEase Uptime Bot")
    parser.add_argument(
        "--url",
        default=os.environ.get("UPTIME_TARGET_URL", "http://127.0.0.1:5000/health"),
        help="Healthcheck URL to ping (default: $UPTIME_TARGET_URL or http://127.0.0.1:5000/health)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("UPTIME_INTERVAL", "300")),
        help="Check interval in seconds (default: 300s / 5 minutes)"
    )
    parser.add_argument(
        "--webhook",
        default=os.environ.get("ALERT_WEBHOOK_URL", None),
        help="Optional webhook URL for downtime alerts"
    )

    args = parser.parse_args()
    try:
        run_bot(url=args.url, interval=args.interval, webhook_url=args.webhook)
    except KeyboardInterrupt:
        print("\n👋 Uptime Bot stopped by user.")
        sys.exit(0)
