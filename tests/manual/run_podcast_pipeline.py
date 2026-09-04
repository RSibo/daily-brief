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

"""Standalone Manual Runner for Phase 5: Audio Podcast Pipeline.

Executes the acoustic script adaptation, speech synthesis, and Drive publishing pipeline:
1. Feeds an approved executive HTML briefing into convert_html_to_spoken_script.
2. Displays the acoustic spoken transcript with phonetic acronym expansions.
3. Synthesizes an MP3 audio file with ID3 metadata.
4. Uploads to Google Drive (/agents/daily-briefing) and outputs permanent link.

Usage:
    uv run python -m tests.manual.run_podcast_pipeline
"""

import os
from unittest.mock import MagicMock

from app.tools.podcast_tools import (
    convert_html_to_spoken_script,
    generate_podcast_pipeline,
)

SAMPLE_APPROVED_BRIEFING = """
<b>OVERNIGHT SUMMARY</b><br>
Overnight communications remained focused on partner escalations, product roadmap confirmations, and regional go-to-market priorities. From senior leadership, Simon Elisha followed up regarding Optus Model Armor & Architecture Escalation with a specific request for technical validation. Regional engineering and go-to-market spaces logged regular progress without blocking dependencies. Commercial deal motions across enterprise accounts are progressing with critical review gates scheduled for this week. Your calendar today features 1 scheduled commitments, opening with AuNZ AI Go-To-Market Leadership Standup at 09:00 AM. All required briefing dossiers, background contexts, and decision options are organized below for your review.<br><br>
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


def run_podcast_simulation() -> None:
    """Runs a manual interactive simulation of the audio podcast pipeline."""
    print("=" * 80)
    print(" [STAGE 4] AUDIO PODCAST PIPELINE SIMULATION")
    print("=" * 80)

    # 1. Acoustic Script Adaptation
    print("\n--- [Step 1] Converting Approved Briefing to Acoustic Spoken Script ---")
    script_result = convert_html_to_spoken_script(SAMPLE_APPROVED_BRIEFING)
    spoken_text = script_result["spoken_script"]
    word_count = script_result["word_count"]
    est_duration = script_result["estimated_duration_seconds"]

    print(f"Word Count: {word_count} words")
    print(
        f"Estimated Duration (@1.05x speed): {est_duration} seconds (~{est_duration // 60}m {est_duration % 60}s)"
    )
    print("\n--- Generated Spoken Transcript ('Written for the Ear') ---")
    print(spoken_text)

    # 2. Audio Synthesis & Drive Publishing
    print("\n--- [Step 2] Synthesizing MP3 Audio & Google Drive Publishing ---")
    mock_context = MagicMock()
    mock_context.state = {}

    pipeline_result = generate_podcast_pipeline(
        spoken_script=spoken_text,
        tool_context=mock_context,
        mock=True,
    )

    local_path = pipeline_result["local_file_path"]
    drive_id = pipeline_result["drive_file_id"]
    drive_url = pipeline_result["drive_web_url"]
    duration = pipeline_result["duration_seconds"]

    print("Audio Asset Summary:")
    print(f"  - Local MP3 Path: {local_path}")
    print(
        f"  - File Size: {os.path.getsize(local_path) if os.path.exists(local_path) else 0} bytes"
    )
    print(f"  - Duration: {duration} seconds")
    print(f"  - Google Drive File ID: {drive_id}")
    print(f"  - Permanent Web URL: {drive_url}")
    print(
        "  - Target Folder ID: 1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV (/agents/daily-briefing)"
    )
    print(
        f"  - Session State 'podcast_asset' Populated: {'podcast_asset' in mock_context.state}"
    )

    print("\n" + "=" * 80)
    print(" [STAGE 4 COMPLETE] AUDIO PODCAST READY FOR CALENDAR & CHAT DELIVERY")
    print("=" * 80)


if __name__ == "__main__":
    run_podcast_simulation()
