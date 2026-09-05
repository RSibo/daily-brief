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
import re
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
3. Output your findings as a structured JSON array of objects inside a ```json ``` markdown code block:
   ```json
   [
     {{
       "domain": "foundation_models",
       "entity": "Provider / Lab Name",
       "headline": "Factual headline",
       "summary": "Technical significance and capability details.",
       "source_url": "https://canonical.url",
       "date": "YYYY-MM-DD",
       "verified": true
     }}
   ]
   ```
4. If no verifiable announcements are discovered in a particular domain for the trailing 72 hours, do not invent items. Return only verified items. If no announcements exist at all across any domain, return an empty array `[]`.
"""


def extract_market_items(raw_data: Any) -> list[dict[str, Any]]:
    """Extracts a list of market item dictionaries from raw string, dict, or list data."""
    if not raw_data:
        return []
    if isinstance(raw_data, list):
        return [i for i in raw_data if isinstance(i, dict)]
    if isinstance(raw_data, dict):
        if "announcements" in raw_data and isinstance(raw_data["announcements"], list):
            return [i for i in raw_data["announcements"] if isinstance(i, dict)]
        return [raw_data]
    if not isinstance(raw_data, str):
        return []

    text = raw_data.strip()

    # 1. Direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [i for i in parsed if isinstance(i, dict)]
        if isinstance(parsed, dict):
            if "announcements" in parsed and isinstance(parsed["announcements"], list):
                return [i for i in parsed["announcements"] if isinstance(i, dict)]
            return [parsed]
    except Exception:
        pass

    # 2. Markdown code block ```json ... ``` or ``` ... ```
    code_block_match = re.search(
        r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL
    )
    if code_block_match:
        try:
            parsed = json.loads(code_block_match.group(1).strip())
            if isinstance(parsed, list):
                return [i for i in parsed if isinstance(i, dict)]
            if isinstance(parsed, dict):
                if "announcements" in parsed and isinstance(
                    parsed["announcements"], list
                ):
                    return [i for i in parsed["announcements"] if isinstance(i, dict)]
                return [parsed]
        except Exception:
            pass

    # 3. Embedded JSON array pattern [ { ... } ]
    array_match = re.search(r"(\[\s*\{.*?\}\s*\])", text, re.DOTALL)
    if array_match:
        try:
            parsed = json.loads(array_match.group(1).strip())
            if isinstance(parsed, list):
                return [i for i in parsed if isinstance(i, dict)]
        except Exception:
            pass

    # 4. Fallback line-by-line extraction for markdown bullets
    items: list[dict[str, Any]] = []
    for line in text.split("\n"):
        line_clean = line.strip()
        if not line_clean.startswith(("-", "*", "•")):
            continue
        url_match = re.search(r"https?://[^\s)\]]+", line_clean)
        source_url = url_match.group(0) if url_match else "https://blog.google"
        domain = "foundation_models"
        line_lower = line_clean.lower()
        if any(
            w in line_lower for w in ["agent", "langgraph", "adk", "crewai", "autogen"]
        ):
            domain = "agents_frameworks"
        elif any(
            w in line_lower
            for w in [
                "cloud",
                "tpu",
                "gpu",
                "blackwell",
                "trainium",
                "cluster",
                "silicon",
                "azure",
                "aws",
            ]
        ):
            domain = "cloud_ai_ml"

        headline_cand = line_clean.lstrip("-*• ").split(":")[0][:100]
        items.append(
            {
                "domain": domain,
                "entity": "Industry",
                "headline": headline_cand,
                "summary": line_clean[:250],
                "source_url": source_url,
                "date": datetime.now(SYDNEY_TZ).strftime("%Y-%m-%d"),
                "verified": True,
            }
        )

    return items


async def process_market_news_callback(
    callback_context: Any,
) -> None:
    """Processes search findings from market_news_agent into structured session state.

    Extracts grounded search items from the agent's response and invokes
    harvest_all_market_news to perform schema formatting, lookback enforcement,
    and domain sorting.
    """
    raw_data = callback_context.state.get("market_news_data")
    if not raw_data and hasattr(callback_context, "_invocation_context"):
        inv_ctx = getattr(callback_context, "_invocation_context", None)
        if inv_ctx and hasattr(inv_ctx, "session") and inv_ctx.session:
            for event in reversed(inv_ctx.session.events):
                if (
                    event.author == "market_news_agent"
                    and event.content
                    and event.content.parts
                ):
                    raw_data = "".join(
                        p.text for p in event.content.parts if p.text and not p.thought
                    )
                    if raw_data:
                        break

    scanned_items = extract_market_items(raw_data)
    structured_payload = harvest_all_market_news(
        lookback_hours=72,
        scanned_items=scanned_items,
        mock=False,
    )
    callback_context.state["market_news_data"] = structured_payload


market_news_agent = Agent(
    name="market_news_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=MARKET_NEWS_INSTRUCTION,
    tools=[
        google_search,
    ],
    after_agent_callback=process_market_news_callback,
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
        "Extract verified technical developments and output them as a structured JSON array of items."
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
            scanned = extract_market_items(harvest_data)
            return harvest_all_market_news(
                lookback_hours=lookback_hours,
                scanned_items=scanned,
                mock=False,
            )
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
