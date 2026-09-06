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

"""Unit tests for the Podcast Spoken Overview Editorial Loop and Tools.

Validates the acoustic linting rules, review evaluation, script finalization,
and ADK LoopAgent configuration for Stage 4a adhering to the
`audio-overview-script-editor` skill.
"""

from unittest.mock import MagicMock

from google.adk.agents import LoopAgent

from app.sub_agents.podcast_editor_reviewer_agent import (
    podcast_editor_reviewer_agent,
)
from app.sub_agents.podcast_editorial_loop import podcast_editorial_loop
from app.sub_agents.podcast_script_writer_agent import (
    podcast_script_writer_agent,
)
from app.tools.podcast_editor_tools import (
    evaluate_podcast_script,
    finalize_approved_podcast_script,
    lint_podcast_spoken_script,
)

SAMPLE_VALID_SPOKEN_SCRIPT = """
Overnight communications remained focused on partner escalations, product confirmations, and regional go-to-market priorities. Senior leadership channels were stable with no emergency directives received. Commercial deal motions are progressing with critical review gates scheduled for this week. Cross-functional execution streams remain active for the day ahead.

In leadership communications and core updates... There's no urgent leadership directives or direct report escalations over the past twenty-four hours.

Turning to our hot list priorities... We've seen no new movements reported on the Optus Model Armor blocker, Woolworths, or local ML processing.

Looking outward at AI market movements... OpenAI released GPT-6 Astra with recurrent depth reasoning for multi-step agentic workflows. Google DeepMind launched Gemini 3.8 Flash setting new benchmarks for long-horizon software engineering. And Meta AI released Muse Spark 1.3 focused on agentic coding efficiency with twenty percent fewer tool calls.
""".strip()

SAMPLE_SCRIPT_WITH_BRACKETS = """
Overnight communications remained focused on partner escalations.

Looking outward at AI market movements:
[Google DeepMind - 2026-09-02] Launches Gemini 3.8 Flash and Restricted 3.8 Flash Cyber.
[OpenAI - 2026-09-03] Releases GPT-6 Astra.
""".strip()

SAMPLE_SCRIPT_WITH_VISUAL_MARKDOWN = """
## Overnight Summary
* **Optus Blocker**: *There is no update yet.*
* **Woolworths**: *No updates.*
""".strip()

SAMPLE_SCRIPT_WITH_GREETING = """
Good morning Rob, welcome back to your morning podcast brief!
Overnight communications remained stable with no major escalations.
""".strip()


def test_lint_podcast_spoken_script_valid() -> None:
    """Verifies that a well-formed spoken script passes all acoustic lint checks."""
    result = lint_podcast_spoken_script(SAMPLE_VALID_SPOKEN_SCRIPT)
    assert result["valid"] is True
    assert len(result["issues"]) == 0
    assert result["checks"]["zero_visual_artifacts"] is True
    assert result["checks"]["no_bracketed_sources"] is True
    assert result["checks"]["no_robotic_counting"] is True
    assert result["checks"]["clean_open"] is True
    assert result["checks"]["no_hyperbole"] is True
    assert result["checks"]["contraction_density_valid"] is True
    assert result["checks"]["sentence_brevity_valid"] is True


def test_lint_detects_bracketed_sources() -> None:
    """Verifies that bracketed date/source tags are flagged for conversational rewrite."""
    result = lint_podcast_spoken_script(SAMPLE_SCRIPT_WITH_BRACKETS)
    assert result["valid"] is False
    assert result["checks"]["no_bracketed_sources"] is False
    assert any("bracketed citations" in issue.lower() for issue in result["issues"])


def test_lint_detects_visual_markdown() -> None:
    """Verifies that markdown headers, asterisks, and bullets are flagged."""
    result = lint_podcast_spoken_script(SAMPLE_SCRIPT_WITH_VISUAL_MARKDOWN)
    assert result["valid"] is False
    assert result["checks"]["zero_visual_artifacts"] is False
    assert any("visual artifacts" in issue.lower() for issue in result["issues"])


def test_lint_detects_greeting_pleasantries() -> None:
    """Verifies that artificial pleasantries and host banter are rejected."""
    result = lint_podcast_spoken_script(SAMPLE_SCRIPT_WITH_GREETING)
    assert result["valid"] is False
    assert result["checks"]["clean_open"] is False
    assert any("opening pleasantry" in issue.lower() for issue in result["issues"])


def test_lint_detects_robotic_counting() -> None:
    """Verifies that mechanical index counting like 'item number one' is caught."""
    script = "Overnight updates were quiet. Item number one is Woolworths. Secondly, Optus needs review."
    result = lint_podcast_spoken_script(script)
    assert result["valid"] is False
    assert result["checks"]["no_robotic_counting"] is False


def test_lint_detects_banned_hyperbole() -> None:
    """Verifies that corporate buzzwords like 'game-changer' are flagged."""
    script = "Overnight updates were quiet. OpenAI launched a revolutionary game-changer model for agents."
    result = lint_podcast_spoken_script(script)
    assert result["valid"] is False
    assert result["checks"]["no_hyperbole"] is False


def test_evaluate_podcast_script_tool() -> None:
    """Verifies evaluate_podcast_script returns approve for clean scripts."""
    mock_context = MagicMock()
    mock_context.state = {"podcast_script_draft": SAMPLE_VALID_SPOKEN_SCRIPT}

    result = evaluate_podcast_script(tool_context=mock_context)
    assert result["verdict"] == "approve"
    assert result["passed"] is True
    assert len(result["issues"]) == 0
    assert "podcast_script_critique" in mock_context.state


def test_evaluate_podcast_script_tool_revise() -> None:
    """Verifies evaluate_podcast_script returns revise for scripts with issues."""
    mock_context = MagicMock()
    mock_context.state = {"podcast_script_draft": SAMPLE_SCRIPT_WITH_BRACKETS}

    result = evaluate_podcast_script(tool_context=mock_context)
    assert result["verdict"] == "revise"
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_finalize_approved_podcast_script() -> None:
    """Verifies finalization sets state, expands acronyms, and triggers escalation."""
    mock_context = MagicMock()
    mock_context.state = {"podcast_script_draft": SAMPLE_VALID_SPOKEN_SCRIPT}
    mock_context.actions = MagicMock()

    result = finalize_approved_podcast_script(tool_context=mock_context)
    assert "spoken_script" in result
    assert result["word_count"] > 0
    assert result["estimated_duration_seconds"] > 0
    assert mock_context.actions.escalate is True
    assert mock_context.actions.skip_summarization is True
    assert "podcast_script" in mock_context.state


def test_podcast_editorial_loop_configuration() -> None:
    """Verifies podcast_editorial_loop structure and iteration limit."""
    assert isinstance(podcast_editorial_loop, LoopAgent)
    assert podcast_editorial_loop.name == "podcast_editorial_loop"
    assert podcast_editorial_loop.max_iterations == 5
    assert len(podcast_editorial_loop.sub_agents) == 2
    assert (
        podcast_editorial_loop.sub_agents[0].name
        == podcast_script_writer_agent.name
    )
    assert (
        podcast_editorial_loop.sub_agents[1].name
        == podcast_editor_reviewer_agent.name
    )
    assert podcast_script_writer_agent.output_key == "podcast_script_draft"
    assert podcast_editor_reviewer_agent.output_key == "podcast_script_critique"
