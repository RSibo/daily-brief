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

"""Manual CLI test runner for Phase 3: Aggregator & Briefing Writer Agent.

Usage:
    uv run python -m tests.manual.run_writer_standalone
    uv run python tests/manual/run_writer_standalone.py --live
"""

import argparse
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from app.app_utils.typing import DraftBriefingPayload
from app.tools.internal_comms_tools import harvest_all_internal_communications
from app.tools.market_news_tools import harvest_all_market_news
from app.tools.synthesis_tools import assemble_draft_briefing

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Briefing Writer Agent manually.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run against live harvester tools instead of synthetic baseline data.",
    )
    args = parser.parse_args()

    sydney_now = datetime.now(SYDNEY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    print("=" * 80)
    print(f"[*] Starting Briefing Writer Synthesis (Sydney Time: {sydney_now})")
    print(f"[*] Mode: {'LIVE HARVEST' if args.live else 'STANDALONE MOCK HARVEST'}")
    print("=" * 80)

    if args.live:
        print("[*] Harvesting internal communications (24h window)...")
        internal_data = harvest_all_internal_communications(lookback_hours=24)
        print("[*] Harvesting market news intelligence (72h window)...")
        market_data = harvest_all_market_news(lookback_hours=72)
    else:
        print("[*] Using synthetic high-fidelity fixture data...")
        internal_data = {
            "leadership_threads": [
                {
                    "thread_id": "thread-001",
                    "sender_name": "Simon Elisha",
                    "sender_email": "selisha@google.com",
                    "subject": "Optus VAIS Escalation and Model Armor Timeline",
                    "snippet": "Need alignment on Model Armor GA schedule for Optus security board review on Thursday.",
                    "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-001",
                    "timestamp": "2026-09-04T08:15:00Z",
                    "is_vip": True,
                    "vip_category": "leadership",
                    "requires_action": True,
                    "action_summary": "Confirm Model Armor GA timeline with product engineering.",
                },
                {
                    "thread_id": "thread-002",
                    "sender_name": "Vamsi Ramakrishnan",
                    "sender_email": "vamsi@google.com",
                    "subject": "Woolworths GE FDE Scoping",
                    "snippet": "Woolies team submitted the final technical architecture for the shopping agent POC.",
                    "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-002",
                    "timestamp": "2026-09-03T21:30:00Z",
                    "is_vip": True,
                    "vip_category": "leadership",
                    "requires_action": False,
                    "action_summary": "Review FDE scoping document before 2 PM standup.",
                },
            ],
            "direct_report_threads": [],
            "chat_space_threads": [
                {
                    "thread_id": "space-fde-01",
                    "sender_name": "AuNZ AI FDE Team",
                    "sender_email": "spaces/AAQA1aF4JGg",
                    "subject": "Shopping Agent Cluster Verification",
                    "snippet": "End-to-end latency benchmarks completed across 10 concurrent customer journeys.",
                    "deep_link": "https://chat.google.com/room/AAQA1aF4JGg",
                    "timestamp": "2026-09-04T07:45:00Z",
                    "is_vip": False,
                    "requires_action": False,
                }
            ],
            "calendar_events": [
                {
                    "title": "AuNZ AI CE Fortnightly Standup",
                    "start_time": "09:30 AM",
                    "prep_link": "https://docs.google.com/document/d/standup-agenda",
                    "attendees": [
                        "selisha@google.com",
                        "vamsi@google.com",
                        "mscutt@google.com",
                    ],
                    "objective": "Q3 Target Execution & Escalation Review",
                },
                {
                    "title": "Woolworths Executive Interlock",
                    "start_time": "02:00 PM",
                    "prep_link": "https://docs.google.com/document/d/woolies-exec",
                    "attendees": ["rob@woolworths.com.au", "rsibo@google.com"],
                    "objective": "Shopping Agent Architecture Sign-Off",
                },
            ],
            "hot_list_matches": {
                "Optus VAIS & Model Armor Blocker": [
                    {
                        "subject": "Optus Security Architecture Alignment",
                        "snippet": "Model Armor evaluation confirmed; waiting on GA commitment.",
                        "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-001",
                    }
                ]
            },
        }

        market_data = {
            "announcements": [
                {
                    "domain": "foundation_models",
                    "entity": "Google DeepMind",
                    "headline": "Gemini 2.5 Flash updates deployed with expanded tool calling",
                    "summary": "Enhanced low-latency endpoints with native agent tool execution.",
                    "source_url": "https://blog.google/technology/ai/gemini-2-5-model-updates/",
                    "date": "2026-09-04",
                    "verified": True,
                },
                {
                    "domain": "cloud_ai_ml",
                    "entity": "Google Cloud",
                    "headline": "Vertex AI Model Armor adds automated prompt injection shields",
                    "summary": "Managed inline defense layer mitigating jailbreak attempts and PII leakage.",
                    "source_url": "https://cloud.google.com/vertex-ai/docs/generative-ai/model-armor/overview",
                    "date": "2026-09-04",
                    "verified": True,
                },
            ]
        }

    print("[*] Assembling executive draft briefing...")
    raw_payload = assemble_draft_briefing(
        internal_comms_data=internal_data,
        market_news_data=market_data,
        hot_list_config_path="config/hot_list.md",
    )

    if "error" in raw_payload:
        print(
            f"[!] Assembly encountered an error:\n{json.dumps(raw_payload['error'], indent=2)}"
        )
        sys.exit(1)

    payload = DraftBriefingPayload(**raw_payload)

    print("\n" + "=" * 80)
    print("DRAFT BRIEFING PREVIEW (EXACT HTML & SECTION ORDER)")
    print("=" * 80)
    print(payload.raw_html)
    print("=" * 80)
    print("[+] Phase 3 Aggregator & Briefing Writer standalone verification complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
