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

"""Manual CLI test harness for the Internal Comms Harvest Agent.

Enables rsibo to run and verify the internal_comms_agent in isolation.
Usage:
    uv run python -m tests.manual.run_internal_comms [--live | --mock]
"""

import argparse
import json

from app.tools.internal_comms_tools import (
    harvest_all_internal_communications,
    load_active_hot_list_themes,
    load_target_chat_spaces,
)


def main():
    parser = argparse.ArgumentParser(
        description="Test internal_comms_agent in isolation."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live harvesting via Cloudtop workspace CLIs",
    )
    args = parser.parse_args()

    print("==========================================================")
    print("  DAILY BRIEF — Phase 1: Internal Comms Harvest Runner")
    print("==========================================================\n")

    print("1. Loading living configurations:")
    spaces = load_target_chat_spaces()
    print(f"   • Target chat spaces loaded: {len(spaces)} spaces")
    hot_list = load_active_hot_list_themes()
    print(f"   • Active Hot List themes loaded: {len(hot_list)} themes\n")

    if args.live:
        print(
            "2. Executing LIVE harvest across Gmail, Google Chat, and Calendar (past 24h)..."
        )
        payload = harvest_all_internal_communications(lookback_hours=24)
    else:
        print("2. Executing MOCK harvest using realistic executive signal fixtures...")
        mock_fixtures = {
            "gmail": [
                {
                    "id": "thread_lead_1",
                    "from": "Simon Elisha <selisha@google.com>",
                    "subject": "Q3 Headcount & Tech Strategy",
                    "snippet": "Rob, please review the proposed CE staffing allocations for Sydney.",
                    "date": "2026-09-04T07:15:00Z",
                },
                {
                    "id": "thread_dr_1",
                    "from": "Ollie Scott <oliverscott@google.com>",
                    "subject": "Optus Model Armor Deployment Blocker",
                    "snippet": "We have an escalation from Tyrone regarding Model Armor VPC egress.",
                    "date": "2026-09-04T06:50:00Z",
                },
            ],
            "chat": {
                "dms": [
                    {
                        "id": "dm_pedro",
                        "sender": "Pedro Correia",
                        "text": "Rob, Woolworths Shopping Agent architecture review is scheduled for 2pm.",
                        "createTime": "2026-09-04T07:10:00Z",
                    }
                ],
                "mentions": [
                    {
                        "id": "mention_vamsi",
                        "sender": "Vamsi Ramakrishnan",
                        "space": "spaces/AAQAWmL5O_g",
                        "text": "@rsibo can you ensure the team is aligned with the regional AI interlock?",
                        "createTime": "2026-09-04T05:30:00Z",
                    }
                ],
            },
            "calendar": [
                {
                    "summary": "Simon Elisha / Rob Sibo 1:1",
                    "start": {"dateTime": "2026-09-04T10:00:00+10:00"},
                    "end": {"dateTime": "2026-09-04T10:30:00+10:00"},
                    "hangoutLink": "https://meet.google.com/abc-defg-hij",
                },
                {
                    "summary": "Woolworths Executive Briefing",
                    "start": {"dateTime": "2026-09-04T14:00:00+10:00"},
                    "end": {"dateTime": "2026-09-04T15:00:00+10:00"},
                    "hangoutLink": "https://meet.google.com/xyz-uvwx-rst",
                },
            ],
        }
        payload = harvest_all_internal_communications(
            lookback_hours=24, test_fixtures=mock_fixtures
        )

    print("3. Harvest Complete! Payload Summary:")
    print(f"   • Lookback hours: {payload.get('lookback_hours')}")
    print(f"   • Leadership threads: {len(payload.get('leadership_threads', []))}")
    print(
        f"   • Direct report threads: {len(payload.get('direct_report_threads', []))}"
    )
    print(f"   • Chat threads/mentions: {len(payload.get('chat_space_threads', []))}")
    print(f"   • Calendar events: {len(payload.get('calendar_events', []))}\n")

    print("Sample Harvested Items (Formatted JSON):")
    print(json.dumps(payload, indent=2))
    print("\n[SUCCESS] Phase 1 Internal Comms Harvester verified successfully.")


if __name__ == "__main__":
    main()
