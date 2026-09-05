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

"""Internal Communications Harvest Agent.

Part of Stage 1 (Parallel Harvesting) in the Daily Brief architecture:
Harvests unread Gmail from VIP leadership/direct reports, Google Chat DMs/spaces,
and today's calendar commitments over the strict 24h Sydney lookback window.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.config import THROUGHPUT_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.internal_comms_tools import (
    fetch_unread_leadership_threads,
    get_daily_calendar_agenda,
    harvest_all_internal_communications,
    scan_target_chat_spaces,
)

INTERNAL_COMMS_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `internal_comms_agent`. Your job is to harvest, filter, and structure
all internal communications received over the last 24 hours from run time in Sydney time.

### Instructions:
1. Execute `harvest_all_internal_communications` (or invoke individual tools `fetch_unread_leadership_threads`, `scan_target_chat_spaces`, and `get_daily_calendar_agenda`).
2. Filter out all automated system alerts, newsletters, calendar decline/accept churn, and kudos/gThanks.
3. Classify senders into VIP categories (leadership, direct_report).
4. Extract canonical thread deep links and action items.
5. Populate the internal comms payload in session state.
"""

internal_comms_agent = Agent(
    name="internal_comms_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INTERNAL_COMMS_INSTRUCTION,
    tools=[
        fetch_unread_leadership_threads,
        scan_target_chat_spaces,
        get_daily_calendar_agenda,
        harvest_all_internal_communications,
    ],
    output_key="internal_comms_data",
)
