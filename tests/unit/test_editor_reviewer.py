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

"""Unit tests for Phase 4: Chief of Staff Reviewer & Editorial Loop.

Validates:
- VP update standards: tone, zero hyperbole, zero emotional spin.
- Banned phrases ("here is your executive brief", "critical emergency").
- Zero emojis and decorative icons enforcement.
- Structural audits: exactly 6 sentences in overnight summary, unbolded text,
  hot list fallbacks ("On topic [Theme] no updates yet."), and agenda start phrase.
- Link validation: detects empty or placeholder links.
- Evaluator verdicts: 'approve' vs 'revise' with actionable critique.
- FinalBriefingPayload generation and LoopAgent escalation mechanics.
"""

from unittest.mock import MagicMock

from google.adk.agents import LoopAgent

from app.app_utils.typing import FinalBriefingPayload
from app.sub_agents.briefing_writer_agent import briefing_writer_agent
from app.sub_agents.editor_reviewer_agent import editor_reviewer_agent
from app.sub_agents.editorial_loop import editorial_loop
from app.tools.editor_tools import (
    evaluate_briefing_draft,
    finalize_approved_briefing,
    lint_vp_standards,
)

SAMPLE_VALID_BRIEFING = """
<b>OVERNIGHT SUMMARY</b><br>
Overnight communications remained focused on partner escalations, product roadmap confirmations, and regional go-to-market priorities. Senior leadership channels were stable overnight with no emergency directives or unscheduled escalations received. Regional engineering and go-to-market spaces logged regular progress without blocking dependencies. Commercial deal motions across enterprise accounts are progressing with critical review gates scheduled for this week. Your schedule today provides substantial focus time with no immediate meeting conflicts on the morning calendar. All required briefing dossiers, background contexts, and decision options are organized below for your review.<br><br>
<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>
<ul>
  <li><b>Optus VAIS Escalation:</b> <a href="https://mail.google.com/mail/u/0/#inbox/optus-1"><u>Architecture validation response</u></a>: Simon Elisha requested confirmation on model armor guardrails. Last response Wednesday; Rob recommended escalating to APAC leads.</li>
</ul>
<br><b>ACTIVE HOT LIST UPDATES</b>
<ul>
  <li><b>Optus VAIS & Model Armor Blocker:</b> <a href="https://mail.google.com/mail/u/0/#inbox/optus-1"><u>Discussion active</u></a></li>
  <li><b>Woolworths (GE, FDE/SWE Initiative, FLW):</b> <i>On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet.</i></li>
  <li><b>Google AI DRZ / AU ML Processing:</b> <i>On topic Google AI DRZ / AU ML Processing no updates yet.</i></li>
</ul>
<br><b>AI MARKET UPDATES (TRAILING 72 HOURS)</b>
<ul>
  <li><b>Anthropic:</b> <a href="https://anthropic.com/news/claude-3-7"><u>Claude 3.7 Sonnet hybrid reasoning released</u></a> - Delivers dual-mode thinking for coding benchmarks.</li>
</ul>
<br><b>LOOKING AT YOUR DAY AHEAD</b>
<p>Looking at your day ahead, here are your scheduled commitments and meeting dossiers:</p>
<ul>
  <li><b>09:00 AM - 09:30 AM:</b> <a href="https://meet.google.com/standup"><u>AI Leadership Standup</u></a> (Meeting link attached).</li>
</ul>
"""


def test_lint_vp_standards_valid_briefing() -> None:
    """Verifies that a compliant executive briefing passes all VP standard checks."""
    result = lint_vp_standards(SAMPLE_VALID_BRIEFING)
    assert result["valid"] is True
    assert len(result["issues"]) == 0
    checks = result["checks"]
    assert checks["no_banned_phrases"] is True
    assert checks["no_emojis"] is True
    assert checks["overnight_summary_unbolded"] is True
    assert checks["overnight_summary_sentences"] == 6
    assert checks["overnight_summary_valid"] is True
    assert checks["hot_list_fallback_valid"] is True
    assert checks["day_ahead_start_valid"] is True
    assert checks["has_valid_links"] is True


def test_lint_vp_standards_empty_input() -> None:
    """Verifies handling when the briefing HTML is empty or whitespace."""
    result = lint_vp_standards("   ")
    assert result["valid"] is False
    assert "empty or blank" in result["issues"][0]


def test_lint_vp_standards_detects_banned_phrases() -> None:
    """Verifies detection of prohibited hyperbole and corporate clichés."""
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        "Overnight communications remained focused",
        "Here is your executive brief on the critical emergency",
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["no_banned_phrases"] is False
    issues_text = " ".join(result["issues"]).lower()
    assert "prohibited hyperbole" in issues_text or "clichés" in issues_text


def test_lint_vp_standards_detects_overused_words() -> None:
    """Verifies that excessive repetition of emotional spin words is flagged."""
    repeated = (
        SAMPLE_VALID_BRIEFING
        + "<p>strategic strategic strategic strategic strategic priority priority priority priority</p>"
    )
    result = lint_vp_standards(repeated)
    assert result["valid"] is False
    issues_text = " ".join(result["issues"]).lower()
    assert "overuse of dramatic/emotional word" in issues_text


def test_lint_vp_standards_detects_emojis() -> None:
    """Verifies that decorative icons and emojis trigger strict failure."""
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        "<b>CORE UPDATES", "<b>🚨 CORE UPDATES 🚀"
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["no_emojis"] is False
    assert any("Decorative emojis" in issue for issue in result["issues"])


