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

"""Observability, Structured JSON Logging, and OpenTelemetry Tracing.

Implements Rubric Category 4 (Observability & Tracing):
- 4.1 Structured JSON Logging: Emits machine-readable JSON logs with rich context.
- 4.2 Intent vs. Outcome Capture: Paired lifecycle events for pre-action intent and post-action outcome.
- 4.3 Distributed Tracing: OpenTelemetry span instrumentation across multi-agent execution.
"""

import functools
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from typing import Any

# Optional OpenTelemetry integration
try:
    from opentelemetry import trace

    tracer = trace.get_tracer("daily-brief")
except ImportError:
    tracer = None


class JsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "agent_name"):
            log_record["agent_name"] = record.agent_name
        if hasattr(record, "event_type"):
            log_record["event_type"] = record.event_type
        if hasattr(record, "tool_name"):
            log_record["tool_name"] = record.tool_name
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_record["data"] = record.extra_data
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def get_logger(name: str = "daily-brief") -> logging.Logger:
    """Returns a configured logger that writes structured JSON logs."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger("daily-brief")


def log_tool_intent(
    tool_name: str, args: dict[str, Any], agent_name: str = "agent"
) -> None:
    """Logs the agent's intended action prior to execution (Rubric Item 4.2)."""
    extra = {
        "agent_name": agent_name,
        "event_type": "TOOL_INTENT",
        "tool_name": tool_name,
        "extra_data": {"input_args": args},
    }
    logger.info(
        f"Agent '{agent_name}' preparing to invoke tool '{tool_name}'", extra=extra
    )


def log_tool_outcome(
    tool_name: str,
    status: str,
    outcome_summary: dict[str, Any],
    duration_ms: float,
    agent_name: str = "agent",
) -> None:
    """Logs the actual outcome and latency after tool execution (Rubric Item 4.2)."""
    extra = {
        "agent_name": agent_name,
        "event_type": "TOOL_OUTCOME",
        "tool_name": tool_name,
        "duration_ms": duration_ms,
        "extra_data": {"status": status, "outcome": outcome_summary},
    }
    logger.info(
        f"Tool '{tool_name}' executed in {duration_ms:.1f}ms with status '{status}'",
        extra=extra,
    )


def trace_tool(tool_name: str, agent_name: str = "agent") -> Callable:
    """Decorator capturing OpenTelemetry span and logging intent vs. outcome."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            sanitized_kwargs = {k: v for k, v in kwargs.items() if k != "tool_context"}
            log_tool_intent(tool_name, sanitized_kwargs, agent_name=agent_name)
            start_time = time.perf_counter()

            if tracer:
                with tracer.start_as_current_span(f"tool:{tool_name}") as span:
                    span.set_attribute("tool.name", tool_name)
                    span.set_attribute("agent.name", agent_name)
                    try:
                        result = func(*args, **kwargs)
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        outcome = (
                            {"status": result.get("status", "success")}
                            if isinstance(result, dict)
                            else {"status": "success"}
                        )
                        log_tool_outcome(
                            tool_name, "success", outcome, duration_ms, agent_name
                        )
                        span.set_attribute("tool.status", "success")
                        return result
                    except Exception as exc:
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        log_tool_outcome(
                            tool_name,
                            "error",
                            {"error_type": type(exc).__name__, "error_msg": str(exc)},
                            duration_ms,
                            agent_name,
                        )
                        span.set_attribute("tool.status", "error")
                        span.record_exception(exc)
                        raise
            else:
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    outcome = (
                        {"status": result.get("status", "success")}
                        if isinstance(result, dict)
                        else {"status": "success"}
                    )
                    log_tool_outcome(
                        tool_name, "success", outcome, duration_ms, agent_name
                    )
                    return result
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    log_tool_outcome(
                        tool_name,
                        "error",
                        {"error_type": type(exc).__name__, "error_msg": str(exc)},
                        duration_ms,
                        agent_name,
                    )
                    raise

        return wrapper

    return decorator


def setup_telemetry() -> str | None:
    """Configure OpenTelemetry and GenAI telemetry with GCS upload."""
    bucket = os.environ.get("LOGS_BUCKET_NAME")
    capture_content = os.environ.get(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
    )
    if bucket and capture_content != "false":
        logging.info(
            "Prompt-response logging enabled - mode: NO_CONTENT (metadata only)"
        )
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "NO_CONTENT"
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "jsonl")
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK", "upload")
        os.environ.setdefault(
            "OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental"
        )
        commit_sha = os.environ.get("COMMIT_SHA", "dev")
        os.environ.setdefault(
            "OTEL_RESOURCE_ATTRIBUTES",
            f"service.namespace=daily-brief,service.version={commit_sha}",
        )
        path = os.environ.get("GENAI_TELEMETRY_PATH", "completions")
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
            f"gs://{bucket}/{path}",
        )
    else:
        logging.info(
            "Prompt-response logging disabled (set LOGS_BUCKET_NAME to enable)"
        )
    return bucket
