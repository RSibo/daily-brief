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

"""Unit tests for Phase 3: Aggregator & Briefing Writer Agent and Synthesis Tools."""

import re

from app.app_utils.typing import DraftBriefingPayload
from app.sub_agents.briefing_writer_agent import briefing_writer_agent
from app.tools.synthesis_tools import (
    assemble_draft_briefing,
    format_calendar_agenda,
    format_core_updates,
    format_hot_list_updates,
    parse_hot_list_themes,
    synthesize_overnight_summary,
)


def test_parse_hot_list_themes():
    """Verifies dynamic parsing of active themes from config/hot_list.md."""
    themes = parse_hot_list_themes("config/hot_list.md")
    assert len(themes) >= 3
    assert "Optus VAIS & Model Armor Blocker" in themes
    assert "Woolworths (GE, FDE/SWE Initiative, FLW)" in themes
    assert "Google AI DRZ / AU ML Processing" in themes


def test_synthesize_overnight_summary_six_sentences():
    """Verifies that the overnight executive summary produces exactly 6 unbolded sentences."""
    summary = synthesize_overnight_summary(
        leadership_threads=[
            {
                "sender_name": "Simon Elisha",
                "subject": "Q3 GTM Strategy",
                "snippet": "Need review on architecture blockers.",
            }
        ],
        chat_threads=[
            {
                "sender_name": "FDE Space",
                "subject": "Woolies deployment",
                "snippet": "Cluster setup verified.",
            }
        ],
        calendar_events=[
            {
                "title": "AuNZ AI Leadership Sync",
                "start_time": "09:30 AM",
            }
        ],
    )

    # Clean punctuation split
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", summary) if s.strip()]
    assert len(sentences) == 6, (
        f"Expected exactly 6 sentences, found {len(sentences)}: {sentences}"
    )

    # Verify no markdown bolding in executive orientation
    assert "**" not in summary
    assert "<b>" not in summary


def test_format_core_updates_constraints():
    """Verifies Core Updates formatting: hyperlinked titles, max 2 bullets, bolded accounts."""
    leadership_threads = [
        {
            "thread_id": "thread-1",
            "sender_name": "Simon Elisha",
            "subject": "Optus VAIS Escalation",
            "snippet": "Customer needs confirmation on Model Armor deployment.",
            "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-1",
            "timestamp": "2026-09-03T18:00:00Z",
            "action_summary": "Confirm Model Armor GA schedule.",
        },
        {
            "thread_id": "thread-2",
            "sender_name": "Vamsi Ramakrishnan",
            "subject": "Woolworths GE Architecture Review",
            "snippet": "Team scoping the Shopping Agent integration.",
            "deep_link": "https://mail.google.com/mail/u/0/#inbox/thread-2",
            "timestamp": "2026-09-03T20:00:00Z",
            "action_summary": "Review FDE scoping document.",
        },
    ]

    html = format_core_updates(leadership_threads=leadership_threads)
    assert "<ul>" in html
    assert "</ul>" in html
    assert "https://mail.google.com/mail/u/0/#inbox/thread-1" in html
    assert "<b>Optus</b>" in html or "Optus" in html
    assert "Action Needed:" in html


def test_format_hot_list_fallback_string():
    """Verifies that inactive themes output the exact mandatory fallback string."""
    # Test with 0 matches -> all 3 themes must emit fallback
    html = format_hot_list_updates(
        hot_list_matches={}, config_path="config/hot_list.md"
    )

    assert "On topic Optus VAIS & Model Armor Blocker no updates yet." in html
    assert "On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet." in html
    assert "On topic Google AI DRZ / AU ML Processing no updates yet." in html

    # Test with 1 matching theme
    matches = {
        "Optus VAIS & Model Armor Blocker": [
            {
                "subject": "Optus Security Signoff",
                "snippet": "Model Armor evaluation approved.",
                "deep_link": "https://mail.google.com/mail/u/0/#inbox/optus-1",
            }
        ]
    }
    partial_html = format_hot_list_updates(
        hot_list_matches=matches, config_path="config/hot_list.md"
    )

    assert "Optus Security Signoff" in partial_html
    assert "https://mail.google.com/mail/u/0/#inbox/optus-1" in partial_html
    assert (
        "On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet."
        in partial_html
    )


def test_format_calendar_agenda_starts_with_required_phrase():
    """Verifies agenda dossier starts with 'Looking at your day ahead...'."""
    events = [
        {
            "title": "AuNZ AI Specialist Sync",
            "start_time": "10:00 AM",
            "prep_link": "https://docs.google.com/document/d/example1",
            "attendees": ["vamsi@google.com", "selisha@google.com"],
            "objective": "Q3 Target Review",
        }
    ]

    html = format_calendar_agenda(calendar_events=events)
    assert "Looking at your day ahead" in html
    assert "AuNZ AI Specialist Sync" in html
    assert "https://docs.google.com/document/d/example1" in html


