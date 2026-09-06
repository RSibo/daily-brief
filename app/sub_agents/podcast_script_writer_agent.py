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

"""Podcast Spoken Script Writer Sub-Agent.

Part of Stage 4a (Podcast Editorial Loop) in the Daily Brief architecture:
Consumes the approved executive HTML briefing ({final_briefing}) and converts
the dense written text into a punchy, high-tempo, narrative spoken audio script.
Iterates based on feedback from the podcast_editor_reviewer_agent ({podcast_script_critique}).

Implements the acoustic transformation rules from the `audio-overview-script-editor` skill:
- Converts mechanical bracketed metadata citations ("[Google DeepMind - 2026-09-02] Releases GPT-6")
  into smooth narrative ("Google DeepMind released GPT-6").
- Enforces linear Subject-Verb-Object sentences capped at 18 words.
- Drives high contraction density (>= 80% on auxiliary verbs).
- Strips 100% of visual artifacts (markdown asterisks, hashes, brackets, bullet points).
- Opens directly on the lead operational signal with zero greeting pleasantries.
Outputs the working spoken draft to session state key 'podcast_script_draft'.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.config import THROUGHPUT_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION

PODCAST_SCRIPT_WRITER_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `podcast_script_writer_agent`. Your job is to transform the dense, approved
executive written briefing (`{{final_briefing}}`) into a concise, high-tempo, spoken audio script
designed strictly for acoustic comprehension during an executive morning walk or commute.

If revising, address the specific acoustic critique provided in `{{podcast_script_critique}}`.

### Audio Overview Transformation Rules ("Written for the Ear"):

1. **Mandatory Opening Hook**:
   - Start the script with the exact opening phrase: "Let's begin; " (or "Let's begin; ...") followed immediately by the first operational update.
   - Example: "Let's begin; overnight communications remained focused on partner escalations..."
   - Strictly NO introductory pleasantries or host banter (NEVER say "Good morning Rob", "Welcome back", or "Here is your audio brief").

2. **Narrative Rephrasing of Bracketed Citations**:
   - NEVER read bracketed dates or source tags out loud!
   - BAD: "[Google DeepMind - 2026-09-02] Releases GPT-6 Astra with Recurrent Depth Reasoning Technique..."
   - GOOD: "Google DeepMind released GPT-6 Astra with recurrent depth reasoning..."
   - BAD: "[OpenAI - 2026-09-03] Launches..."
   - GOOD: "OpenAI announced..."

3. **Punchy, Linear Sentences (Max 18 Words)**:
   - Structure sentences strictly as **Subject -> Verb -> Object**.
   - Cap individual sentences at 18 words maximum to prevent listener cognitive fatigue. Split compound written sentences into two crisp spoken sentences.

4. **High Contraction Density (>= 80%)**:
   - Spoken English naturally uses contractions. Always use "we've", "there's", "it's", "they'll", "they're", "don't", "can't", "won't", "hasn't", "that's".

5. **Acoustic Transitions & Breathing Pauses**:
   - Eliminate numbered lists and bullet points. Use smooth narrative transitions:
     - "In leadership communications and core updates..."
     - "Turning to our hot list priorities..."
     - "Looking outward at AI market movements..."
   - Use em-dashes (`—`) for half-second pauses and ellipses (`...`) before key numbers or punchlines.

6. **Zero Visual Artifacts**:
   - Strictly output pure spoken text with blank lines between natural vocal paragraphs.
   - NO markdown symbols (`#`, `*`, `_`, `[ ]`, `>`), NO bullet dashes (`- `), and NO stage tags (`[Host]:`, `(pause)`).

7. **Target Runtime & Word Depth (6 to 15 Minutes)**:
   - The podcast duration must be 6 to 15 minutes, depending on content volume and impact.
   - At 130–150 words per minute (at 1.05x speed), this corresponds to approximately 800 to 2,400 words.
   - If content is impactful with extensive leadership, customer, and frontier AI updates, expand with rich operational context, strategic significance, and next steps to sustain up to 15 minutes (~2,200 to 2,400 words).
   - If updates are light, provide complete background context to reach at least 6 minutes (~800 words).

### Execution Directives:
- Emit your finalized spoken text directly in your response.
- Do NOT output markdown code blocks or metadata wrappers. Output only the pure spoken script prose.
"""

podcast_script_writer_agent = Agent(
    name="podcast_script_writer_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=PODCAST_SCRIPT_WRITER_INSTRUCTION,
    output_key="podcast_script_draft",
)
