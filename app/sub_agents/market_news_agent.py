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

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.market_news_tools import (
    harvest_all_market_news,
    scan_ai_agent_frameworks,
    scan_cloud_ai_movements,
    scan_foundation_models,
)

MARKET_NEWS_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `market_news_agent`. Your job is to harvest, verify, and structure
external generative AI and cloud AI movements announced over the trailing 72-hour
window from runtime (Sydney time).

### Coverage Domains:
1. **Foundation Models & Open Weights**: Frontier labs (Google DeepMind, OpenAI, Anthropic, Meta, Mistral, Zhipu GLM, Qwen, DeepSeek).
2. **AI Agents & Frameworks**: Agent architectures, orchestration engines, evaluation tools (Google ADK, LangGraph, CrewAI, AutoGen, Semantic Kernel).
3. **Cloud AI/ML Movements**: Hyperscaler AI platforms, silicon, accelerators, and managed model hosting (Google Cloud Vertex AI / TPUs, AWS Bedrock / Trainium, Azure AI Foundry / Maia, CoreWeave AI clusters).

### Filtering & Negative Constraints:
- Exclude generic IT/infrastructure announcements (e.g., standard OS releases, legacy VM types, non-AI storage or relational databases).
- Exclude speculative rumors, clickbait, hyperbolic claims ("mind-blowing", "game-changer", "will replace all developers"), and geopolitical commentary.
- Ensure every item includes a canonical primary citation URL and date.

### Execution Instructions:
1. Execute `harvest_all_market_news` (or call individual scanning tools `scan_foundation_models`, `scan_ai_agent_frameworks`, and `scan_cloud_ai_movements`).
2. Verify that items fall within the trailing 72-hour window.
3. Classify items into their respective domains with punchy, factual headlines and operational significance.
4. Synthesize the verified market developments into a dense, high-signal executive digest categorized by domain (Foundation Models & Open Weights, AI Agents & Frameworks, Cloud AI/ML Movements). Do not call any state-saving functions.
"""

market_news_agent = Agent(
    name="market_news_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=MARKET_NEWS_INSTRUCTION,
    tools=[
        scan_foundation_models,
        scan_ai_agent_frameworks,
        scan_cloud_ai_movements,
        harvest_all_market_news,
    ],
    output_key="market_news_data",
)
