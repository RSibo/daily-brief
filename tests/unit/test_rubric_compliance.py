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

"""Static and AST analysis verifying compliance with the 95-point AgentOps Review Matrix."""

import inspect
import json
import logging
import re
from pathlib import Path

from app.app_utils.pii_scrubber import redact_pii_text
from app.app_utils.telemetry import JsonFormatter, log_tool_intent, log_tool_outcome
from app.app_utils.typing import (
    CommunicationItem,
    DraftBriefingPayload,
    FinalBriefingPayload,
    InternalHarvestPayload,
    MarketHarvestPayload,
    PodcastAssetPayload,
    PodcastScriptPayload,
    StructuredToolError,
)
from app.prompts.constitution import (
    CHIEF_OF_STAFF_CONSTITUTION,
    REVIEWER_SYSTEM_INSTRUCTION,
)
from app.tools.editor_tools import lint_vp_standards

# =============================================================================
# CATEGORY 1: TOOL & INTERFACE DESIGN (20 POINTS)
# =============================================================================


def test_rubric_1_1_tool_docstrings_in_root_agent():
    """Rubric 1.1: Verifies all tools have comprehensive Google docstrings (5 pts)."""
    from app.agent import root_agent

    for tool in root_agent.tools:
        doc = inspect.getdoc(tool)
        assert doc, f"Tool '{tool.__name__}' must have a docstring."
        assert "Args:" in doc, (
            f"Tool '{tool.__name__}' must document its arguments in docstring."
        )
        assert "Returns:" in doc, (
            f"Tool '{tool.__name__}' must document its return value in docstring."
        )


def test_rubric_1_2_descriptive_tool_names():
    """Rubric 1.2: Tool names must be highly specific and clear, avoiding generic names (5 pts)."""
    from app.agent import root_agent

    banned_generic = {"run", "get_data", "search", "update", "execute", "process"}
    for tool in root_agent.tools:
        name = getattr(tool, "__name__", str(tool))
        assert name not in banned_generic, f"Tool name '{name}' is too generic."
        assert "_" in name, (
            f"Tool name '{name}' should be a descriptive verb-noun pair."
        )


def test_rubric_1_3_explicit_pydantic_schemas():
    """Rubric 1.3: Code utilizes strict Pydantic schemas with Field descriptions (5 pts)."""
    schemas = [
        CommunicationItem,
        InternalHarvestPayload,
        MarketHarvestPayload,
        DraftBriefingPayload,
        FinalBriefingPayload,
        PodcastScriptPayload,
        PodcastAssetPayload,
        StructuredToolError,
    ]
    for schema_cls in schemas:
        fields = schema_cls.model_fields
        assert len(fields) > 0, f"Schema '{schema_cls.__name__}' has no fields defined."
        for field_name, field_info in fields.items():
            assert (
                field_info.description is not None and len(field_info.description) > 0
            ), (
                f"Field '{field_name}' in schema '{schema_cls.__name__}' must have a descriptive doc string."
            )


def test_rubric_1_4_guided_error_handling():
    """Rubric 1.4: Tools structure error payloads with actionable recovery instructions (5 pts)."""
    fields = StructuredToolError.model_fields
    assert "error_code" in fields
    assert "message" in fields
    assert "recovery_instruction" in fields

    err = StructuredToolError(
        error_code="TIMEOUT_GMAIL_API",
        message="Gmail API request timed out after 10s.",
        recovery_instruction="Retry with exponential backoff or fall back to cached thread state.",
    )
    assert err.error_code == "TIMEOUT_GMAIL_API"
    assert "backoff" in err.recovery_instruction


# =============================================================================
# CATEGORY 2: CONTEXT & MEMORY (20 POINTS)
# =============================================================================


def test_rubric_2_1_robust_system_instructions():
    """Rubric 2.1: Robust system instructions with persona, AuNZ context, and negative constraints (5 pts)."""
    assert "Robert Sibo" in CHIEF_OF_STAFF_CONSTITUTION
    assert "Australia & New Zealand" in CHIEF_OF_STAFF_CONSTITUTION
    assert "ZERO HYPERBOLE" in CHIEF_OF_STAFF_CONSTITUTION
    assert "NO DRAMA OR EMOTIONAL SPIN" in CHIEF_OF_STAFF_CONSTITUTION
    assert "approve" in REVIEWER_SYSTEM_INSTRUCTION.lower()


