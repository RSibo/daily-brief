#!/usr/bin/env python3
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

"""Unified Autonomous Daily Brief Runner for Cloudtop.

Supports both scheduled operational modes:
1. Morning Mode (--mode morning):
   - Triggered at 6:00 AM Sydney (Mon-Sat).
   - Scans 24h internal comms & 72h frontier AI announcements via Google Search.
   - Synthesizes 4-section executive brief ('OVERNIGHT SUMMARY').
   - Adapts to spoken script, renders [YYMMDD]-Daily Brief.mp3 via edge-tts.
   - Uploads to Google Drive (/agents/daily-briefing).
   - Schedules 06:00 AM - 06:30 AM Sydney calendar event titled 'Your Morning Brief'
     with native MP3 attachment.

2. Afternoon Mode (--mode afternoon):
   - Triggered at 4:00 PM Sydney (Mon-Fri).
   - Scans 12h internal comms (5:00 AM to 5:00 PM Sydney workday).
   - Synthesizes end-of-day triage ('EXECUTIVE WRAP-UP (DECISION & TRIAGE ORIENTATION)').
   - Adapts to spoken script, renders [YYMMDD]-Day In Review.mp3 via edge-tts.
   - Uploads to Google Drive (/agents/daily-briefing).
   - Schedules 07:00 PM - 07:30 PM Sydney calendar event titled 'Day In Review'
     with native MP3 attachment.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from app.sub_agents.market_news_agent import run_market_news_agent
from app.tools.delivery_tools import (
    cleanup_pipeline_artifacts,
    inject_audio_header_into_briefing,
    schedule_briefing_calendar_event,
)
from app.tools.editor_tools import evaluate_briefing_draft, lint_vp_standards
from app.tools.internal_comms_tools import harvest_all_internal_communications
from app.tools.podcast_tools import (
    convert_html_to_spoken_script,
    synthesize_podcast_audio,
    upload_podcast_to_drive,
)
from app.tools.synthesis_tools import assemble_draft_briefing

SYDNEY_TZ = ZoneInfo("Australia/Sydney")
DRIVE_FOLDER_ID = "1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV"


def main():
    sydney_now = datetime.now(SYDNEY_TZ)
    default_mode = "afternoon" if 12 <= sydney_now.hour < 20 else "morning"

    parser = argparse.ArgumentParser(description="Autonomous Daily Brief Runner")
    parser.add_argument(
        "--mode",
        choices=["morning", "afternoon"],
        default=default_mode,
        help="Briefing mode: 'morning' (06:00 slot) or 'afternoon' (19:00 slot)",
    )
    parser.add_argument(
        "--date",
        default=sydney_now.strftime("%Y-%m-%d"),
        help="Target date YYYY-MM-DD (defaults to current Sydney date)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in offline mock mode without calling live APIs",
    )
    args = parser.parse_args()

    mode = args.mode
    target_date = args.date
    is_mock = args.mock

    print("=" * 80)
    print(f"STARTING AUTONOMOUS DAILY BRIEF RUN [{mode.upper()} MODE]")
    print(f"Current Sydney Time: {sydney_now.isoformat()}")
    print(f"Target Event Date:   {target_date}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Stage 1: Harvesting Communications & Market Intelligence
    # --------------------------------------------------------------------------
    if mode == "morning":
        lookback_hours = 24
        print(
            f"\n[Stage 1/6] Harvesting internal comms (lookback: {lookback_hours}h)..."
        )
        internal_data = harvest_all_internal_communications(
            lookback_hours=lookback_hours
        )

        print(
            "  Harvesting live frontier AI market news via market_news_agent & google_search..."
        )
        market_data = run_market_news_agent(
            lookback_hours=72, allow_mock_fallback=is_mock
        )
    else:
        # Afternoon mode: 12-hour workday window
        lookback_hours = 12
        print(
            f"\n[Stage 1/6] Harvesting daytime internal comms (lookback: {lookback_hours}h)..."
        )
        internal_data = harvest_all_internal_communications(
            lookback_hours=lookback_hours
        )
        market_data = {"announcements": []}

    print(
        f"  Internal Comms: {len(internal_data.get('leadership_threads', []))} leadership, "
        f"{len(internal_data.get('chat_space_threads', []))} chat, "
        f"{len(internal_data.get('calendar_events', []))} calendar"
    )
    if mode == "morning":
        print(
            f"  Market Announcements: {len(market_data.get('announcements', []))} frontier AI developments"
        )

    # --------------------------------------------------------------------------
    # Stage 2: Synthesis & Assembly of Executive Briefing
    # --------------------------------------------------------------------------
    print(f"\n[Stage 2/6] Synthesizing executive briefing ({mode} mode)...")
    draft = assemble_draft_briefing(
        internal_comms_data=internal_data,
        market_news_data=market_data,
        include_calendar=False,
        mode=mode,
    )
    if "error" in draft:
        print(f"Error assembling draft: {draft['error']}")
        sys.exit(1)

    raw_html = draft["raw_html"]
    print(f"  Draft briefing generated ({len(raw_html)} characters).")

    # --------------------------------------------------------------------------
    # Stage 3: Chief of Staff Editorial Quality Control & Linting
    # --------------------------------------------------------------------------
    print("\n[Stage 3/6] Running Chief of Staff review and VP standards linting...")
    lint_res = lint_vp_standards(raw_html)
    print(
        f"  Lint result: valid={lint_res.get('valid')}, issues={lint_res.get('issues')}"
    )

    eval_res = evaluate_briefing_draft(draft_html=raw_html)
    print(f"  Editor evaluation verdict: {eval_res.get('verdict')}")

    # --------------------------------------------------------------------------
    # Stage 4: Spoken Script Adaptation & Audio Podcast Synthesis (edge-tts)
    # --------------------------------------------------------------------------
    print("\n[Stage 4/6] Adapting script for the ear & synthesizing MP3 audio...")
    script_payload = convert_html_to_spoken_script(html_content=raw_html)
    spoken_script = script_payload["spoken_script"]
    word_count = script_payload["word_count"]
    est_duration = script_payload["estimated_duration_seconds"]
    print(
        f"  Spoken script prepared: {word_count} words (~{est_duration // 60}m {est_duration % 60}s)."
    )

    date_compact = sydney_now.strftime("%y%m%d")
    if mode == "morning":
        mp3_filename = f"[{date_compact}]-Daily Brief.mp3"
        cal_summary = "Your Morning Brief"
        start_time = "06:00:00"
        end_time = "06:30:00"
    else:
        mp3_filename = f"[{date_compact}]-Day In Review.mp3"
        cal_summary = "Day In Review"
        start_time = "19:00:00"
        end_time = "19:30:00"

    script_file = os.path.join(
        tempfile.gettempdir(), f"daily_brief_script_{mode}_{date_compact}.txt"
    )
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(spoken_script)

    mp3_path = os.path.join(tempfile.gettempdir(), mp3_filename)
    if is_mock:
        audio_res = synthesize_podcast_audio(
            spoken_script=spoken_script, output_path=mp3_path, mock=True
        )
        print(
            f"  Mock audio generated: {mp3_path} ({audio_res.get('duration_seconds')}s)."
        )
    else:
        print(
            f"  Synthesizing audio via edge-tts (en-US-AvaNeural / +5% rate) -> {mp3_path}..."
        )
        tts_cmd = [
            "uv",
            "run",
            "--with",
            "edge-tts",
            "edge-tts",
            "--voice",
            "en-US-AvaNeural",
            "--rate",
            "+5%",
            "-f",
            script_file,
            "--write-media",
            mp3_path,
        ]
        subprocess.run(tts_cmd, capture_output=True, text=True, check=True)
        file_size = os.path.getsize(mp3_path)
        print(f"  Audio synthesized successfully! Size: {file_size:,} bytes.")

    # --------------------------------------------------------------------------
    # Stage 5: Upload Podcast to Google Drive & Inject Listen Link
    # --------------------------------------------------------------------------
    print("\n[Stage 5/6] Uploading MP3 to Google Drive (/agents/daily-briefing)...")
    upload_res = upload_podcast_to_drive(
        file_path=mp3_path, folder_id=DRIVE_FOLDER_ID, mock=is_mock
    )
    drive_file_id = upload_res["drive_file_id"]
    drive_web_url = upload_res["drive_web_url"]
    print(f"  Uploaded to Drive! File ID: {drive_file_id}")
    print(f"  Permanent URL: {drive_web_url}")

    final_briefing_html = inject_audio_header_into_briefing(raw_html, drive_web_url)

    # --------------------------------------------------------------------------
    # Stage 6: Autonomous Google Calendar Event Creation & Cleanup
    # --------------------------------------------------------------------------
    print(
        f"\n[Stage 6/6] Scheduling Google Calendar event '{cal_summary}' for {start_time[:5]} Sydney time..."
    )
    cal_res = schedule_briefing_calendar_event(
        briefing_html=final_briefing_html,
        podcast_asset={"drive_file_id": drive_file_id, "drive_web_url": drive_web_url},
        event_date_str=target_date,
        summary=cal_summary,
        start_time=start_time,
        end_time=end_time,
        attachment_title=mp3_filename,
        mock=is_mock,
    )
    print(
        f"  Calendar event scheduled: {cal_res.get('summary')} (ID: {cal_res.get('event_id')})"
    )
    print(f"  Event Link: {cal_res.get('html_link')}")
    print(f"  Attachment: {cal_res.get('attachment_url')}")

    cleanup_res = cleanup_pipeline_artifacts(retention_days=7)
    print(f"  Post-delivery lifecycle cleanup completed: {cleanup_res.get('status')}")

    print("\n" + "=" * 80)
    print(f"AUTONOMOUS {mode.upper()} RUN COMPLETED SUCCESSFULLY!")
    print(f"Calendar Event: {cal_res.get('html_link')}")
    print(f"Podcast Audio:  {drive_web_url}")
    print("=" * 80)

    out_file = os.path.join(
        tempfile.gettempdir(), f"daily_brief_{mode}_{date_compact}_output.json"
    )
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "mode": mode,
                "calendar_event": cal_res,
                "drive_asset": upload_res,
                "final_html": final_briefing_html,
                "spoken_script": spoken_script,
            },
            f,
            indent=2,
        )
    print(f"Saved run output metadata to {out_file}")


if __name__ == "__main__":
    main()
