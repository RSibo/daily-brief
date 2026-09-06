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

"""Podcast Spoken Overview Editorial Loop Orchestration.

Part of Stage 4a (Acoustic Rewriting & QC) in the Daily Brief architecture:
Connects `podcast_script_writer_agent` (acoustic rewriter) and
`podcast_editor_reviewer_agent` (audio QC reviewer) within an ADK `LoopAgent`
with `max_iterations=5`.

The writer adapts the approved written executive briefing ({final_briefing})
into a punchy, conversational, spoken-for-the-ear script adhering to the
`audio-overview-script-editor` skill. The reviewer lints and audits the draft
against strict acoustic criteria (zero markdown artifacts, no bracketed dates,
linear sentence brevity, high contraction density, zero greeting fluff).
When the reviewer approves, it invokes `finalize_approved_podcast_script`
and `exit_loop`, populating `podcast_script` for `podcast_creator_agent`.
"""

from google.adk.agents import LoopAgent

from app.sub_agents.podcast_editor_reviewer_agent import (
    podcast_editor_reviewer_agent,
)
from app.sub_agents.podcast_script_writer_agent import (
    podcast_script_writer_agent,
)

podcast_editorial_loop = LoopAgent(
    name="podcast_editorial_loop",
    sub_agents=[
        podcast_script_writer_agent,
        podcast_editor_reviewer_agent,
    ],
    max_iterations=5,
)
