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

"""Unit tests for Unified Daily Brief Runner Loops.

Validates:
- `run_editorial_loop`: Multi-iteration Chief of Staff revision & approval workflow.
- `revise_briefing_draft`: Remediation of VP standard violations (emojis, banned phrases).
- `run_podcast_editorial_loop`: Multi-iteration acoustic revision & approval workflow.
- `revise_podcast_script`: Removal of visual artifacts, bracket citations, contractions.
"""

from scripts.run_daily_brief import (
    revise_briefing_draft,
    revise_podcast_script,
    run_editorial_loop,
    run_podcast_editorial_loop,
)


def test_revise_briefing_draft_cleans_emojis_and_hyperbole() -> None:
    """Verifies that revise_briefing_draft strips emojis and banned hyperbole."""
    flawed_html = "<b>OVERNIGHT SUMMARY</b><br>Here is your executive brief on the critical emergency! 🚨"
    clean_html = revise_briefing_draft(flawed_html, issues=["Banned hyperbole"])
    assert "🚨" not in clean_html
    assert "here is your executive brief" not in clean_html.lower()
    assert "critical emergency" not in clean_html.lower()


def test_run_editorial_loop_approval() -> None:
    """Verifies that run_editorial_loop completes and returns approved payload."""
    internal_data = {
        "leadership_threads": [],
        "direct_report_threads": [],
        "chat_space_threads": [],
        "calendar_events": [],
        "hot_list_matches": {},
    }
    market_data = {"announcements": []}
    result = run_editorial_loop(
        internal_data=internal_data,
        market_data=market_data,
        mode="afternoon",
        max_iterations=4,
    )
    assert result["is_approved"] is True
    assert "final_html" in result
    assert len(result["final_html"]) > 0


def test_revise_podcast_script_acoustic_rules() -> None:
    """Verifies that revise_podcast_script enforces acoustic standards."""
    raw_script = """
# Morning Overview
**Today's Updates**
- Item number one: we have seen that [Google DeepMind - 2026-09-02] Releases GPT-6.
- Secondly, there is a game-changer announcement.
"""
    revised = revise_podcast_script(raw_script, issues=["Visual artifacts"])
    assert "#" not in revised
    assert "**" not in revised
    assert not any(line.strip().startswith("-") for line in revised.splitlines())
    assert "we've" in revised
    assert "there's" in revised
    assert "[Google DeepMind" not in revised
    assert revised.startswith("Let's begin;")


def test_run_podcast_editorial_loop_approval() -> None:
    """Verifies that run_podcast_editorial_loop adapts briefing and approves script."""
    sample_html = """
<b>OVERNIGHT SUMMARY</b><br>
Overnight communications remained focused on partner escalations, product roadmap confirmations, and regional go-to-market priorities. Senior leadership channels were stable overnight with no emergency directives or unscheduled escalations received. Regional engineering and go-to-market spaces logged regular progress without blocking dependencies. Commercial deal motions across enterprise accounts are progressing with critical review gates scheduled for this week. Cross-functional execution streams and account workstreams remain active for the day ahead. All required briefing dossiers, background contexts, and decision options are organized below for your review.<br><br>
<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>
<ul>
  <li>No urgent leadership directives or direct report escalations over the past 24 hours.</li>
</ul>
<br><b>ACTIVE HOT LIST UPDATES</b>
<ul>
  <li><b>Optus VAIS & Model Armor Blocker:</b> <i>On topic Optus VAIS & Model Armor Blocker no updates yet.</i></li>
  <li><b>Woolworths (GE, FDE/SWE Initiative, FLW):</b> <i>On topic Woolworths (GE, FDE/SWE Initiative, FLW) no updates yet.</i></li>
  <li><b>Google AI DRZ / AU ML Processing:</b> <i>On topic Google AI DRZ / AU ML Processing no updates yet.</i></li>
</ul>
"""
    result = run_podcast_editorial_loop(
        final_briefing_html=sample_html, max_iterations=5
    )
    assert "spoken_script" in result
    assert result["word_count"] > 0
    assert result["spoken_script"].startswith("Let's begin;")
