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

"""Unit tests for Phase 5: Audio Podcast Pipeline.

Validates:
- Conversion of email-formatted HTML into acoustic spoken scripts ("written for the ear").
- Removal of raw URLs, markdown syntax, and parenthetical links.
- Phonetic acronym expansions (VAIS -> V-A-I-S, DRZ -> D-R-Z, FLW -> F-L-W,
  FDE -> F-D-E, SWE -> S-W-E, CE -> C-E, AuNZ -> Australia and New Zealand).
- Spoken signpost insertion and zero-greeting fluff opening.
- MP3 synthesis, frame encoding, and Google Drive upload payload generation.
- ADK sub-agent definitions: podcast_script_agent and podcast_creator_agent.
"""

import os
from unittest.mock import MagicMock

from app.app_utils.typing import PodcastAssetPayload, PodcastScriptPayload
from app.sub_agents.podcast_creator_agent import podcast_creator_agent
from app.sub_agents.podcast_script_agent import podcast_script_agent
from app.tools.podcast_tools import (
    convert_html_to_spoken_script,
    generate_podcast_pipeline,
    synthesize_podcast_audio,
    upload_podcast_to_drive,
)

SAMPLE_APPROVED_BRIEFING = """
<b><a href="https://drive.google.com/file/d/old-asset/view"><u>Listen to Brief</u></a></b><br><br>
<b>OVERNIGHT SUMMARY</b><br>
Overnight communications remained focused on partner escalations, product roadmap confirmations, and regional go-to-market priorities. Senior leadership channels were stable overnight with no emergency directives or unscheduled escalations received. Regional engineering and go-to-market spaces logged regular progress without blocking dependencies. Commercial deal motions across enterprise accounts are progressing with critical review gates scheduled for this week. Your schedule today provides substantial focus time with no immediate meeting conflicts on the morning calendar. All required briefing dossiers, background contexts, and decision options are organized below for your review.<br><br>
<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>
<ul>
  <li><b>[<b>Optus</b>] <a href="https://mail.google.com/mail/u/0/#inbox/optus-1"><u>Optus VAIS Model Armor Blocker</u></a>:</b> Friday Simon Elisha noted: "Need confirmation on model armor deployment in AuNZ." <b>Action Needed:</b> Review with Alex Chi.</li>
  <li><b>[<b>Woolworths</b>] <a href="https://chat.google.com/room/woolworths-fde"><u>Woolworths FDE and SWE Workshop</u></a>:</b> Pedro Correia confirmed FDE readiness for FLW rollout.</li>
</ul>
<br><b>ACTIVE HOT LIST UPDATES</b>
<ul>
  <li><b><a href="https://mail.google.com/mail/u/0/#inbox/optus-1"><u>Optus VAIS & Model Armor Blocker</u></a>:</b> Optus VAIS review ongoing.</li>
  <li><b>Woolworths (GE, FDE/SWE Initiative, FLW):</b> <i>On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet.</i></li>
  <li><b>Google AI DRZ / AU ML Processing:</b> <i>On topic Google AI DRZ / AU ML Processing no updates yet.</i></li>
</ul>
<br><b>AI MARKET UPDATES (TRAILING 72 HOURS)</b>
<ul>
  <li><b>[Anthropic - 2026-09-03] <a href="https://anthropic.com/news/claude-3-7"><u>Claude 3.7 Sonnet Hybrid Reasoning Released</u></a>:</b> Hybrid model offering instant inference alongside extended chain-of-thought.</li>
</ul>
<br><b>LOOKING AT YOUR DAY AHEAD</b>
<p>Looking at your day ahead, here are your scheduled commitments and meeting dossiers:</p>
<ul>
  <li><b>[09:00 AM - AuNZ AI Go-To-Market Leadership Standup] (<a href="https://calendar.google.com"><u>Prep Doc</u></a>):</b> Attendees: rsibo@google.com, elisha@google.com. <b>Focus:</b> Strategic alignment.</li>
</ul>
"""


def test_convert_html_to_spoken_script_removes_tags_and_urls() -> None:
    """Verifies that HTML tags, href URLs, and listen banners are completely removed."""
    result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    script_payload = PodcastScriptPayload(**result)
    script = script_payload.spoken_script

    assert "<a" not in script
    assert "href=" not in script
    assert "<b>" not in script
    assert "<ul>" not in script
    assert "<li>" not in script
    assert "Listen to Brief" not in script


def test_convert_html_to_spoken_script_applies_phonetics() -> None:
    """Verifies phonetic expansions of acronyms like VAIS, DRZ, FLW, FDE, SWE, AuNZ."""
    result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    script = result["spoken_script"]

    assert "V-A-I-S" in script
    assert "D-R-Z" in script
    assert "F-L-W" in script
    assert "F-D-E" in script
    assert "S-W-E" in script
    assert "Australia and New Zealand" in script
    assert "Gemini Enterprise" in script


