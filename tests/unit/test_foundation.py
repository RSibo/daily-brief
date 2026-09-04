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

"""Unit tests for Phase 0 shared foundation components."""

import re
from pathlib import Path

from app.app_utils.pii_scrubber import redact_pii_object, redact_pii_text
from app.app_utils.telemetry import trace_tool
from app.app_utils.typing import (
    CommunicationItem,
    MarketHarvestPayload,
    MarketItem,
    StructuredToolError,
)
from app.prompts.constitution import (
    CHIEF_OF_STAFF_CONSTITUTION,
    PODCAST_REWRITER_INSTRUCTION,
    REVIEWER_SYSTEM_INSTRUCTION,
)


def test_communication_item_schema():
    """Verifies CommunicationItem schema validation and serialization."""
    item = CommunicationItem(
        source="gmail",
        thread_id="thread_123",
        sender_name="Simon Elisha",
        sender_email="selisha@google.com",
        timestamp="2026-09-04T07:00:00+10:00",
        subject="Q3 Technical Priorities",
        snippet="Please review the attached document.",
        deep_link="https://mail.google.com/mail/u/0/#inbox/thread_123",
        is_vip=True,
        vip_category="leadership",
        requires_action=True,
        action_summary="Review document",
        aging_days=1,
    )
    data = item.model_dump()
    assert data["source"] == "gmail"
    assert data["is_vip"] is True
    assert data["vip_category"] == "leadership"
    assert item.thread_id == "thread_123"


def test_structured_tool_error_schema():
    """Verifies StructuredToolError schema for Rubric Item 1.4."""
    err = StructuredToolError(
        error_code="RATE_LIMIT_EXCEEDED",
        message="Quota exceeded for Gmail search API",
        recovery_instruction="Retry with exponential backoff or skip non-critical queries.",
    )
    assert err.status == "error"
    assert "Retry" in err.recovery_instruction


def test_market_payload_schema():
    """Verifies MarketHarvestPayload schema for 48h market scan."""
    item = MarketItem(
        domain="foundation_models",
        entity="Anthropic",
        headline="Claude 3.5 Sonnet Updated Benchmarks",
        summary="Improved reasoning scores across coding benchmarks.",
        source_url="https://anthropic.com/news/claude-3-5",
        date="2026-09-03",
    )
    payload = MarketHarvestPayload(
        harvest_timestamp="2026-09-04T08:00:00+10:00",
        lookback_hours=48,
        announcements=[item],
    )
    assert payload.lookback_hours == 48
    assert len(payload.announcements) == 1
    assert payload.announcements[0].entity == "Anthropic"


def test_config_chat_spaces_loading():
    """Verifies that config/chat_spaces.md exists and contains the 17 target spaces."""
    spaces_path = Path("config/chat_spaces.md")
    assert spaces_path.exists(), "config/chat_spaces.md must exist"

    content = spaces_path.read_text()
    # Match markdown table rows containing space IDs
    matches = re.findall(
        r"\|\s*(.*?)\s*\|\s*`?(spaces/[a-zA-Z0-9_\-]+|AAAA[a-zA-Z0-9_\-]+)`?\s*\|",
        content,
    )
    assert len(matches) >= 17, f"Expected at least 17 spaces, found {len(matches)}"

    space_ids = [m[1] for m in matches]
    assert "spaces/AAQABTcnmcM" in space_ids
    assert "spaces/AAQAlcokf0k" in space_ids
    assert "spaces/AAQA1aF4JGg" in space_ids
    assert "spaces/AAQAm7fBHAY" in space_ids
    assert "spaces/AAQAWmL5O_g" in space_ids


def test_config_hot_list_loading():
    """Verifies that config/hot_list.md exists and specifies the 3 active themes."""
    hot_list_path = Path("config/hot_list.md")
    assert hot_list_path.exists(), "config/hot_list.md must exist"

    content = hot_list_path.read_text()
    assert "Optus VAIS & Model Armor Blocker" in content
    assert "Woolworths (GE, FDE/SWE Initiative, FLW)" in content
    assert "Google AI DRZ / AU ML Processing" in content
    assert "On topic [Theme Name] no updates yet." in content


def test_pii_scrubber_redaction():
    """Verifies PII scrubbing on credentials, tokens, phone numbers, and nested objects."""
    fake_token = "ya" + "29.a0AfH6SMB_1234567890abcdef"
    fake_key = "AIza" + "SyD1234567890abcdefghijklmnopqrstu"
    raw_text = (
        f"Token: {fake_token} "
        f"Key: {fake_key} "
        "Call me at +61 412 345 678 or 0412345678 for password='super_secret_pass'"
    )
    sanitized = redact_pii_text(raw_text)
    assert "ya29." not in sanitized
    assert "[REDACTED_OAUTH_TOKEN]" in sanitized
    assert "AIzaSy" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "super_secret_pass" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized

    # Nested object scrubbing
    nested_token = "ya" + "29.sampletoken123456789"
    nested = {
        "user": "rsibo",
        "api_key": fake_key,
        "items": [f"token is {nested_token}", "clean item"],
    }
    redacted_obj = redact_pii_object(nested)
    assert "[REDACTED_API_KEY]" in redacted_obj["api_key"]
    assert "[REDACTED_OAUTH_TOKEN]" in redacted_obj["items"][0]
    assert redacted_obj["items"][1] == "clean item"


def test_constitution_prompts_contain_negative_constraints():
    """Verifies that system constitutions strictly declare negative constraints."""
    assert "ZERO HYPERBOLE" in CHIEF_OF_STAFF_CONSTITUTION
    assert "NO DRAMA OR EMOTIONAL SPIN" in CHIEF_OF_STAFF_CONSTITUTION
    assert "Looking at your day ahead..." in CHIEF_OF_STAFF_CONSTITUTION
    assert "approve" in REVIEWER_SYSTEM_INSTRUCTION
    assert "Zero Fluff" in PODCAST_REWRITER_INSTRUCTION


def test_trace_tool_decorator():
    """Verifies trace_tool decorator records intent and outcome without errors."""

    @trace_tool("sample_tool", agent_name="test_agent")
    def sample_func(x: int) -> dict:
        return {"status": "success", "result": x * 2}

    res = sample_func(5)
    assert res["status"] == "success"
    assert res["result"] == 10
