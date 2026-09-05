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

"""Comprehensive End-to-End Integration Test for the Daily Brief Pipeline.

Validates that every single phase of the executive Daily Brief executes cleanly,
creates required structured content in session state, and progresses all the way
from initial harvesting to final delivery and lifecycle cleanup without errors.

Phases tested sequentially:
1. Phase 1 & 2: Parallel Harvesting (Internal Comms + Technical Market News)
2. Phase 3: Briefing Writer (6-sentence overnight summary, core updates, hot list)
3. Phase 4: Editorial Reviewer (Lint VP standards, approve & escalate loop exit)
4. Phase 5: Spoken Script Conversion (Phonetics, signposts, zero fluff)
5. Phase 6: Podcast Audio Synthesis & Asset Creation (Mock audio generation)
6. Phase 7: Delivery, Calendar Event Scheduling & Automated Artifact Clean-Up
"""

import os
import re
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from app.tools.delivery_tools import deliver_daily_briefing
from app.tools.editor_tools import finalize_approved_briefing, lint_vp_standards
from app.tools.internal_comms_tools import harvest_all_internal_communications
from app.tools.market_news_tools import (
    harvest_all_market_news,
    is_within_lookback_window,
)
from app.tools.podcast_tools import (
    convert_html_to_spoken_script,
    generate_podcast_pipeline,
)
from app.tools.synthesis_tools import assemble_draft_briefing

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


class MockToolContextActions:
    """Mock actions container for ADK ToolContext."""

    def __init__(self) -> None:
        self.escalate: bool = False


def create_pipeline_tool_context(
    initial_state: dict[str, Any] | None = None,
) -> ToolContext:
    """Constructs a fully functional mock ToolContext for pipeline testing."""
    context = MagicMock(spec=ToolContext)
    context.state = initial_state if initial_state is not None else {}
    context.actions = MockToolContextActions()
    return context


