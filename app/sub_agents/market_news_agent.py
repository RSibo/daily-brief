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

"""External Market News Harvest Agent.

Part of Stage 1 (Parallel Harvesting) in the Daily Brief architecture:
Scans verified external generative AI developments, model releases, agent frameworks,
and cloud AI movements over the strict 72-hour trailing window (Sydney time).
Outputs structured MarketHarvestPayload to session state key 'market_news_data'.
"""

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.genai import types

from app.config import THROUGHPUT_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.market_news_tools import harvest_all_market_news

SYDNEY_TZ = ZoneInfo("Australia/Sydney")

MARKET_NEWS_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Persona:
You are the `market_news_agent` providing external technical market intelligence for the Head of AI/ML.
Your principal is a deeply technical AI/ML executive who evaluates architectural breakthroughs,
novel model paradigms, and hidden signals that could represent the next wave of innovation,
rather than minor library version bumps or marketing announcements.

### Coverage Domains & Technical Signal Priorities:
1. **Novel Model Architectures & Reasoning Paradigms**:
   - Frontier labs (Google DeepMind, DeepSeek, OpenAI, Anthropic, Meta, Mistral, Qwen).
   - Test-time compute scaling, dynamic thinking budgets, and inference self-verification.
   - Mixture-of-Experts (MoE) routing efficiency, Multi-head Latent Attention (MLA), DualPipe computation overlap, and hybrid SSM/Transformer architectures.
   - Reinforcement learning from verifiable rewards (RLVR), self-correcting reasoning loops, and post-training distillation.
2. **AI Agent Systems & Production Frameworks**:
   - Enterprise agent architectures and multi-agent supervisory patterns (Google ADK, LangGraph, CrewAI, AutoGen).
   - Transactional state version travel, durable execution, sandboxed tool generation, and automated quality flywheel evals.
3. **Frontier AI Compute, Silicon & Clusters**:
   - Hyperscaler AI platforms and specialized accelerator clusters (Google Cloud TPU v6e Trillium with optical circuit switching, NVIDIA Blackwell GB200 NVL72 deployments, AWS Trainium, Azure Maia, CoreWeave scale-out inference).

### Strict Negative Filters:
- Exclude minor library updates, patch versions (e.g. v0.1.2 bugfixes), and wrapper utilities.
- Exclude outdated models and older 2024/2025 news (such as older Claude 3.5 Sonnet or Llama 3.0/3.1 announcements).
- Exclude generic IT/cloud infrastructure (standard compute, non-AI storage, relational databases).
- Exclude speculative rumors, clickbait, hyperbolic claims ("mind-blowing", "game-changer", "will replace all developers"), and corporate PR fluff.
- Strictly enforce the trailing 72-hour window from runtime (Sydney time).
- Ensure every item includes a canonical primary citation URL and verified technical specifics.

### Execution Instructions:
1. Execute multiple targeted queries using `google_search` to discover breaking announcements from the trailing 72 hours across:
   - Foundation models & frontier lab releases (e.g., "Google DeepMind announcement", "Gemini 2.5 release", "OpenAI news", "Anthropic Claude update", "DeepSeek open weights release", "Meta Llama release").
   - AI agent frameworks (e.g., "Google ADK release notes", "LangGraph release", "AI agents enterprise framework").
   - Hyperscaler AI/ML & custom silicon (e.g., "Google Cloud TPU Trillium", "NVIDIA Blackwell GB200 deployment", "AWS Bedrock Trainium update", "Azure AI Foundry announcement").
2. Parse the search results into verified items adhering strictly to the `MarketItem` schema:
   - `domain`: One of "foundation_models", "agents_frameworks", or "cloud_ai_ml".
   - `entity`: Name of provider, lab, or framework (e.g. "Google DeepMind", "Anthropic", "Meta AI", "OpenAI").
   - `headline`: Clear, factual headline specifying the technical development.
   - `summary`: Dense 1-2 sentence description of architectural significance, benchmarks, or capability gains.
   - `source_url`: Real canonical primary citation URL discovered in search results (e.g. blog.google, openai.com, ai.meta.com).
   - `date`: YYYY-MM-DD date of the announcement within the trailing 72-hour window.
   - `verified`: True.
3. MUST invoke `harvest_all_market_news(scanned_items=[...])` passing the list of parsed item dictionaries.
   DO NOT call `harvest_all_market_news()` with zero arguments or empty lists.
4. If no verifiable announcements are discovered in a particular domain for the trailing 72 hours, do not invent items. Omit empty domains rather than fabricating news.
"""

market_news_agent = Agent(
    name="market_news_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=MARKET_NEWS_INSTRUCTION,
    tools=[
        google_search,
        harvest_all_market_news,
    ],
    output_key="market_news_data",
)


def run_market_news_agent(
    lookback_hours: int = 72,
    allow_mock_fallback: bool = False,
    session_service: Any | None = None,
) -> dict[str, Any]:
    """Executes market_news_agent with live Google Search and records results into session state.

    Args:
        lookback_hours: Enforced lookback window duration in hours (default 72).
        allow_mock_fallback: If True, falls back to test baseline fixtures if agent execution fails
            (useful for offline testing or sandboxed unit tests). Defaults to False.
        session_service: Optional ADK SessionService instance.

    Returns:
        Serialized MarketHarvestPayload dictionary containing harvested market intelligence.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    sydney_now = datetime.now(SYDNEY_TZ)
    svc = session_service or InMemorySessionService()
    session = svc.create_session_sync(
        user_id="daily_brief_runner", app_name="daily_brief"
    )
    runner = Runner(
        agent=market_news_agent, session_service=svc, app_name="daily_brief"
    )

    prompt = (
        f"Today is {sydney_now.strftime('%A, %B %d, %Y')} in Sydney. "
        f"Search Google for recent external frontier AI developments, model releases, agent frameworks, "
        f"and cloud AI/ML infrastructure updates over the trailing {lookback_hours} hours. "
        "Extract verified technical developments and invoke harvest_all_market_news(scanned_items=[...]) "
        "with the structured items."
    )
    message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

    try:
        for _ in runner.run(
            new_message=message,
            user_id="daily_brief_runner",
            session_id=session.id,
        ):
            pass

        session_after = svc.get_session_sync(
            session_id=session.id,
            user_id="daily_brief_runner",
            app_name="daily_brief",
        )
        harvest_data = session_after.state.get("market_news_data")
        if isinstance(harvest_data, dict) and "announcements" in harvest_data:
            return harvest_data
        elif isinstance(harvest_data, str):
            try:
                parsed = json.loads(harvest_data)
                if isinstance(parsed, dict) and "announcements" in parsed:
                    return parsed
            except Exception:
                pass
    except Exception as exc:
        if not allow_mock_fallback:
            return {
                "error": f"Failed to run live market news agent: {exc!s}",
                "announcements": [],
                "harvest_timestamp": sydney_now.isoformat(),
                "lookback_hours": lookback_hours,
            }

    if allow_mock_fallback:
        return harvest_all_market_news(lookback_hours=lookback_hours, mock=True)

    return harvest_all_market_news(lookback_hours=lookback_hours, mock=False)