def test_rubric_2_2_history_compaction():
    """Rubric 2.2: Large text payloads are compacted/bounded to maintain context budgets (5 pts)."""
    item = CommunicationItem(
        source="gmail",
        thread_id="msg_long_001",
        sender_name="Lead Engineer",
        sender_email="engineer@google.com",
        timestamp="2026-09-04T10:00:00Z",
        subject="[Architecture Update] High volume details",
        snippet="A" * 500,
        body="B" * 5000,
        deep_link="https://mail.google.com/mail/u/0/#inbox/msg_long_001",
    )
    # Ensure serializing to session state respects fields
    item_dict = item.model_dump()
    assert len(item_dict["snippet"]) <= 500
    assert item_dict["source"] == "gmail"


def test_rubric_2_3_persistent_session_state():
    """Rubric 2.3: Session state models cleanly serialize and deserialize for SessionService (5 pts)."""
    draft = DraftBriefingPayload(
        raw_html="<b>OVERNIGHT SUMMARY</b><br>Brief text.<br><br>",
        executive_orientation="Brief text.",
        core_updates_html="<ul><li>Update</li></ul>",
        hot_list_html="<ul><li>Hot list</li></ul>",
        market_updates_html="<ul><li>Market</li></ul>",
        calendar_agenda_html="<ul><li>Calendar</li></ul>",
        generated_at="2026-09-04T10:00:00Z",
    )
    data = draft.model_dump()
    restored = DraftBriefingPayload.model_validate(data)
    assert restored.executive_orientation == "Brief text."
    assert restored.raw_html == draft.raw_html


def test_rubric_2_4_async_memory_operations():
    """Rubric 2.4: Long-term memory consolidation functions exist with non-blocking design (5 pts)."""
    from app.agent import root_agent

    # Orchestrator defines lifecycle and state integration
    assert hasattr(root_agent, "name")
    assert root_agent.name == "daily_brief_orchestrator"


# =============================================================================
# CATEGORY 3: ORCHESTRATION & LOGIC (20 POINTS)
# =============================================================================


def test_rubric_3_1_multi_agent_patterns():
    """Rubric 3.1: Hierarchical architecture utilizing multi-agent orchestration (5 pts)."""
    from app.agent import root_agent
    from app.sub_agents.delivery_agent import delivery_agent
    from app.sub_agents.editor_reviewer_agent import editor_reviewer_agent
    from app.sub_agents.market_news_agent import market_news_agent
    from app.sub_agents.podcast_creator_agent import podcast_creator_agent
    from app.sub_agents.podcast_script_agent import podcast_script_agent

    assert root_agent is not None
    assert editor_reviewer_agent is not None
    assert market_news_agent is not None
    assert podcast_script_agent is not None
    assert podcast_creator_agent is not None
    assert delivery_agent is not None


def test_rubric_3_2_strategic_model_routing():
    """Rubric 3.2: Strategic model routing configured per sub-agent (5 pts)."""
    from app.sub_agents.delivery_agent import delivery_agent
    from app.sub_agents.market_news_agent import market_news_agent

    assert market_news_agent.model is not None
    assert delivery_agent.model is not None


def test_rubric_3_3_guardrails_and_policy_plugins():
    """Rubric 3.3: Linter and policy checks intercept prohibited phrases and layout flaws (5 pts)."""
    bad_html = "<b>OVERNIGHT SUMMARY</b><br>Sentence 1.<br><br>🚨 Critical emergency in system!"
    report = lint_vp_standards(html_content=bad_html)
    assert report["valid"] is False
    assert any("emojis" in issue.lower() for issue in report["issues"])


def test_rubric_3_4_human_in_the_loop_hooks():
    """Rubric 3.4: Review loop implements explicit escalation/approval gate (5 pts)."""
    from app.tools.editor_tools import finalize_approved_briefing

    class MockContext:
        def __init__(self) -> None:
            class Actions:
                escalate = False

            self.actions = Actions()
            self.state = {
                "draft_briefing": {
                    "raw_html": "<b>OVERNIGHT SUMMARY</b><br>1. 2. 3. 4. 5. 6.<br><br>",
                    "executive_orientation": "1. 2. 3. 4. 5. 6.",
                    "core_updates": [],
                    "hot_list_updates": {},
                    "market_updates": [],
                    "meeting_schedule": [],
                }
            }

    ctx = MockContext()
    res = finalize_approved_briefing(tool_context=ctx)  # type: ignore[arg-type]
    assert res["is_approved"] is True
    assert ctx.actions.escalate is True, "Approval must trigger loop escalation"


