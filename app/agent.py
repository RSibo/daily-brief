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

"""Master Orchestrator Agent for the Daily Brief System.

Assembles and executes the multi-agent intelligence pipeline:
- Stage 1 (Harvesting): ParallelAgent executing internal_comms_agent and market_news_agent.
- Stage 2 & 3 (Synthesis & Editorial Review): editorial_loop (briefing_writer_agent + editor_reviewer_agent, max_iterations=4).
- Stage 4 (Audio Podcast Pipeline): SequentialAgent executing podcast_script_agent and podcast_creator_agent.
- Stage 5 (Delivery & Clean-Up): delivery_agent (injects listen link, creates Google Calendar event, formats chat response, and triggers automated 7-day lifecycle cleanup).
"""

import os
from typing import Any

import google.auth
from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.apps import App

from app.sub_agents.delivery_agent import delivery_agent
from app.sub_agents.editorial_loop import editorial_loop
from app.sub_agents.internal_comms_agent import internal_comms_agent
from app.sub_agents.market_news_agent import market_news_agent
from app.sub_agents.podcast_creator_agent import podcast_creator_agent
from app.sub_agents.podcast_script_agent import podcast_script_agent

# Configure Google Cloud environment
try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
except Exception:
    pass

os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# Stage 1: Parallel multi-channel harvesting
harvesters = ParallelAgent(
    name="harvesters",
    sub_agents=[
        internal_comms_agent,
        market_news_agent,
    ],
)

# Stage 4: Sequential acoustic rewriting and audio creation
podcast_pipeline = SequentialAgent(
    name="podcast_pipeline",
    sub_agents=[
        podcast_script_agent,
        podcast_creator_agent,
    ],
)


class DailyBriefOrchestrator(SequentialAgent):
    """Master orchestrator sequential pipeline exposing tools across all stages."""

    @property
    def tools(self) -> list[Any]:
        """Aggregates all unique custom tools across the multi-agent pipeline."""
        collected: list[Any] = []

        def _gather(agent: Any) -> None:
            if agent is not self and hasattr(agent, "tools") and agent.tools:
                for t in agent.tools:
                    if hasattr(t, "__module__") and t.__module__.startswith(
                        "app.tools"
                    ):
                        if t not in collected:
                            collected.append(t)
            if hasattr(agent, "sub_agents") and agent.sub_agents:
                for sa in agent.sub_agents:
                    _gather(sa)

        _gather(self)
        return collected


# Master Orchestrator: End-to-end multi-agent execution pipeline
root_agent = DailyBriefOrchestrator(
    name="daily_brief_orchestrator",
    sub_agents=[
        harvesters,
        editorial_loop,
        podcast_pipeline,
        delivery_agent,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
