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

"""Standalone Manual Runner for Phase 4: Chief of Staff Reviewer & Editorial Loop.

Executes a simulation of the writer-reviewer editorial refinement cycle:
1. Synthesizes a baseline executive briefing draft.
2. Demonstrates the rejection gate: feeds a draft with VP standard violations
   (banned hyperbole, emojis, incorrect sentence count) and shows structured critique.
3. Demonstrates the approval gate: audits the fully compliant executive draft,
   emitting 'approve' and escalating loop exit.
4. Outputs the final serialized FinalBriefingPayload.

Usage:
    uv run python -m tests.manual.run_editorial_loop
"""

from unittest.mock import MagicMock

from app.tools.editor_tools import (
    evaluate_briefing_draft,
    finalize_approved_briefing,
    lint_vp_standards,
)
from app.tools.synthesis_tools import assemble_draft_briefing


def run_editorial_simulation() -> None:
    """Runs an interactive terminal simulation of the editorial review loop."""
    print("=" * 80)
    print(" [STAGE 3] CHIEF OF STAFF REVIEWER & EDITORIAL LOOP SIMULATION")
    print("=" * 80)

    # 1. Synthesize baseline draft
    print("\n--- [Step 1] Synthesizing Baseline Executive Draft ---")
    mock_internal_comms = {
        "harvest_timestamp": "2026-09-04T08:00:00+10:00",
        "lookback_hours": 24,
        "leadership_threads": [
            {
                "source": "gmail",
                "thread_id": "thread-elisha-1",
                "sender_name": "Simon Elisha",
                "sender_email": "elisha@google.com",
                "timestamp": "2026-09-04T07:15:00Z",
                "subject": "Optus Model Armor & Architecture Escalation",
                "snippet": "Need urgent confirmation on the APAC model armor deployment.",
                "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-elisha-1",
            }
        ],
        "direct_report_threads": [
            {
                "source": "chat",
                "thread_id": "thread-alex-1",
                "sender_name": "Alex Chi",
                "sender_email": "alexchi@google.com",
                "timestamp": "2026-09-04T07:45:00Z",
                "subject": "Woolworths FDE/SWE Workshop Readiness",
                "snippet": "Pre-workshop customer briefing deck ready for review.",
                "deep_link": "https://chat.google.com/room/woolworths-fde/thread-alex-1",
            }
        ],
        "chat_space_threads": [],
        "calendar_events": [
            {
                "title": "AuNZ AI Go-To-Market Leadership Standup",
                "start_time": "09:00 AM",
                "end_time": "09:30 AM",
                "attendees": ["rsibo@google.com", "elisha@google.com"],
                "meeting_link": "https://meet.google.com/aunz-ai-standup",
            }
        ],
        "hot_list_matches": {
            "Optus VAIS & Model Armor Blocker": [
                {
                    "source": "gmail",
                    "thread_id": "thread-elisha-1",
                    "sender_name": "Simon Elisha",
                    "sender_email": "elisha@google.com",
                    "timestamp": "2026-09-04T07:15:00Z",
                    "subject": "Optus Model Armor & Architecture Escalation",
                    "snippet": "Model armor review needed",
                    "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-elisha-1",
                }
            ]
        },
    }

    mock_market_news = {
        "harvest_timestamp": "2026-09-04T08:00:00+10:00",
        "lookback_hours": 72,
        "announcements": [
            {
                "domain": "foundation_models",
                "entity": "Anthropic",
                "headline": "Claude 3.7 Sonnet Hybrid Reasoning Released",
                "summary": "Hybrid model offering instant inference alongside extended chain-of-thought.",
                "source_url": "https://anthropic.com/news/claude-3-7",
                "date": "2026-09-03",
                "verified": True,
            }
        ],
    }

    draft_payload = assemble_draft_briefing(mock_internal_comms, mock_market_news)
    compliant_html = draft_payload["raw_html"]
    print("Baseline draft assembled successfully.")

    # 2. Rejection Demonstration (Flawed Draft)
    print("\n--- [Step 2] Iteration 1: Reviewer Auditing Flawed Draft ---")
    flawed_html = compliant_html.replace(
        "<b>OVERNIGHT SUMMARY</b><br>",
        "<b>OVERNIGHT SUMMARY</b><br>Here is your executive brief on the critical emergency! 🚨<br><br>",
    )
    rejection_result = evaluate_briefing_draft(flawed_html)
    print(f"Verdict: {rejection_result['verdict'].upper()}")
    print(f"Critique: {rejection_result['critique']}")
    print("Issues Flagged:")
    for idx, issue in enumerate(rejection_result.get("issues", []), 1):
        print(f"  {idx}. {issue}")

    # 3. Approval Demonstration (Compliant Draft)
    print("\n--- [Step 3] Iteration 2: Reviewer Auditing Compliant Draft ---")
    approval_result = evaluate_briefing_draft(compliant_html)
    print(f"Verdict: {approval_result['verdict'].upper()}")
    print(f"Critique: {approval_result['critique']}")
    lint_checks = lint_vp_standards(compliant_html)["checks"]
    print("VP Standard Verification Checks:")
    for check_name, passed in lint_checks.items():
        print(f"  - {check_name}: {'PASS' if passed else 'FAIL'}")

    # 4. Finalization and Loop Escalation
    print("\n--- [Step 4] Finalization & Loop Escalation ---")
    mock_context = MagicMock()
    mock_context.state = {}
    mock_context.actions = MagicMock()

    final_payload = finalize_approved_briefing(
        draft_html=compliant_html,
        reviewer_notes="Chief of Staff editorial review approved: zero hyperbole, verified links, strict 6-sentence summary.",
        tool_context=mock_context,
    )

    print("State Key 'final_briefing' populated:")
    print(f"  - is_approved: {final_payload['is_approved']}")
    print(f"  - approved_at: {final_payload['approved_at']}")
    print(f"  - reviewer_notes: {final_payload['editor_review_notes']}")
    print(f"  - Loop Escalation Triggered: {mock_context.actions.escalate is True}")

    print("\n" + "=" * 80)
    print(" [STAGE 3 COMPLETE] BRIEFING APPROVED FOR STAGE 4 AUDIO PODCAST PIPELINE")
    print("=" * 80)


if __name__ == "__main__":
    run_editorial_simulation()
