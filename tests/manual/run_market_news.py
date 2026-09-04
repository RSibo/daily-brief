# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Manual CLI test runner for Phase 2: External Market News Harvest Agent.

Usage:
    uv run python -m tests.manual.run_market_news
    uv run python tests/manual/run_market_news.py --lookback 48
"""

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from app.app_utils.typing import MarketHarvestPayload
from app.tools.market_news_tools import harvest_all_market_news

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run External Market News Harvester manually."
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=48,
        help="Lookback window duration in hours (default: 48).",
    )
    args = parser.parse_args()

    sydney_now = datetime.now(SYDNEY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("=" * 80)
    print(f"[*] Starting Market News Harvest (Sydney Time: {sydney_now})")
    print(f"[*] Enforcing Trailing {args.lookback}-Hour Window...")
    print("=" * 80)

    raw_payload = harvest_all_market_news(lookback_hours=args.lookback)

    if "error" in raw_payload:
        print(
            f"[!] Harvest encountered an error:\n{json.dumps(raw_payload['error'], indent=2)}"
        )
        sys.exit(1)

    payload = MarketHarvestPayload(**raw_payload)

    print(
        f"\n[+] Successfully harvested {len(payload.announcements)} verified announcements."
    )
    print(
        f"[+] Lookback Window: {payload.lookback_hours} hours | Timestamp: {payload.harvest_timestamp}\n"
    )

    domains = {
        "foundation_models": "1. Foundation Models & Open Weights",
        "agents_frameworks": "2. AI Agents & Multi-Agent Frameworks",
        "cloud_ai_ml": "3. Cloud AI/ML Platforms & Accelerators",
    }

    for domain_key, domain_label in domains.items():
        domain_items = [
            item for item in payload.announcements if item.domain == domain_key
        ]
        print(f"\n--- {domain_label} ({len(domain_items)} items) ---")
        if not domain_items:
            print("  (No updates within the lookback window)")
            continue

        for i, item in enumerate(domain_items, 1):
            print(f"\n  [{i}] {item.entity} ({item.date})")
            print(f"      Headline: {item.headline}")
            print(f"      Significance: {item.summary}")
            print(f"      Source: {item.source_url}")

    print("\n" + "=" * 80)
    print("[*] Phase 2 Market News Harvest manual verification complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