def test_lint_vp_standards_detects_sentence_count_mismatch() -> None:
    """Verifies that overnight summaries with != 6 sentences are flagged."""
    # 3 sentences only
    short_summary = (
        "<b>OVERNIGHT SUMMARY</b><br>"
        "Sentence one was reported. Sentence two was recorded. Sentence three completed.<br><br>"
    )
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        SAMPLE_VALID_BRIEFING[
            SAMPLE_VALID_BRIEFING.find(
                "<b>OVERNIGHT SUMMARY</b>"
            ) : SAMPLE_VALID_BRIEFING.find("<b>CORE UPDATES")
        ],
        short_summary,
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["overnight_summary_sentences"] == 3
    assert result["checks"]["overnight_summary_valid"] is False


def test_lint_vp_standards_detects_bolding_in_summary() -> None:
    """Verifies that bold text inside the overnight summary triggers a failure."""
    bold_summary = (
        "<b>OVERNIGHT SUMMARY</b><br>"
        "Sentence one. <b>Sentence two in bold.</b> Sentence three. "
        "Sentence four. Sentence five. Sentence six.<br><br>"
    )
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        SAMPLE_VALID_BRIEFING[
            SAMPLE_VALID_BRIEFING.find(
                "<b>OVERNIGHT SUMMARY</b>"
            ) : SAMPLE_VALID_BRIEFING.find("<b>CORE UPDATES")
        ],
        bold_summary,
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["overnight_summary_unbolded"] is False


def test_lint_vp_standards_detects_missing_hot_list() -> None:
    """Verifies detection when the Active Hot List section is missing."""
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        "<b>ACTIVE HOT LIST UPDATES</b>", ""
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["hot_list_fallback_valid"] is False


def test_lint_vp_standards_detects_invalid_day_ahead_start() -> None:
    """Verifies that section 5 must open with 'Looking at your day ahead...'."""
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        "Looking at your day ahead, here are your scheduled commitments",
        "Here is the list of meetings you have today",
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["day_ahead_start_valid"] is False


def test_lint_vp_standards_detects_placeholder_hyperlinks() -> None:
    """Verifies that empty or placeholder '#' links are flagged."""
    flawed_briefing = SAMPLE_VALID_BRIEFING.replace(
        'href="https://mail.google.com/mail/u/0/#inbox/optus-1"', 'href="#"'
    )
    result = lint_vp_standards(flawed_briefing)
    assert result["valid"] is False
    assert result["checks"]["has_valid_links"] is False


def test_evaluate_briefing_draft_approval() -> None:
    """Verifies evaluate_briefing_draft emits 'approve' on compliant HTML."""
    eval_result = evaluate_briefing_draft(SAMPLE_VALID_BRIEFING)
    assert eval_result["verdict"] == "approve"
    assert eval_result["passed"] is True
    assert len(eval_result["issues"]) == 0
    assert "satisfies all executive VP standards" in eval_result["critique"]


def test_evaluate_briefing_draft_rejection() -> None:
    """Verifies evaluate_briefing_draft emits 'revise' on non-compliant HTML."""
    flawed = SAMPLE_VALID_BRIEFING + "<p>🚨 Critical emergency alert!</p>"
    eval_result = evaluate_briefing_draft(flawed)
    assert eval_result["verdict"] == "revise"
    assert eval_result["passed"] is False
    assert len(eval_result["issues"]) > 0
    assert "Draft requires revisions" in eval_result["critique"]


def test_finalize_approved_briefing_payload() -> None:
    """Verifies that finalize_approved_briefing produces a valid FinalBriefingPayload."""
    final_dict = finalize_approved_briefing(
        draft_html=SAMPLE_VALID_BRIEFING,
        reviewer_notes="Approved - passes all VP standards and formatting rules.",
    )
    payload = FinalBriefingPayload(**final_dict)
    assert payload.is_approved is True
    assert payload.final_html == SAMPLE_VALID_BRIEFING
    assert payload.editor_review_notes is not None
    assert payload.approved_at is not None


def test_finalize_approved_briefing_with_tool_context() -> None:
    """Verifies that ToolContext session state and escalation actions are triggered."""
    mock_context = MagicMock()
    mock_context.state = {}
    mock_context.actions = MagicMock()

    finalize_approved_briefing(
        draft_html=SAMPLE_VALID_BRIEFING,
        reviewer_notes="Approved by Chief of Staff.",
        tool_context=mock_context,
    )

    assert "final_briefing" in mock_context.state
    assert mock_context.state["final_briefing"]["is_approved"] is True
    assert mock_context.actions.escalate is True
    assert mock_context.actions.skip_summarization is True


def test_editor_reviewer_agent_configuration() -> None:
    """Verifies editor_reviewer_agent properties and tools list."""
    assert editor_reviewer_agent.name == "editor_reviewer_agent"
    assert editor_reviewer_agent.output_key == "final_briefing"
    tool_names = [
        t.__name__ if hasattr(t, "__name__") else t.name
        for t in editor_reviewer_agent.tools
    ]
    assert "lint_vp_standards" in tool_names
    assert "evaluate_briefing_draft" in tool_names
    assert "finalize_approved_briefing" in tool_names
    assert "exit_loop" in tool_names


def test_editorial_loop_configuration() -> None:
    """Verifies editorial_loop orchestration properties."""
    assert isinstance(editorial_loop, LoopAgent)
    assert editorial_loop.name == "editorial_loop"
    assert editorial_loop.max_iterations == 3
    assert len(editorial_loop.sub_agents) == 2
    assert editorial_loop.sub_agents[0].name == briefing_writer_agent.name
    assert editorial_loop.sub_agents[1].name == editor_reviewer_agent.name