def test_assemble_draft_briefing_full_payload():
    """Verifies complete assembly into DraftBriefingPayload conforming to PRD structure."""
    internal_data = {
        "leadership_threads": [
            {
                "thread_id": "thread-101",
                "sender_name": "Simon Elisha",
                "subject": "FY27 Tech GTM Strategy",
                "snippet": "Planning targets for generative AI specialist teams.",
                "deep_link": "https://mail.google.com/mail/u/0/#inbox/101",
                "timestamp": "2026-09-04T08:00:00Z",
                "action_summary": "Prepare headcount allocation proposal.",
            }
        ],
        "direct_report_threads": [],
        "chat_space_threads": [],
        "calendar_events": [
            {
                "title": "Customer Executive Interlock",
                "start_time": "02:00 PM",
                "prep_link": "https://docs.google.com/document/d/example2",
                "attendees": ["customer@example.com"],
                "objective": "Architecture signoff.",
            }
        ],
        "hot_list_matches": {},
    }

    market_data = {
        "announcements": [
            {
                "domain": "foundation_models",
                "entity": "Google DeepMind",
                "headline": "Gemini 2.5 Flash updates deployed",
                "summary": "Enhanced tool calling and sub-second reasoning latency.",
                "source_url": "https://blog.google/technology/ai/gemini-2-5-updates/",
                "date": "2026-09-04",
                "verified": True,
            }
        ]
    }

    raw_payload = assemble_draft_briefing(
        internal_data, market_data, "config/hot_list.md"
    )
    assert "error" not in raw_payload

    payload = DraftBriefingPayload(**raw_payload)

    # 1. Verify executive orientation
    assert (
        len(
            [
                s
                for s in re.split(r"[.!?]\s+", payload.executive_orientation)
                if s.strip()
            ]
        )
        == 6
    )

    # 2. Verify all sections appear in raw_html in the exact sequential order
    pos_summary = payload.raw_html.find("OVERNIGHT SUMMARY")
    pos_core = payload.raw_html.find("CORE UPDATES & LEADERSHIP DIRECTIVES")
    pos_hot = payload.raw_html.find("ACTIVE HOT LIST UPDATES")
    pos_market = payload.raw_html.find("AI MARKET UPDATES (TRAILING 72 HOURS)")
    pos_calendar = payload.raw_html.find("LOOKING AT YOUR DAY AHEAD")

    assert pos_summary != -1
    assert pos_core != -1
    assert pos_hot != -1
    assert pos_market != -1
    assert pos_calendar != -1

    assert pos_summary < pos_core < pos_hot < pos_market < pos_calendar, (
        f"Section order violation in raw_html! Positions: summary={pos_summary}, core={pos_core}, "
        f"hot={pos_hot}, market={pos_market}, calendar={pos_calendar}"
    )


def test_briefing_writer_agent_definition():
    """Verifies ADK agent configuration for briefing_writer_agent."""
    assert briefing_writer_agent.name == "briefing_writer_agent"
    assert briefing_writer_agent.output_key == "draft_briefing"
    assert len(briefing_writer_agent.tools) == 6
    tool_names = [getattr(t, "__name__", str(t)) for t in briefing_writer_agent.tools]
    assert "assemble_draft_briefing" in tool_names
    assert "synthesize_overnight_summary" in tool_names
    assert "format_core_updates" in tool_names
    assert "format_hot_list_updates" in tool_names
    assert "format_market_updates" in tool_names
    assert "format_calendar_agenda" in tool_names


def test_assemble_draft_briefing_with_string_inputs():
    """Verifies that assemble_draft_briefing handles raw string inputs defensively."""
    # 1. Test with JSON strings
    internal_json = (
        '{"leadership_threads": [], "chat_space_threads": [], "calendar_events": []}'
    )
    market_json = '{"announcements": [{"entity": "Anthropic", "headline": "Claude 3.7 Sonnet released", "date": "2026-09-04", "source_url": "https://anthropic.com", "summary": "Hybrid reasoning model."}]}'

    res_json = assemble_draft_briefing(internal_json, market_json)
    assert "error" not in res_json
    assert "Claude 3.7 Sonnet released" in res_json["raw_html"]

    # 2. Test with raw markdown strings
    internal_md = "**Internal Comms Summary**\n- No urgent directives."
    market_md = "### Market Movements\n- **[Google]** Gemini 2.5 updates deployed.\n- **[AWS]** Bedrock multi-model routing."

    res_md = assemble_draft_briefing(internal_md, market_md)
    assert "error" not in res_md
    assert "Gemini 2.5 updates deployed." in res_md["raw_html"]
    assert "Bedrock multi-model routing." in res_md["raw_html"]
