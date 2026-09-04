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

"""Integration tests for Phase 6: Master Orchestrator, Delivery & Clean-Up Pipeline.

Validates:
- Complete multi-agent architecture composition:
    1. Stage 1: ParallelAgent (harvesters: internal_comms_agent + market_news_agent)
    2. Stage 2 & 3: LoopAgent (editorial_loop: writer + reviewer, max_iterations=4)
    3. Stage 4: SequentialAgent (podcast_pipeline: script + creator)
    4. Stage 5: Agent (delivery_agent: calendar, chat, and automated cleanup)
- Audio badge injection ('Listen to Brief').
- Google Calendar event scheduling (30-min private, transparent 'Your Morning Brief' at 06:00 AM Sydney time).
- Interactive chat response delivery.
- Automated lifecycle clean-up (cleanup_pipeline_artifacts):
    - Purges ephemeral harvest cache dumps.
    - Purges local MP3 files older than 7 days while preserving recent audio.
"""

import os
import tempfile
import time
from unittest.mock import MagicMock

from google.adk.agents import LoopAgent, ParallelAgent, SequentialAgent

from app.agent import app, root_agent
from app.sub_agents.delivery_agent import delivery_agent
from app.sub_agents.editorial_loop import editorial_loop
from app.sub_agents.internal_comms_agent import internal_comms_agent
from app.sub_agents.market_news_agent import market_news_agent
from app.sub_agents.podcast_creator_agent import podcast_creator_agent
from app.sub_agents.podcast_script_agent import podcast_script_agent
from app.tools.delivery_tools import (
    cleanup_pipeline_artifacts,
    deliver_daily_briefing,
    format_chat_delivery_response,
    inject_audio_header_into_briefing,
    schedule_briefing_calendar_event,
)

SAMPLE_BRIEFING_HTML = """
<b>OVERNIGHT SUMMARY</b><br>
Overnight communications remained focused on partner escalations, product roadmap confirmations, and regional go-to-market priorities. Senior leadership channels were stable overnight with no emergency directives or unscheduled escalations received. Regional engineering and go-to-market spaces logged regular progress without blocking dependencies. Commercial deal motions across enterprise accounts are progressing with critical review gates scheduled for this week. Your schedule today provides substantial focus time with no immediate meeting conflicts on the morning calendar. All required briefing dossiers, background contexts, and decision options are organized below for your review.<br><br>
<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>
<ul>
  <li><b>[<b>Optus</b>] <a href="https://mail.google.com"><u>Model Armor Blocker</u></a>:</b> Confirmation pending.</li>
</ul>
<br><b>ACTIVE HOT LIST UPDATES</b>
<ul>
  <li><b>Woolworths (GE, FDE/SWE Initiative, FLW):</b> <i>On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet.</i></li>
</ul>
<br><b>AI MARKET UPDATES (TRAILING 72 HOURS)</b>
<ul>
  <li><b>Anthropic:</b> <a href="https://anthropic.com"><u>Claude 3.7 Sonnet Released</u></a></li>
</ul>
<br><b>LOOKING AT YOUR DAY AHEAD</b>
<p>Looking at your day ahead, here are your scheduled commitments and meeting dossiers:</p>
<ul>
  <li>09:00 AM - AI Leadership Standup.</li>
</ul>
"""


def test_orchestrator_structure_and_hierarchy() -> None:
    """Verifies the complete multi-agent orchestrator hierarchy."""
    assert root_agent.name == "daily_brief_orchestrator"
    assert app.root_agent == root_agent
    assert isinstance(root_agent, SequentialAgent)

    sub_agents = root_agent.sub_agents
    assert len(sub_agents) == 4

    # Stage 1: Parallel Harvesters
    stage1 = sub_agents[0]
    assert isinstance(stage1, ParallelAgent)
    assert stage1.name == "harvesters"
    assert len(stage1.sub_agents) == 2
    assert stage1.sub_agents[0].name == internal_comms_agent.name
    assert stage1.sub_agents[1].name == market_news_agent.name

    # Stage 2 & 3: Editorial Loop (with max_iterations=4)
    stage2 = sub_agents[1]
    assert isinstance(stage2, LoopAgent)
    assert stage2.name == editorial_loop.name
    assert stage2.max_iterations == 4
    assert len(stage2.sub_agents) == 2

    # Stage 4: Sequential Podcast Pipeline
    stage4 = sub_agents[2]
    assert isinstance(stage4, SequentialAgent)
    assert stage4.name == "podcast_pipeline"
    assert len(stage4.sub_agents) == 2
    assert stage4.sub_agents[0].name == podcast_script_agent.name
    assert stage4.sub_agents[1].name == podcast_creator_agent.name

    # Stage 5: Delivery and Cleanup
    stage5 = sub_agents[3]
    assert stage5.name == delivery_agent.name
    assert stage5.output_key == "delivery_result"


