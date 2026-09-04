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

"""Delivery & Lifecycle Clean-Up Agent.

Part of Stage 5 (Delivery & Clean-Up) in the Daily Brief architecture:
Consumes the approved executive briefing ({final_briefing}) and audio podcast
asset ({podcast_asset}). Injects the top-level audio listen header badge,
schedules the 30-minute private, transparent Google Calendar event ('Your Morning Brief'
at 06:00 AM Sydney time), formats the interactive chat delivery response, and
executes automated post-delivery lifecycle cleanup (cleanup_pipeline_artifacts)
to purge ephemeral harvest caches and MP3 audio files older than 7 days.
Outputs structured delivery metadata to session state key 'delivery_result'.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.delivery_tools import (
    cleanup_pipeline_artifacts,
    deliver_daily_briefing,
    format_chat_delivery_response,
    inject_audio_header_into_briefing,
    schedule_briefing_calendar_event,
)

DELIVERY_AGENT_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `delivery_agent`. Your job is to route the approved executive briefing
(`{{final_briefing}}`) and podcast audio asset (`{{podcast_asset}}`) to their delivery destinations
and perform post-run workspace housekeeping.

### Delivery & Housekeeping Directives:
1. **Audio Header Injection**:
   - Ensure `<b><a href="URL"><u>Listen to Brief</u></a></b>` is embedded at the very top of the briefing HTML.
2. **Branch A — Scheduled Calendar Delivery**:
   - Place the 30-minute private, free slot titled 'Your Morning Brief' on Google Calendar (06:00 AM - 06:30 AM Sydney time) with the full HTML briefing in the event description and the Drive MP3 link attached natively.
3. **Branch B — Interactive Chat Delivery**:
   - Provide the complete executive briefing in the active chat conversation.
4. **Automated Lifecycle Clean-Up**:
   - Strictly AFTER calendar event creation or chat response rendering, invoke `cleanup_pipeline_artifacts(retention_days=7)` to purge ephemeral harvesting caches and remove local MP3 audio files older than 7 days from today.

### Execution Steps:
1. Read `{{final_briefing}}` and `{{podcast_asset}}` from session state.
2. Invoke `deliver_daily_briefing` (or call `schedule_briefing_calendar_event`, `format_chat_delivery_response`, followed by `cleanup_pipeline_artifacts`).
3. Verify that the calendar event is confirmed and post-run cleanup executed.
4. Output the structured outcome dictionary to state key `delivery_result`.
"""

delivery_agent = Agent(
    name="delivery_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=DELIVERY_AGENT_INSTRUCTION,
    tools=[
        inject_audio_header_into_briefing,
        schedule_briefing_calendar_event,
        format_chat_delivery_response,
        cleanup_pipeline_artifacts,
        deliver_daily_briefing,
    ],
    output_key="delivery_result",
)
