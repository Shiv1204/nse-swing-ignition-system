"""Invoke the deployed/local EOD API and optionally send shortlist alerts to a webhook.

Schedule this script after the NSE cash-market close (e.g. 15:45 IST).
Set NSIS_API_URL and optionally NSIS_ALERT_WEBHOOK in the environment.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def post_json(url: str, payload: dict, timeout: int = 180) -> dict:
    request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def alert_payload(result: dict) -> dict:
    shortlist = result.get("shortlist", [])
    return {
        "event": "nsis_eod_scan",
        "universe_as_of_date": result.get("universe_as_of_date"),
        "market_regime": (result.get("market_regime") or {}).get("regime", "unavailable"),
        "shortlist_count": len(shortlist),
        "shortlist": [
            {"symbol": row.get("symbol"), "score": (row.get("ranking") or {}).get("score"),
             "setups": row.get("passed_setups", [])}
            for row in shortlist
        ],
        "warning": "Research candidates only. No trade orders are placed.",
    }


def main() -> int:
    base = os.getenv("NSIS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    sync = os.getenv("NSIS_SYNC_BEFORE_SCAN", "false").lower() in {"1", "true", "yes"}
    try:
        result = post_json(f"{base}/api/v1/pipeline/eod", {"sync_market_data": sync, "shortlist_limit": 30})
    except (URLError, HTTPError, TimeoutError, ValueError) as exc:
        print(f"EOD scan failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "symbols_ranked": result.get("symbols_ranked"),
        "shortlist_count": result.get("shortlist_count"),
        "market_regime": (result.get("market_regime") or {}).get("regime", "unavailable"),
        "sync_errors": result.get("symbols_sync_failed"),
        "notes": result.get("notes", []),
    }, indent=2))
    webhook = os.getenv("NSIS_ALERT_WEBHOOK")
    if webhook:
        try:
            request = Request(webhook, data=json.dumps(alert_payload(result)).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=20) as response:
                print(f"Alert webhook delivered: HTTP {response.status}")
        except (URLError, HTTPError, TimeoutError) as exc:
            print(f"Alert webhook failed: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
