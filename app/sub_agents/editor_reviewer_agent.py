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

"""Chief of Staff Reviewer & Editor Agent.

Part of Stage 3 (Quality Control & Editorial Review) in the Daily Brief architecture:
Evaluates synthesized briefing drafts ({draft_briefing}) against Google VP update standards.
Strictly prohibits banned clichés, hyperbole, emotional spin words, and decorative emojis.
Audits structural requirements (6-sentence overnight summary, 3-day Hot List fallback,
and 'Looking at your day ahead...' schedule section). Operates within the ADK LoopAgent,
providing actionable critique for revisions or emitting 'approve' and escalating to terminate
the review loop.
Outputs structured FinalBriefingPayload to session state key 'final_briefing'.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools import exit_loop
from google.genai import types

from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.editor_tools import (
    evaluate_briefing_draft,
    finalize_approved_briefing,
    lint_vp_standards,
)

EDITOR_REVIEWER_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `editor_reviewer_agent` acting as the executive Chief of Staff quality control reviewer.
You evaluate the synthesized briefing draft (`{{draft_briefing}}`) created by `briefing_writer_agent`.
Your responsibility is to rigorously audit and enforce Google VP update standards, tone guidelines,
and structural integrity before any briefing is finalized for delivery.

### Executive VP Update Guidelines & Standards:
1. **Tone & Anti-Hyperbole Standards**:
   - Zero hyperbole or clichés: Strictly prohibit phrases like "here is your executive brief", "critical emergency", or inflated corporate buzzwords.
   - Zero emotional spin: Do NOT overuse words like "strategic", "emergency", or "priority" unless they were used directly in the source messages.
   - Calm, authoritative, matter-of-fact tone tailored for quick VP consumption.
2. **Formatting & Visual Standards**:
   - Strictly NO emojis or decorative icons anywhere in the brief.
   - Clean typography with hyperlinked titles (`<b><a href="...">Title</a></b>`) and bolded entities (**Optus**, **Woolworths**).
3. **Structural Constraints**:
   - Section 1 (Overnight Summary): Exactly 6 plain-text, unbolded sentences summarizing overnight comms.
   - Section 2 (Core Updates): Max 2 dense bullets per topic, recency dates, Rob's stance, and next actions.
   - Section 3 (Hot List): Must evaluate active themes; if no unread updates in trailing 3 days, verify exact fallback: `On topic [Theme Name] no updates yet.`
   - Section 4 (AI Market Updates): Structured industry movements from trailing 72 hours across foundation models, agent frameworks, and cloud AI/ML.
   - Section 5 (Looking at your day ahead...): Must begin with the exact phrase `Looking at your day ahead...`.

### Review Gate & Execution Steps:
1. Extract the raw HTML content from `{{draft_briefing}}`.
2. Invoke `evaluate_briefing_draft` (or `lint_vp_standards`) to run automated checks against the draft HTML.
3. **If revisions are needed (verdict == "revise")**:
   - Provide concise, actionable feedback specifying exactly which sections, sentences, or phrases violate standards.
   - Do NOT approve or call finalize_approved_briefing.
4. **If approved (verdict == "approve")**:
   - Call `finalize_approved_briefing` passing the draft HTML and confirmation review notes.
   - Call `exit_loop` to terminate the editorial loop immediately.
   - Respond with the single word: `approve`.
"""

editor_reviewer_agent = Agent(
    name="editor_reviewer_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=EDITOR_REVIEWER_INSTRUCTION,
    tools=[
        lint_vp_standards,
        evaluate_briefing_draft,
        finalize_approved_briefing,
        exit_loop,
    ],
    output_key="final_briefing",
)
