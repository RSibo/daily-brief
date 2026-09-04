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

"""Unit tests for Phase 2: External Market News Harvest Agent and Tools."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.app_utils.typing import MarketHarvestPayload, MarketItem
from app.sub_agents.market_news_agent import market_news_agent
from app.tools.market_news_tools import (
    harvest_all_market_news,
    is_clickbait_or_noise,
    is_within_lookback_window,
    scan_ai_agent_frameworks,
    scan_cloud_ai_movements,
    scan_foundation_models,
)

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def test_clickbait_and_noise_filtering():
    """Verifies that sensational clickbait and non-AI infra noise are flagged."""
    clickbait_samples = [
        "This new model is a total GAME-CHANGER and shocking!",
        "OpenAI is dead: This leak will replace all developers tomorrow",
        "Insane mind-blowing breakthrough destroys competition",
    ]
    for sample in clickbait_samples:
        assert is_clickbait_or_noise(sample) is True, (
            f"Failed to filter clickbait: {sample}"
        )

    infra_samples = [
        "Debian 12 point release notes and legacy VM retirement schedule",
        "General storage pricing update for standard VPC peering buckets",
        "MySQL 8.0 maintenance and relational database minor version patch",
    ]
    for sample in infra_samples:
        assert is_clickbait_or_noise(sample) is True, (
            f"Failed to filter non-AI infra: {sample}"
        )

    clean_samples = [
        "Gemini 2.5 Flash updates with expanded context processing and code execution",
        "Claude 3.7 Sonnet hybrid reasoning architecture released",
        "Vertex AI Model Armor adds automated prompt injection shields",
    ]
    for sample in clean_samples:
        assert is_clickbait_or_noise(sample) is False, (
            f"Erroneously flagged clean sample: {sample}"
        )


def test_lookback_window_enforcement():
    """Verifies strict adherence to the trailing 72-hour window."""
    now = datetime.now(SYDNEY_TZ)

    # 12 hours ago -> should pass
    recent_date = (now - timedelta(hours=12)).strftime("%Y-%m-%d")
    assert (
        is_within_lookback_window(recent_date, lookback_hours=72, reference_time=now)
        is True
    )

    # 60 hours ago -> should pass under 72h window
    valid_date = (now - timedelta(hours=60)).strftime("%Y-%m-%d")
    assert (
        is_within_lookback_window(valid_date, lookback_hours=72, reference_time=now)
        is True
    )

    # 5 days ago -> should fail
    old_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
    assert (
        is_within_lookback_window(old_date, lookback_hours=72, reference_time=now)
        is False
    )


def test_scan_foundation_models():
    """Verifies that foundation model scanner returns valid MarketItems with URLs."""
    items = scan_foundation_models(lookback_hours=72)
    assert len(items) > 0

    for item_dict in items:
        item = MarketItem(**item_dict)
        assert item.domain == "foundation_models"
        assert item.source_url.startswith("http")
        assert len(item.headline) > 10
        assert len(item.entity) > 0
        assert item.verified is True


def test_scan_ai_agent_frameworks():
    """Verifies that AI agent framework scanner returns valid items."""
    items = scan_ai_agent_frameworks(lookback_hours=72)
    assert len(items) > 0

    for item_dict in items:
        item = MarketItem(**item_dict)
        assert item.domain == "agents_frameworks"
        assert item.source_url.startswith("http")
        assert len(item.summary) > 10


def test_scan_cloud_ai_movements():
    """Verifies that cloud AI scanner focuses exclusively on AI/ML platforms and silicon."""
    items = scan_cloud_ai_movements(lookback_hours=72)
    assert len(items) > 0

    for item_dict in items:
        item = MarketItem(**item_dict)
        assert item.domain == "cloud_ai_ml"
        assert item.source_url.startswith("http")


def test_harvest_all_market_news_payload_schema():
    """Verifies composite harvest returns a valid MarketHarvestPayload."""
    payload_dict = harvest_all_market_news(lookback_hours=72)
    assert "error" not in payload_dict

    payload = MarketHarvestPayload(**payload_dict)
    assert payload.lookback_hours == 72
    assert len(payload.announcements) >= 3

    domains_present = {item.domain for item in payload.announcements}
    assert "foundation_models" in domains_present
    assert "agents_frameworks" in domains_present
    assert "cloud_ai_ml" in domains_present


def test_market_news_agent_definition():
    """Verifies ADK agent configuration for market_news_agent."""
    assert market_news_agent.name == "market_news_agent"
    assert market_news_agent.output_key == "market_news_data"
    assert len(market_news_agent.tools) == 4
    tool_names = [getattr(t, "__name__", str(t)) for t in market_news_agent.tools]
    assert "harvest_all_market_news" in tool_names
    assert "scan_foundation_models" in tool_names
    assert "scan_ai_agent_frameworks" in tool_names
    assert "scan_cloud_ai_movements" in tool_names