def test_inject_audio_header_into_briefing() -> None:
    """Verifies that the Listen to Brief banner is inserted cleanly."""
    drive_url = "https://drive.google.com/file/d/test-mp3-id/view"
    result = inject_audio_header_into_briefing(SAMPLE_BRIEFING_HTML, drive_url)

    assert result.startswith(
        f'<b><a href="{drive_url}"><u>Listen to Brief</u></a></b><br><br>'
    )
    # Test idempotence (no double header)
    second_injection = inject_audio_header_into_briefing(result, drive_url)
    assert second_injection.count("Listen to Brief") == 1


def test_schedule_briefing_calendar_event_mock() -> None:
    """Verifies Google Calendar 30-minute private, transparent morning briefing creation."""
    podcast_asset = {"drive_web_url": "https://drive.google.com/file/d/sample/view"}
    event = schedule_briefing_calendar_event(
        briefing_html=SAMPLE_BRIEFING_HTML,
        podcast_asset=podcast_asset,
        event_date_str="2026-09-04",
        mock=True,
    )

    assert event["summary"] == "Your Morning Brief"
    assert event["start_time"] == "2026-09-04T06:00:00+10:00"
    assert event["end_time"] == "2026-09-04T06:30:00+10:00"
    assert event["visibility"] == "private"
    assert event["transparency"] == "transparent"
    assert event["attachment_url"] == podcast_asset["drive_web_url"]
    assert event["status"] == "confirmed"


def test_format_chat_delivery_response() -> None:
    """Verifies rendering of the interactive chat briefing response."""
    podcast_asset = {"drive_web_url": "https://drive.google.com/file/d/chat-audio/view"}
    rendered = format_chat_delivery_response(
        final_briefing={"final_html": SAMPLE_BRIEFING_HTML},
        podcast_asset=podcast_asset,
    )
    assert "Listen to Brief" in rendered
    assert "chat-audio" in rendered
    assert "OVERNIGHT SUMMARY" in rendered


def test_cleanup_pipeline_artifacts_retention_and_purge() -> None:
    """Verifies cleanup purges harvest caches and MP3 files older than 7 days, retaining newer ones."""
    temp_dir = tempfile.mkdtemp()
    cache_dir = os.path.join(temp_dir, "harvest_cache")
    os.makedirs(cache_dir, exist_ok=True)

    # 1. Create dummy harvest cache file
    cache_file = os.path.join(cache_dir, "test_harvest.json")
    with open(cache_file, "w") as f:
        f.write('{"cached": true}')

    # 2. Create an old MP3 file (10 days old)
    old_mp3 = os.path.join(temp_dir, "[260820]-Daily-Brief.mp3")
    with open(old_mp3, "wb") as f:
        f.write(b"old-audio-data")
    ten_days_ago = time.time() - (10 * 86400)
    os.utime(old_mp3, (ten_days_ago, ten_days_ago))

    # 3. Create a fresh MP3 file (today)
    new_mp3 = os.path.join(temp_dir, "[260904]-Daily-Brief.mp3")
    with open(new_mp3, "wb") as f:
        f.write(b"new-audio-data")

    # Run cleanup with 7-day retention
    cleanup_result = cleanup_pipeline_artifacts(
        retention_days=7,
        harvest_cache_dir=cache_dir,
        audio_dir=temp_dir,
    )

    assert cleanup_result["status"] == "success"
    assert cleanup_result["purged_harvest_caches"] >= 1
    assert not os.path.exists(cache_file)
    assert not os.path.exists(old_mp3)
    assert os.path.exists(new_mp3)
    assert cleanup_result["retained_audio_files"] >= 1

    # Clean up test directory
    if os.path.exists(new_mp3):
        os.remove(new_mp3)
    if os.path.exists(cache_dir):
        os.rmdir(cache_dir)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)


def test_deliver_daily_briefing_full_sequence() -> None:
    """Verifies end-to-end deliver_daily_briefing with calendar, chat, and post-cleanup."""
    mock_context = MagicMock()
    mock_context.state = {}

    outcome = deliver_daily_briefing(
        final_briefing={"final_html": SAMPLE_BRIEFING_HTML},
        podcast_asset={
            "drive_web_url": "https://drive.google.com/file/d/full-test/view"
        },
        delivery_mode="all",
        mock=True,
        tool_context=mock_context,
    )

    assert outcome["status"] == "delivered"
    assert outcome["calendar_event"] is not None
    assert outcome["calendar_event"]["summary"] == "Your Morning Brief"
    assert outcome["has_audio_link"] is True
    assert outcome["cleanup"]["status"] == "success"
    assert "delivery_result" in mock_context.state


def test_delivery_agent_properties() -> None:
    """Verifies delivery_agent configuration and tool declarations."""
    assert delivery_agent.name == "delivery_agent"
    assert delivery_agent.output_key == "delivery_result"
    tool_names = [
        t.__name__ if hasattr(t, "__name__") else t.name for t in delivery_agent.tools
    ]
    assert "inject_audio_header_into_briefing" in tool_names
    assert "schedule_briefing_calendar_event" in tool_names
    assert "format_chat_delivery_response" in tool_names
    assert "cleanup_pipeline_artifacts" in tool_names
    assert "deliver_daily_briefing" in tool_names
