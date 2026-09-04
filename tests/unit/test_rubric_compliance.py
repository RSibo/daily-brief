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
from app.app_utils.telemetry import JsonFormatter
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


def test_rubric_1_1_tool_docstrings_in_root_agent():
    """Rubric 1.1: Verifies all tools in root_agent have comprehensive Google docstrings."""
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
    """Rubric 1.2: Tool names must be highly specific and clear, avoiding generic names."""
    from app.agent import root_agent

    banned_generic = {"run", "get_data", "search", "update", "execute", "process"}
    for tool in root_agent.tools:
        name = getattr(tool, "__name__", str(tool))
        assert name not in banned_generic, f"Tool name '{name}' is too generic."
        assert "_" in name, (
            f"Tool name '{name}' should be a descriptive verb-noun pair."
        )


def test_rubric_1_3_explicit_pydantic_schemas():
    """Rubric 1.3: Code utilizes strict Pydantic schemas with Field descriptions."""
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


def test_rubric_4_1_structured_json_logging():
    """Rubric 4.1: Logger emits machine-readable JSON with required metadata."""
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


def test_rubric_4_4_pii_redaction_pipeline():
    """Rubric 4.4: Active scrubbing mechanisms to redact sensitive data."""
    fake_key = "AIza" + "SyD1234567890abcdefghijklmnopqrstu"
    sample = f"Connecting to Google Cloud using {fake_key}"
    scrubbed = redact_pii_text(sample)
    assert "AIzaSy" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed


def test_rubric_5_3_secure_secret_management():
    """Rubric 5.3: No hardcoded API keys or private keys in tracked codebase."""
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