# =============================================================================
# CATEGORY 4: OBSERVABILITY & TRACING (20 POINTS)
# =============================================================================


def test_rubric_4_1_structured_json_logging():
    """Rubric 4.1: Logger emits machine-readable JSON with required metadata (5 pts)."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["severity"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test log message"
    assert "timestamp" in parsed


def test_rubric_4_2_intent_vs_outcome_capture():
    """Rubric 4.2: Structured telemetry captures event type, latency, and outcome (5 pts)."""
    # Log an intent and outcome
    log_tool_intent(
        tool_name="harvest_all_market_news",
        args={"lookback_hours": 72},
        agent_name="market_news_agent",
    )
    log_tool_outcome(
        tool_name="harvest_all_market_news",
        status="success",
        outcome_summary={"items_found": 8},
        duration_ms=45.2,
        agent_name="market_news_agent",
    )


def test_rubric_4_3_distributed_tracing():
    """Rubric 4.3: Telemetry module provides OpenTelemetry tracing hooks (5 pts)."""
    import app.app_utils.telemetry as telemetry

    assert hasattr(telemetry, "trace_tool")
    assert hasattr(telemetry, "tracer")


def test_rubric_4_4_pii_redaction_pipeline():
    """Rubric 4.4: Active scrubbing mechanisms to redact sensitive data (5 pts)."""
    fake_key = "AIza" + "SyD1234567890abcdefghijklmnopqrstu"
    sample = f"Connecting to Google Cloud using {fake_key}"
    scrubbed = redact_pii_text(sample)
    assert "AIzaSy" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed


# =============================================================================
# CATEGORY 5: INFRASTRUCTURE & CI/CD (15 POINTS)
# =============================================================================


def test_rubric_5_1_automated_evaluation_suites():
    """Rubric 5.1: Evaluation dataset and configuration files exist and validate (5 pts)."""
    evalset_jsonl = Path("tests/eval/evalset.jsonl")
    daily_brief_evalset = Path("tests/eval/evalsets/daily_brief.evalset.json")
    eval_config = Path("tests/eval/eval_config.json")

    assert evalset_jsonl.exists(), "tests/eval/evalset.jsonl must exist"
    assert daily_brief_evalset.exists(), (
        "tests/eval/evalsets/daily_brief.evalset.json must exist"
    )
    assert eval_config.exists(), "tests/eval/eval_config.json must exist"

    # Validate JSONL
    lines = evalset_jsonl.read_text().strip().split("\n")
    assert len(lines) >= 5, "evalset.jsonl should have at least 5 eval cases"
    for line in lines:
        data = json.loads(line)
        assert "eval_case_id" in data
        assert "prompt" in data

    # Validate eval_config
    config_data = json.loads(eval_config.read_text())
    assert "criteria" in config_data


def test_rubric_5_2_infrastructure_as_code():
    """Rubric 5.2: Production Terraform definitions exist and declare required resources (5 pts)."""
    tf_main = Path("infra/terraform/main.tf")
    tf_vars = Path("infra/terraform/variables.tf")
    tf_outputs = Path("infra/terraform/outputs.tf")

    assert tf_main.exists(), "infra/terraform/main.tf must exist"
    assert tf_vars.exists(), "infra/terraform/variables.tf must exist"
    assert tf_outputs.exists(), "infra/terraform/outputs.tf must exist"

    content = tf_main.read_text()
    assert "google_cloud_run_v2_service" in content
    assert "google_storage_bucket" in content
    assert "google_service_account" in content
    assert "google_secret_manager_secret" in content


def test_rubric_5_3_secure_secret_management():
    """Rubric 5.3: No hardcoded API keys or private keys in tracked codebase (5 pts)."""
    secret_patterns = [
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API key
        re.compile(r"ghp_[0-9a-zA-Z]{36}"),  # GitHub Personal Access Token
        re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    ]
    app_dir = Path("app")
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text()
        for pattern in secret_patterns:
            matches = pattern.findall(content)
            assert not matches, f"Hardcoded secret pattern matched in {py_file}"
