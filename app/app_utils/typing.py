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

"""Core Pydantic data schemas and contracts for Daily Brief ADK agents.

These schemas enforce strict JSON schema validation for all sub-agent
state transitions, tool inputs/outputs, and evaluation harnesses in compliance
with Rubric Item 1.3.
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class Feedback(BaseModel):
    """Represents feedback for a conversation."""

    score: int | float
    text: str | None = ""
    log_type: Literal["feedback"] = "feedback"
    service_name: Literal["daily-brief"] = "daily-brief"
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class StructuredToolError(BaseModel):
    """Structured recovery payload returned by tools upon handled failures.

    In compliance with Rubric Item 1.4 (Guided Error Handling), tools return
    recovery instructions allowing the calling LLM agent to self-heal.
    """

    status: Literal["error"] = Field(
        default="error", description="Failure indicator status"
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error identifier (e.g. RATE_LIMIT_EXCEEDED, SPACE_NOT_FOUND)",
    )
    message: str = Field(..., description="Human-readable explanation of the error")
    recovery_instruction: str = Field(
        ...,
        description="Actionable guidance for the agent to recover or adapt its plan",
    )


class CommunicationItem(BaseModel):
    """Represents an individual communication thread from Gmail or Google Chat."""

    source: Literal["gmail", "chat", "calendar"] = Field(
        ..., description="Originating channel"
    )
    thread_id: str = Field(..., description="Unique thread or message identifier")
    sender_name: str = Field(..., description="Display name of the sender")
    sender_email: str = Field(..., description="Email address or user handle of sender")
    timestamp: str = Field(..., description="ISO 8601 formatted message timestamp")
    subject: str = Field(..., description="Thread subject or topic header")
    snippet: str = Field(..., description="Concise preview of message content")
    body: str | None = Field(default=None, description="Cleaned message body content")
    deep_link: str = Field(
        ..., description="Canonical URL to open thread in web or mobile app"
    )
    is_vip: bool = Field(
        default=False, description="Whether the sender is on the VIP stakeholder map"
    )
    vip_category: Literal["leadership", "direct_report", "strategic_partner"] | None = (
        Field(default=None, description="Categorization of the VIP sender")
    )
    requires_action: bool = Field(
        default=False,
        description="Whether this thread contains an explicit blocker or ask",
    )
    action_summary: str | None = Field(
        default=None, description="Extracted actionable request or decision needed"
    )
    aging_days: int = Field(
        default=0,
        description="Number of days the thread has remained unread/unanswered",
    )


class InternalHarvestPayload(BaseModel):
    """Payload produced by the internal_comms_agent covering the past 24h window."""

    harvest_timestamp: str = Field(
        ..., description="Timestamp when the harvest was conducted in Sydney time"
    )
    lookback_hours: int = Field(
        default=24, description="Enforced lookback window duration in hours"
    )
    leadership_threads: list[CommunicationItem] = Field(
        default_factory=list,
        description="Triaged unread threads from upward & regional leadership",
    )
    direct_report_threads: list[CommunicationItem] = Field(
        default_factory=list,
        description="Escalations, approvals, and asks from the 15 direct reports",
    )
    chat_space_threads: list[CommunicationItem] = Field(
        default_factory=list,
        description="High-priority announcements or discussions from target team spaces",
    )
    calendar_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological agenda of today's calendar commitments with prep links",
    )
    hot_list_matches: dict[str, list[CommunicationItem]] = Field(
        default_factory=dict,
        description="Unread messages over trailing 3 days matching active Hot List themes",
    )


class MarketItem(BaseModel):
    """Represents a verified external generative AI or cloud market movement."""

    domain: Literal["foundation_models", "agents_frameworks", "cloud_ai_ml"] = Field(
        ..., description="Domain category of the industry update"
    )
    entity: str = Field(
        ...,
        description="Organization, lab, or model name (e.g. Anthropic, OpenAI, GCP)",
    )
    headline: str = Field(
        ..., description="Punchy, factual summary of the release or update"
    )
    summary: str = Field(..., description="Operational and commercial significance")
    source_url: str = Field(..., description="Canonical source citation URL")
    date: str = Field(..., description="Announcement date within the 72-hour window")
    verified: bool = Field(
        default=True,
        description="Whether the update has been confirmed by a primary source",
    )


class MarketHarvestPayload(BaseModel):
    """Payload produced by the market_news_agent covering the trailing 72-hour window."""

    harvest_timestamp: str = Field(
        ..., description="Timestamp when the market scan was conducted"
    )
    lookback_hours: int = Field(
        default=72, description="Enforced lookback window duration in hours"
    )
    announcements: list[MarketItem] = Field(
        default_factory=list,
        description="Verified industry movements across foundation models, agents, and cloud AI",
    )


class DraftBriefingPayload(BaseModel):
    """Working draft briefing synthesized by briefing_writer_agent."""

    executive_orientation: str = Field(
        ..., description="6 plain text sentences summarizing critical overnight comms"
    )
    core_updates_html: str = Field(
        ..., description="HTML bulleted updates for leadership and critical projects"
    )
    hot_list_html: str = Field(
        ...,
        description="HTML section for active Hot List themes with 3-day unread check",
    )
    market_updates_html: str = Field(
        ..., description="HTML section for external AI market announcements"
    )
    calendar_agenda_html: str = Field(
        ...,
        description="HTML section for today's agenda starting with 'Looking at your day ahead...'",
    )
    raw_html: str = Field(
        ..., description="Assembled complete HTML briefing prior to editorial review"
    )
    generated_at: str = Field(..., description="Generation timestamp")


class FinalBriefingPayload(BaseModel):
    """Final, approved briefing verified by editor_reviewer_agent."""

    final_html: str = Field(..., description="Polished, email-ready HTML briefing text")
    is_approved: bool = Field(
        ..., description="True if the review loop emitted 'approve'"
    )
    editor_review_notes: str | None = Field(
        default=None, description="Critique notes or confirmation summary"
    )
    approved_at: str | None = Field(default=None, description="Approval timestamp")


class PodcastScriptPayload(BaseModel):
    """Acoustically adapted spoken script produced by podcast_script_agent."""

    spoken_script: str = Field(
        ...,
        description="Natural conversational spoken text free of markdown or URL syntax",
    )
    word_count: int = Field(..., description="Total word count of the spoken script")
    estimated_duration_seconds: int = Field(
        ..., description="Projected audio duration at 1.05x speaking pace"
    )
    generated_at: str = Field(..., description="Script generation timestamp")


class PodcastAssetPayload(BaseModel):
    """Audio file artifact produced and uploaded by podcast_creator_agent."""

    local_file_path: str = Field(
        ..., description="Local filesystem path to generated MP3 file"
    )
    drive_file_id: str = Field(
        ..., description="Google Drive file ID under /agents/daily-briefing"
    )
    drive_web_url: str = Field(
        ..., description="Permanent shareable web URL for the MP3 asset"
    )
    duration_seconds: int = Field(..., description="Actual audio duration in seconds")
    created_at: str = Field(..., description="Upload timestamp")
