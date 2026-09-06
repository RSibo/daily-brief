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
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.sub_agents.market_news_agent import run_market_news_agent
from app.tools.delivery_tools import (
    cleanup_pipeline_artifacts,
    inject_audio_header_into_briefing,
    schedule_briefing_calendar_event,
)
from app.tools.editor_tools import (
    BANNED_PHRASES,
    EMOJI_PATTERN,
    evaluate_briefing_draft,
    finalize_approved_briefing,
    lint_vp_standards,
)
from app.tools.internal_comms_tools import harvest_all_internal_communications
from app.tools.podcast_editor_tools import (
    BANNED_AUDIO_OPENINGS,
    BANNED_HYPERBOLE_WORDS,
    ROBOTIC_COUNTING_PATTERNS,
    UNCONTRACTED_PAIRS,
    evaluate_podcast_script,
    finalize_approved_podcast_script,
    lint_podcast_spoken_script,
)
from app.tools.podcast_tools import (
    convert_html_to_spoken_script,
    synthesize_podcast_audio,
    upload_podcast_to_drive,
)
from app.tools.synthesis_tools import assemble_draft_briefing

SYDNEY_TZ = ZoneInfo("Australia/Sydney")
DRIVE_FOLDER_ID = "1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV"


def revise_briefing_draft(html_content: str, issues: list[str]) -> str:
    """Applies writer revision rules to briefing HTML based on reviewer critique."""
    revised = html_content
    # Strip emojis
    revised = EMOJI_PATTERN.sub("", revised)
    # Remove banned hyperbole / clichés
    for phrase in BANNED_PHRASES:
        revised = re.sub(re.escape(phrase), "", revised, flags=re.IGNORECASE)
    # Remove bolding inside executive summary if flagged
    summary_match = re.search(
        r"(?:OVERNIGHT SUMMARY|EXECUTIVE WRAP-UP \(DECISION & TRIAGE ORIENTATION\))(?:</b>|</h3>)(?:<br\s*/?>\s*)+(.*?)(?:<br\s*/?>\s*<br\s*/?>|<b>\s*[A-Z0-9\s&]{4,}</b>|<h[1-6]>|$)",
        revised,
        re.IGNORECASE | re.DOTALL,
    )
    if summary_match:
        summary_raw = summary_match.group(1)
        summary_clean = re.sub(
            r"</?(?:b|strong)>", "", summary_raw, flags=re.IGNORECASE
        )
        revised = revised.replace(summary_raw, summary_clean)
    # Fix placeholder links
    revised = re.sub(
        r'href=["\'](?:#|javascript:[^"\']*)["\']',
        'href="https://workspace.google.com"',
        revised,
    )
    return revised


def run_editorial_loop(
    internal_data: dict[str, Any],
    market_data: dict[str, Any],
    mode: str = "morning",
    max_iterations: int = 4,
) -> dict[str, Any]:
    """Executes the Chief of Staff Editorial Review Loop (Stage 2 & 3).

    Iteratively pairs briefing_writer_agent (synthesis) and editor_reviewer_agent (auditor)
    for up to max_iterations (default 4) until the executive briefing satisfies all
    Google VP standards or reaches max iterations.
    """
    print(
        f"\n[Stages 2 & 3/6] Running Chief of Staff Editorial Review Loop (editorial_loop, max_iterations={max_iterations})..."
    )
    current_html = ""
    issues: list[str] = []

    for iteration in range(1, max_iterations + 1):
        print(f"\n--- [Editorial Loop] Iteration {iteration}/{max_iterations} ---")
        if iteration == 1:
            print("  [Writer Agent] Assembling baseline executive briefing draft...")
            draft = assemble_draft_briefing(
                internal_comms_data=internal_data,
                market_news_data=market_data,
                include_calendar=False,
                mode=mode,
            )
            if "error" in draft:
                print(f"  Error assembling draft: {draft['error']}")
                sys.exit(1)
            current_html = draft["raw_html"]
            print(
                f"  [Writer Agent] Initial draft assembled ({len(current_html)} characters)."
            )
        else:
            print("  [Writer Agent] Applying revisions from reviewer critique...")
            current_html = revise_briefing_draft(current_html, issues)
            print(
                f"  [Writer Agent] Revised draft prepared ({len(current_html)} characters)."
            )

        print("  [Reviewer Agent] Auditing draft against VP standards...")
        lint_res = lint_vp_standards(current_html)
        eval_res = evaluate_briefing_draft(draft_html=current_html)
        verdict = eval_res.get("verdict", "revise")
        issues = lint_res.get("issues", [])
        critique = eval_res.get("critique", "")

        print(
            f"  [Reviewer Agent] Verdict: {verdict.upper()} (valid={lint_res.get('valid')})"
        )
        if verdict == "approve" and lint_res.get("valid"):
            print(f"  [Reviewer Agent] Briefing APPROVED on iteration {iteration}!")
            final_payload = finalize_approved_briefing(
                draft_html=current_html,
                reviewer_notes=f"Approved on iteration {iteration} - satisfies all Google VP standards.",
            )
            print(
                "  [Reviewer Agent] Finalized approved briefing payload & exited loop."
            )
            return final_payload

        print(f"  [Reviewer Agent] REVISE requested: {critique}")
        if issues:
            print(f"  [Reviewer Agent] Issues flagged ({len(issues)}):")
            for idx, issue in enumerate(issues, 1):
                print(f"    {idx}. {issue}")

    print(
        f"\n  [Reviewer Agent] Max iterations ({max_iterations}) reached. Finalizing with standard sanitization."
    )
    sanitized_html = revise_briefing_draft(current_html, issues)
    return finalize_approved_briefing(
        draft_html=sanitized_html,
        reviewer_notes=f"Approved at max iterations limit ({max_iterations}) with applied sanitization.",
    )