def test_convert_html_to_spoken_script_adds_spoken_signposts() -> None:
    """Verifies natural conversational transitions between briefing sections."""
    result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    script = result["spoken_script"]

    assert "In leadership communications and core team updates:" in script
    assert "Turning to our hot list priorities:" in script
    assert (
        "Looking outward at AI market updates over the trailing seventy-two hours:"
        in script
    )
    assert "And looking at your day ahead" in script


def test_convert_html_to_spoken_script_zero_greeting_fluff() -> None:
    """Verifies that the script drops artificial intros and opens directly with overnight comms."""
    result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    script = result["spoken_script"]

    assert not script.startswith("Good morning")
    assert not script.startswith("Welcome to your")
    assert not script.startswith("Here is your")
    assert script.startswith(
        "Overnight communications remained focused on partner escalations"
    )


def test_convert_html_to_spoken_script_duration_and_word_count() -> None:
    """Verifies that word count and duration calculations are computed."""
    result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    assert result["word_count"] > 100
    assert result["estimated_duration_seconds"] > 30
    assert "generated_at" in result


def test_convert_html_to_spoken_script_empty_input() -> None:
    """Verifies that empty HTML returns a StructuredToolError."""
    result = convert_html_to_spoken_script("")
    assert result["status"] == "error"
    assert result["error_code"] == "EMPTY_CONTENT"
    assert "recovery_instruction" in result


def test_synthesize_podcast_audio_generates_valid_mp3() -> None:
    """Verifies MP3 synthesis produces a valid audio file on disk with ID3 tag."""
    result = synthesize_podcast_audio("Short test spoken script.", mock=True)
    assert "local_file_path" in result
    file_path = result["local_file_path"]
    assert os.path.exists(file_path)
    assert result["file_size_bytes"] > 0
    assert result["duration_seconds"] >= 1

    # Verify ID3 header
    with open(file_path, "rb") as f:
        header = f.read(3)
        assert header == b"ID3"

    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)


def test_upload_podcast_to_drive_mock() -> None:
    """Verifies Drive upload tool produces a valid Drive file ID and web URL."""
    result = upload_podcast_to_drive("/tmp/dummy.mp3", mock=True)
    assert result["drive_file_id"].startswith("1")
    assert "https://drive.google.com/file/d/" in result["drive_web_url"]
    assert "/view" in result["drive_web_url"]


def test_generate_podcast_pipeline_full_payload() -> None:
    """Verifies end-to-end execution of synthesis and upload returning PodcastAssetPayload."""
    result = generate_podcast_pipeline("Acoustic script for test pipeline.", mock=True)
    payload = PodcastAssetPayload(**result)
    assert payload.drive_file_id is not None
    assert payload.drive_web_url.startswith("https://drive.google.com/file/d/")
    assert payload.duration_seconds >= 1
    assert payload.local_file_path.endswith(".mp3")
    assert payload.created_at is not None

    # Cleanup
    if os.path.exists(payload.local_file_path):
        os.remove(payload.local_file_path)


def test_generate_podcast_pipeline_with_tool_context() -> None:
    """Verifies that passing ToolContext updates session state key 'podcast_asset'."""
    mock_context = MagicMock()
    mock_context.state = {}

    result = generate_podcast_pipeline(
        "Script for context test.", tool_context=mock_context, mock=True
    )
    assert "podcast_asset" in mock_context.state
    assert (
        mock_context.state["podcast_asset"]["drive_file_id"] == result["drive_file_id"]
    )

    # Cleanup
    local_path = result["local_file_path"]
    if os.path.exists(local_path):
        os.remove(local_path)


def test_podcast_script_agent_properties() -> None:
    """Verifies podcast_script_agent structure and configuration."""
    assert podcast_script_agent.name == "podcast_script_agent"
    assert podcast_script_agent.output_key == "podcast_script"
    assert len(podcast_script_agent.tools) == 1
    tool_name = (
        podcast_script_agent.tools[0].__name__
        if hasattr(podcast_script_agent.tools[0], "__name__")
        else podcast_script_agent.tools[0].name
    )
    assert tool_name == "convert_html_to_spoken_script"


def test_podcast_creator_agent_properties() -> None:
    """Verifies podcast_creator_agent structure and configuration."""
    assert podcast_creator_agent.name == "podcast_creator_agent"
    assert podcast_creator_agent.output_key == "podcast_asset"
    tool_names = [
        t.__name__ if hasattr(t, "__name__") else t.name
        for t in podcast_creator_agent.tools
    ]
    assert "synthesize_podcast_audio" in tool_names
    assert "upload_podcast_to_drive" in tool_names
    assert "generate_podcast_pipeline" in tool_names
