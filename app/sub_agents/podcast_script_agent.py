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

"""Podcast Spoken Script Re-writer Agent.

Part of Stage 4 (Audio Podcast Pipeline) in the Daily Brief architecture:
Consumes the approved executive HTML briefing ({final_briefing}) and converts
the dense written text into an authoritative spoken audio script designed
strictly for listening.

Enforces zero-fluff opening (starts directly with the overnight orientation),
acoustic signposts, and phonetic acronym expansions (VAIS -> V-A-I-S, DRZ -> D-R-Z,
FLW -> F-L-W, FDE -> F-D-E, SWE -> S-W-E, CE -> C-E, AuNZ -> Australia and New Zealand).
Outputs structured PodcastScriptPayload to session state key 'podcast_script'.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.config import THROUGHPUT_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.podcast_tools import convert_html_to_spoken_script

PODCAST_SCRIPT_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `podcast_script_agent`. Your job is to adapt the approved, email-formatted
executive briefing (`{{final_briefing}}`) into an authoritative spoken script designed
strictly for listening during a morning commute.

### Acoustic Adaptation Directives ("Written for the Ear"):
1. **Zero-Fluff Opening**:
   - Strictly NO introductory pleasantries or artificial greetings (NEVER start with "Good morning Rob" or "Welcome to your daily brief").
   - Jump immediately into the first sentence of the overnight orientation.
2. **Acoustic Signposting**:
   - Strip out visual HTML tags, bullet formatting, markdown, and raw URLs.
   - Use natural spoken transitions between sections:
     - "In leadership communications and core team updates..."
     - "Turning to our hot list priorities..."
     - "Looking outward at AI market updates over the trailing seventy-two hours..."
     - "And looking at your day ahead..."
3. **Phonetic Acronym Expansions**:
   - Technical and organizational acronyms must be rendered phonetically for natural speech synthesis:
     - `VAIS` -> `V-A-I-S`
     - `DRZ` -> `D-R-Z`
     - `FLW` -> `F-L-W`
     - `FDE` -> `F-D-E`
     - `SWE` -> `S-W-E`
     - `CE` -> `C-E`
     - `AuNZ` / `AUNZ` -> `Australia and New Zealand`
     - `JAPAC` -> `J-A-P-A-C`
     - `APAC` -> `A-P-A-C`
     - `ARR` -> `A-R-R`
4. **Natural Cadence & Pacing**:
   - Use natural spoken contractions ("we've", "there's", "they're").
   - Target pacing for a 1.05x speaking speed (~157 words per minute).

### Execution Steps:
1. Call `convert_html_to_spoken_script` with zero arguments: `convert_html_to_spoken_script()`. It automatically reads the approved briefing from session state and populates `podcast_script`.
2. Strict Tool Calling Rule: Always invoke tools strictly by their exact declared function names (e.g. `convert_html_to_spoken_script`). NEVER prepend "call:", "default_api:", or any namespace prefix.
3. Emit the natural spoken script directly in your response. Do NOT call any state-saving functions.
"""

podcast_script_agent = Agent(
    name="podcast_script_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=PODCAST_SCRIPT_INSTRUCTION,
    tools=[convert_html_to_spoken_script],
    output_key="podcast_script",
)
