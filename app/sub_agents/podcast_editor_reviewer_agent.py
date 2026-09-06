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

"""Chief of Staff Audio Reviewer & Podcast Editor Agent.

Part of Stage 4a (Podcast Editorial Loop) in the Daily Brief architecture:
Evaluates synthesized spoken audio drafts ({podcast_script_draft}) against
the acoustic standards established in the `audio-overview-script-editor` skill.

Audits:
- Zero visual artifacts (markdown asterisks, hashes, brackets, bullet dashes).
- Mechanical metadata brackets (e.g. '[Google DeepMind - 2026-09-02]').
- Sentence length (linear sentences strictly capped under 18-22 words).
- High contraction density (natural spoken contractions).
- Zero greeting pleasantries (clean, direct business open).
- Zero robotic index counting ('item one', 'secondly').
- Hyperbole ban (anti-buzzword compliance).

Operates within the ADK LoopAgent, returning actionable critique for revisions
or calling `finalize_approved_podcast_script` and `exit_loop` upon approval.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools import exit_loop
from google.genai import types

from app.config import ANALYTICAL_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.podcast_editor_tools import (
    evaluate_podcast_script,
    finalize_approved_podcast_script,
    lint_podcast_spoken_script,
)

PODCAST_EDITOR_REVIEWER_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `podcast_editor_reviewer_agent` acting as the executive Chief of Staff audio quality control reviewer.
You evaluate the spoken audio draft (`{{podcast_script_draft}}`) produced by `podcast_script_writer_agent`.
Your responsibility is to enforce rigorous acoustic standards, vocal punchiness, and spoken clarity
before the script is submitted for audio synthesis and publication.

### Audio Overview Review Standards:
1. **Zero Visual Artifacts**:
   - Strictly NO markdown symbols (`*`, `#`, `_`, `[ ]`, `>`), bullet points, dashes at line starts, or speaker tags.
   - Script must be pure, clean spoken paragraphs separated by blank lines.
2. **No Mechanical Bracketed Citations**:
   - Prohibit date/source brackets like `[Google DeepMind - 2026-09-02]`. These must be converted to smooth narrative phrasing.
3. **Sentence Brevity & Linear Syntax**:
   - Sentences must be linear Subject-Verb-Object structures capped at 18 words. Flag any run-on or multi-clause sentences.
4. **Contraction Density**:
   - Spoken language requires contractions ("we've", "there's", "it's", "they'll", "don't"). Uncontracted formal syntax is unacceptable for audio.
5. **Zero-Fluff Opening**:
   - First sentence must deliver immediate operational signal. Strictly reject greeting filler ("Good morning", "Welcome to").
6. **Zero Robotic Counting**:
   - Reject "item number one", "secondly", "point one". Transitions must sound conversational.
7. **Hyperbole Ban**:
   - Reject unquoted buzzwords ("game-changer", "revolutionary", "critical emergency").

### Review Execution Steps:
1. Call `evaluate_podcast_script()` with zero arguments (it automatically loads `podcast_script_draft` from session state).
2. If revisions are needed (verdict == "revise"):
   - Provide concise, actionable feedback specifying exactly which sentences are too long, which brackets remain, or where contractions are missing.
   - Do NOT approve or call finalize_approved_podcast_script.
3. If approved (verdict == "approve"):
   - Call `finalize_approved_podcast_script()` with zero arguments (it automatically commits `podcast_script` to session state and escalates).
   - Call `exit_loop()` to terminate the editorial loop immediately.
   - Respond with the single word: `approve`.
"""

podcast_editor_reviewer_agent = Agent(
    name="podcast_editor_reviewer_agent",
    model=Gemini(
        model=ANALYTICAL_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=PODCAST_EDITOR_REVIEWER_INSTRUCTION,
    tools=[
        lint_podcast_spoken_script,
        evaluate_podcast_script,
        finalize_approved_podcast_script,
        exit_loop,
    ],
    output_key="podcast_script_critique",
)