def test_end_to_end_pipeline_all_phases_progression() -> None:
    """Executes each pipeline phase in exact sequence and asserts end-to-end success."""
    context = create_pipeline_tool_context()

    # -------------------------------------------------------------------------
    # STAGE 1: Parallel Harvesting (Internal Comms + Market News)
    # -------------------------------------------------------------------------
    synthetic_internal_fixtures = {
        "gmail": [
            {
                "id": "thread_optus_001",
                "sender": "selisha@google.com",
                "from": "selisha@google.com",
                "timestamp": datetime.now(UTC).isoformat(),
                "subject": "[Optus] Model Armor Blocker Escalation",
                "snippet": "Need urgent confirmation on Optus Model Armor deployment approval by 2pm.",
                "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread_optus_001",
            }
        ],
        "chat": [
            {
                "id": "msg_chat_002",
                "sender": "lead-eng@google.com",
                "timestamp": datetime.now(UTC).isoformat(),
                "text": "Woolworths FDE/SWE engagement architecture review is confirmed for tomorrow.",
                "space": "spaces/eng_leads",
            }
        ],
        "calendar": [
            {
                "summary": "AI Leadership Weekly Sync",
                "start": {"dateTime": "2026-09-05T09:00:00+10:00"},
                "end": {"dateTime": "2026-09-05T09:30:00+10:00"},
                "attendees": [{"email": "leadership@google.com"}],
                "hangoutLink": "https://meet.google.com/abc-defg-hij",
            }
        ],
    }

    # Harvest Internal Comms
    internal_result = harvest_all_internal_communications(
        lookback_hours=24,
        test_fixtures=synthetic_internal_fixtures,
        tool_context=context,
    )
    assert isinstance(internal_result, dict)
    assert "internal_comms_data" in context.state, (
        "internal_comms_data missing from session state"
    )
    assert len(context.state["internal_comms_data"]["leadership_threads"]) >= 1
    assert len(context.state["internal_comms_data"]["chat_space_threads"]) >= 1

    # Harvest Market News (Technical Head of AI/ML persona)
    market_result = harvest_all_market_news(
        lookback_hours=72, tool_context=context, mock=True
    )
    assert isinstance(market_result, dict)
    assert "market_news_data" in context.state, (
        "market_news_data missing from session state"
    )
    announcements = context.state["market_news_data"]["announcements"]
    assert len(announcements) >= 3, "Expected at least 3 verified market items"

    # Verify market data freshness (strictly trailing 72 hours) and technical quality
    now = datetime.now(SYDNEY_TZ)
    domains_present = set()
    for item in announcements:
        domains_present.add(item["domain"])
        assert is_within_lookback_window(
            item["date"], lookback_hours=72, reference_time=now
        ), f"Market item {item['headline']} date {item['date']} is outside 72h window"
        # Ensure no clickbait
        assert not re.search(
            r"\b(game[- ]?changer|insane|mind[- ]?blowing)\b", item["headline"], re.I
        )
        assert item["source_url"].startswith("http")

    assert "foundation_models" in domains_present
    assert "agents_frameworks" in domains_present
    assert "cloud_ai_ml" in domains_present

    # -------------------------------------------------------------------------
    # STAGE 2: Draft Briefing Synthesis (Briefing Writer)
    # -------------------------------------------------------------------------
    # Invoke assemble_draft_briefing with zero data arguments, relying on context.state
    draft_result = assemble_draft_briefing(tool_context=context)
    assert isinstance(draft_result, dict)
    assert "draft_briefing" in context.state, (
        "draft_briefing missing from session state"
    )
    draft_payload = context.state["draft_briefing"]
    raw_html = draft_payload["raw_html"]
    assert len(raw_html) > 200, "Briefing HTML is unexpectedly sparse"

    # Verify sections in raw_html
    assert "<b>OVERNIGHT SUMMARY</b>" in raw_html
    assert "<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>" in raw_html
    assert "<b>ACTIVE HOT LIST UPDATES</b>" in raw_html
    assert "<b>AI MARKET UPDATES (TRAILING 72 HOURS)</b>" in raw_html

    # Verify calendar agenda is excluded from briefing text per user requirement
    assert "LOOKING AT YOUR DAY AHEAD" not in raw_html

    # Verify 6-sentence summary rule and no bolding inside summary
    summary_text = draft_payload.get("executive_orientation", "")
    if not summary_text:
        summary_match = re.search(
            r"<b>OVERNIGHT SUMMARY</b><br>\s*(.*?)\s*<br><br>",
            raw_html,
            re.DOTALL,
        )
        assert summary_match is not None, "Overnight summary section not found"
        summary_text = summary_match.group(1).strip()
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_text) if s.strip()
    ]
    assert len(sentences) == 6, (
        f"Expected exactly 6 sentences in summary, got {len(sentences)}: {sentences}"
    )
    assert "<b>" not in summary_text, "Overnight summary must not contain bold tags"

    # Verify no emojis anywhere in the HTML
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]",
        re.UNICODE,
    )
    assert not emoji_pattern.search(raw_html), (
        "Draft briefing contains prohibited emojis"
    )

    # -------------------------------------------------------------------------
    # STAGE 3: Editorial Review & Approval (Editor Reviewer)
    # -------------------------------------------------------------------------
    # Lint draft against VP standards
    lint_report = lint_vp_standards(html_content=raw_html)
    assert lint_report["valid"] is True, (
        f"Lint check failed: {lint_report.get('issues')}"
    )

    # Finalize approved briefing with zero data arguments, pulling from context.state
    approval_result = finalize_approved_briefing(tool_context=context)
    assert isinstance(approval_result, dict)
    assert "final_briefing" in context.state, (
        "final_briefing missing from session state"
    )
    final_payload = context.state["final_briefing"]
    assert final_payload["is_approved"] is True
    assert len(final_payload["final_html"]) > 200
    # Verify loop exit escalation flag was set
    assert context.actions.escalate is True, (
        "Editor reviewer must set escalate=True to break loop"
    )

    # -------------------------------------------------------------------------
    # STAGE 4: Spoken Script Conversion (Podcast Script Agent)
    # -------------------------------------------------------------------------
    # Invoke convert_html_to_spoken_script with zero arguments, pulling from context.state
    script_result = convert_html_to_spoken_script(tool_context=context)
    assert isinstance(script_result, dict)
    assert "podcast_script" in context.state, (
        "podcast_script missing from session state"
    )
    podcast_script_payload = context.state["podcast_script"]
    spoken_script = podcast_script_payload["spoken_script"]
    assert len(spoken_script) > 100, "Spoken script is unexpectedly empty"

    # Verify spoken script properties: no HTML tags, no URLs, no greeting fluff
    assert "<" not in spoken_script and ">" not in spoken_script, (
        "Spoken script contains raw HTML tags"
    )
    assert "http://" not in spoken_script and "https://" not in spoken_script, (
        "Spoken script contains URLs"
    )
    assert not spoken_script.lower().startswith("good morning"), (
        "Spoken script must omit greeting fluff"
    )
    assert podcast_script_payload["word_count"] > 100
    assert podcast_script_payload["estimated_duration_seconds"] > 0

    # -------------------------------------------------------------------------
    # STAGE 5: Podcast Audio Generation (Podcast Creator Agent)
    # -------------------------------------------------------------------------
    # Invoke generate_podcast_pipeline with zero data arguments, pulling from context.state
    pipeline_result = generate_podcast_pipeline(tool_context=context, mock=True)
    assert isinstance(pipeline_result, dict)
    assert "podcast_asset" in context.state, "podcast_asset missing from session state"
    podcast_asset = context.state["podcast_asset"]
    assert podcast_asset["drive_web_url"].startswith("http")
    assert os.path.exists(podcast_asset["local_file_path"]), (
        f"Audio file not found: {podcast_asset['local_file_path']}"
    )
    assert podcast_asset["duration_seconds"] > 0

    # -------------------------------------------------------------------------
    # STAGE 6: Delivery, Scheduling & Lifecycle Clean-Up (Delivery Agent)
    # -------------------------------------------------------------------------
    # Invoke deliver_daily_briefing with zero data arguments, pulling from context.state
    delivery_result = deliver_daily_briefing(tool_context=context, mock=True)
    assert isinstance(delivery_result, dict)
    assert "delivery_result" in context.state, (
        "delivery_result missing from session state"
    )
    delivery_payload = context.state["delivery_result"]
    assert delivery_payload["status"] == "delivered"
    assert delivery_payload["calendar_event_id"].startswith("cal-brief-")

    chat_response = delivery_payload["chat_response"]
    assert "Listen to Brief" in chat_response
    assert podcast_asset["drive_web_url"] in chat_response
    assert "CORE UPDATES & LEADERSHIP DIRECTIVES" in chat_response
    assert "ACTIVE HOT LIST UPDATES" in chat_response
    assert "AI MARKET UPDATES" in chat_response
    assert not emoji_pattern.search(chat_response), (
        "Chat response contains prohibited emojis"
    )

    # Verify lifecycle clean-up completed
    assert delivery_payload["cleanup_status"]["status"] == "success"

    # -------------------------------------------------------------------------
    # FINAL STATE INTEGRITY ASSERTION
    # -------------------------------------------------------------------------
    required_state_keys = [
        "internal_comms_data",
        "market_news_data",
        "draft_briefing",
        "final_briefing",
        "podcast_script",
        "podcast_asset",
        "delivery_result",
    ]
    for key in required_state_keys:
        assert key in context.state, (
            f"Required pipeline state key '{key}' missing at completion"
        )
        assert context.state[key] is not None, f"Pipeline state key '{key}' is None"
