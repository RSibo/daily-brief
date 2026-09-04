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

"""Editorial Loop Agent Orchestration.

Part of Stage 3 (Quality Control & Editorial Review) in the Daily Brief architecture:
Connects `briefing_writer_agent` (synthesizer) and `editor_reviewer_agent` (reviewer)
within an ADK `LoopAgent`.

The writer drafts the executive briefing (`draft_briefing`), and the reviewer audits
the draft against Google VP standards. If flaws or tone violations are detected,
the reviewer returns critique for the writer to revise in the next iteration.
Once the reviewer approves, it calls `finalize_approved_briefing`, escalates via `exit_loop`,
and emits 'approve', immediately terminating the loop to advance execution to Stage 4.
"""

from google.adk.agents import LoopAgent

from app.sub_agents.briefing_writer_agent import briefing_writer_agent
from app.sub_agents.editor_reviewer_agent import editor_reviewer_agent

editorial_loop = LoopAgent(
    name="editorial_loop",
    sub_agents=[
        briefing_writer_agent,
        editor_reviewer_agent,
    ],
    max_iterations=4,
)