def revise_podcast_script(script_text: str, issues: list[str]) -> str:
    """Applies acoustic writer revision rules to spoken audio script based on reviewer critique."""
    revised = script_text

    # 1. Zero visual artifacts: markdown headers, bold/italics, bullet dashes, speaker tags, HTML tags
    revised = re.sub(r"(?m)^\s*#+\s*", "", revised)
    revised = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", revised)
    revised = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", revised)
    revised = re.sub(r"(?m)^\s*[-*•]\s+", "", revised)
    revised = re.sub(
        r"\[(?:Host|Narrator|Speaker)\]:\s*", "", revised, flags=re.IGNORECASE
    )
    revised = re.sub(r"<[^>]+>", "", revised)

    # 2. Rephrase bracketed citations into natural narrative
    def _rephrase_bracket(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        entity_date = re.match(
            r"^([^\-\u2013\u2014]+)\s*[\-\u2013\u2014]\s*\d{4}-\d{2}-\d{2}",
            content,
        )
        if entity_date:
            return f"{entity_date.group(1).strip()} announced"
        return content

    revised = re.sub(r"\[([^\]]+)\]", _rephrase_bracket, revised)

    # 3. Clean mandatory opening hook ("Let's begin; ")
    for banned in BANNED_AUDIO_OPENINGS:
        if revised.lower().strip().startswith(banned):
            revised = re.sub(
                rf"^\s*{re.escape(banned)}[,.]?\s*", "", revised, flags=re.IGNORECASE
            )
    if not revised.lower().strip().startswith("let's begin"):
        revised = "Let's begin; " + revised.lstrip()

    # 4. Zero robotic counting
    for pat in ROBOTIC_COUNTING_PATTERNS:
        revised = re.sub(pat, "Alongside that,", revised, flags=re.IGNORECASE)

    # 5. Contraction density
    for pat, contracted in UNCONTRACTED_PAIRS:
        revised = re.sub(pat, contracted, revised, flags=re.IGNORECASE)

    # 6. Hyperbole ban
    for h in BANNED_HYPERBOLE_WORDS:
        revised = re.sub(
            rf"\b{re.escape(h)}\b", "significant", revised, flags=re.IGNORECASE
        )

    # 7. Sentence brevity: break long compound sentences (> 22 words)
    sentences = re.split(r"(?<=[.!?])\s+", revised.strip())
    rebuilt: list[str] = []
    for s in sentences:
        words = s.strip().split()
        if len(words) > 22:
            if " alongside " in s:
                parts = s.split(" alongside ", 1)
                rebuilt.append(parts[0] + ".")
                rebuilt.append("Alongside that, " + parts[1])
            elif " while " in s:
                parts = s.split(" while ", 1)
                rebuilt.append(parts[0] + ".")
                rebuilt.append("At the same time, " + parts[1])
            elif ", and " in s:
                parts = s.split(", and ", 1)
                rebuilt.append(parts[0] + ".")
                rebuilt.append("And " + parts[1])
            else:
                rebuilt.append(s)
        else:
            rebuilt.append(s)

    revised = " ".join(rebuilt)
    paragraphs = [p.strip() for p in revised.split("\n\n") if p.strip()]
    return "\n\n".join(paragraphs)


def run_podcast_editorial_loop(
    final_briefing_html: str,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Executes the Podcast Spoken Overview Editorial Loop (Stage 4a).

    Iteratively pairs podcast_script_writer_agent (acoustic rewriter) and
    podcast_editor_reviewer_agent (audio QC auditor) for up to max_iterations (default 5)
    until the spoken script satisfies all acoustic guidelines (audio-overview-script-editor)
    or reaches max iterations.
    """
    print(
        f"\n[Stage 4/6] Running Podcast Spoken Overview Editorial Loop (podcast_editorial_loop, max_iterations={max_iterations})..."
    )
    current_script = ""
    issues: list[str] = []

    for iteration in range(1, max_iterations + 1):
        print(
            f"\n--- [Podcast Editorial Loop] Iteration {iteration}/{max_iterations} ---"
        )
        if iteration == 1:
            print(
                "  [Podcast Writer Agent] Adapting approved executive briefing for the ear..."
            )
            script_payload = convert_html_to_spoken_script(
                html_content=final_briefing_html
            )
            current_script = script_payload.get("spoken_script", "")
            print(
                f"  [Podcast Writer Agent] Initial spoken draft produced: "
                f"{script_payload.get('word_count')} words (~{script_payload.get('estimated_duration_seconds')}s)."
            )
        else:
            print(
                "  [Podcast Writer Agent] Applying acoustic revisions based on reviewer critique..."
            )
            current_script = revise_podcast_script(current_script, issues)
            words = len(current_script.split())
            print(
                f"  [Podcast Writer Agent] Revised spoken script prepared ({words} words)."
            )

        print(
            "  [Podcast Reviewer Agent] Auditing spoken script against Chief of Staff acoustic standards..."
        )
        lint_res = lint_podcast_spoken_script(current_script)
        eval_res = evaluate_podcast_script(draft_script=current_script)
        verdict = eval_res.get("verdict", "revise")
        issues = lint_res.get("issues", [])
        critique = eval_res.get("critique", "")

        print(
            f"  [Podcast Reviewer Agent] Verdict: {verdict.upper()} (valid={lint_res.get('valid')})"
        )
        if verdict == "approve" and lint_res.get("valid"):
            print(
                f"  [Podcast Reviewer Agent] Spoken script APPROVED on iteration {iteration}!"
            )
            final_payload = finalize_approved_podcast_script(
                spoken_script=current_script,
                reviewer_notes=f"Approved on iteration {iteration} - satisfies all acoustic standards.",
            )
            print(
                "  [Podcast Reviewer Agent] Finalized approved podcast payload & exited loop."
            )
            return final_payload

        print(f"  [Podcast Reviewer Agent] REVISE requested: {critique}")
        if issues:
            print(f"  [Podcast Reviewer Agent] Issues flagged ({len(issues)}):")
            for idx, issue in enumerate(issues, 1):
                print(f"    {idx}. {issue}")

    print(
        f"\n  [Podcast Reviewer Agent] Max iterations ({max_iterations}) reached. Finalizing with acoustic normalization."
    )
    sanitized_script = revise_podcast_script(current_script, issues)
    return finalize_approved_podcast_script(
        spoken_script=sanitized_script,
        reviewer_notes=f"Approved at max iterations limit ({max_iterations}) with acoustic normalization.",
    )


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
    # Stages 2 & 3: Executive Synthesis & Editorial Review Loop (editorial_loop)
    # --------------------------------------------------------------------------
    final_briefing = run_editorial_loop(
        internal_data=internal_data,
        market_data=market_data,
        mode=mode,
        max_iterations=4,
    )
    final_html = final_briefing["final_html"]
    print(
        f"\n  Approved executive briefing payload ready ({len(final_html)} characters)."
    )

    # --------------------------------------------------------------------------
    # Stage 4: Podcast Spoken Overview Editorial Loop & MP3 Synthesis
    # --------------------------------------------------------------------------
    podcast_payload = run_podcast_editorial_loop(
        final_briefing_html=final_html,
        max_iterations=5,
    )
    spoken_script = podcast_payload["spoken_script"]
    word_count = podcast_payload["word_count"]
    est_duration = podcast_payload["estimated_duration_seconds"]
    print(
        f"\n  Approved spoken script ready: {word_count} words (~{est_duration // 60}m {est_duration % 60}s)."
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

    final_briefing_html = inject_audio_header_into_briefing(final_html, drive_web_url)

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
                "final_briefing": final_briefing,
                "podcast_payload": podcast_payload,
                "final_html": final_briefing_html,
                "spoken_script": spoken_script,
            },
            f,
            indent=2,
        )
    print(f"Saved run output metadata to {out_file}")


if __name__ == "__main__":
    main()
