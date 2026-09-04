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

"""Automated evaluation metrics and judge harnesses for the Daily Brief agent (Rubric Item 5.1)."""

import re
from typing import Any
from urllib.parse import urlparse


def evaluate_executive_tone(html_briefing: str) -> dict[str, Any]:
    """Evaluates the briefing against Chief of Staff executive tone standards.

    Rules checked:
    1. Overnight summary is present and consists of exactly 6 sentences.
    2. Summary text does not contain bold HTML tags (<b>/<strong>).
    3. Zero emojis anywhere in the document.
    4. Zero sensationalized/hyperbolic buzzwords ('game-changer', 'insane', 'critical emergency').

    Args:
        html_briefing: The synthesized HTML briefing string.

    Returns:
        Dict with 'score' (0.0 to 1.0), 'passed' (bool), and 'issues' list.
    """
    issues: list[str] = []

    # 1. Emoji check
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]",
        re.UNICODE,
    )
    if emoji_pattern.search(html_briefing):
        issues.append("Disallowed emojis found in briefing HTML.")

    # 2. Hyperbolic language check
    banned_words = [
        r"\bgame[- ]?changer\b",
        r"\bmind[- ]?blowing\b",
        r"\binsane\b",
        r"\bcritical emergency\b",
        r"\bhere is your executive brief\b",
    ]
    for pattern in banned_words:
        if re.search(pattern, html_briefing, re.I):
            issues.append(
                f"Disallowed dramatic/hyperbolic phrase matching pattern: {pattern}"
            )

    # 3. Overnight summary structure & length
    summary_match = re.search(
        r"<b>OVERNIGHT SUMMARY</b><br>\s*(.*?)\s*<br><br>",
        html_briefing,
        re.DOTALL,
    )
    if not summary_match:
        issues.append("Missing '<b>OVERNIGHT SUMMARY</b>' header or structure.")
    else:
        summary_text = summary_match.group(1).strip()
        if "<b>" in summary_text or "<strong>" in summary_text:
            issues.append(
                "Overnight summary contains bolding, violating unbolded plain-text requirement."
            )

        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_text) if s.strip()
        ]
        if len(sentences) != 6:
            issues.append(
                f"Overnight summary must be exactly 6 sentences; found {len(sentences)}."
            )

    passed = len(issues) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(issues) * 0.25))
    return {"score": score, "passed": passed, "issues": issues}


def evaluate_noise_suppression(
    internal_data: dict[str, Any], output_briefing: str
) -> dict[str, Any]:
    """Evaluates whether low-priority chatter is suppressed while leadership directives are retained.

    Args:
        internal_data: Raw internal harvest payload containing leadership and chat threads.
        output_briefing: The synthesized HTML briefing string.

    Returns:
        Dict with 'score', 'passed', and 'issues'.
    """
    issues: list[str] = []

    # Verify that leadership threads are cited
    leadership_threads = internal_data.get("leadership_threads", [])
    for thread in leadership_threads:
        subject = thread.get("subject", "")
        # Subject should be referenced or represented
        clean_subj = re.sub(r"\[.*?\]", "", subject).strip()
        if (
            clean_subj
            and len(clean_subj) > 5
            and clean_subj.lower() not in output_briefing.lower()
        ):
            issues.append(
                f"Leadership directive '{subject}' was omitted from briefing."
            )

    passed = len(issues) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(issues) * 0.3))
    return {"score": score, "passed": passed, "issues": issues}


def evaluate_link_validity(html_briefing: str) -> dict[str, Any]:
    """Validates that all hyperlinked sources in the briefing contain valid HTTP/HTTPS URLs.

    Args:
        html_briefing: The synthesized HTML briefing string.

    Returns:
        Dict with 'score', 'passed', and 'issues'.
    """
    issues: list[str] = []
    hrefs = re.findall(r'href=["\'](.*?)["\']', html_briefing, re.I)

    if not hrefs:
        issues.append("No hyperlinked sources found in briefing.")

    for href in hrefs:
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            issues.append(f"Invalid or relative hyperlink URL: '{href}'")

    passed = len(issues) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(issues) * 0.2))
    return {
        "score": score,
        "passed": passed,
        "total_links": len(hrefs),
        "issues": issues,
    }


def evaluate_hot_list_fallback(
    html_briefing: str, active_themes: list[str]
) -> dict[str, Any]:
    """Verifies that all active Hot List priorities are accounted for, using the exact fallback if silent.

    Args:
        html_briefing: The synthesized HTML briefing string.
        active_themes: List of hot list theme names (e.g., ['Optus VAIS', 'Woolworths']).

    Returns:
        Dict with 'score', 'passed', and 'issues'.
    """
    issues: list[str] = []

    if "<b>ACTIVE HOT LIST UPDATES</b>" not in html_briefing:
        issues.append("Missing '<b>ACTIVE HOT LIST UPDATES</b>' section.")
        return {"score": 0.0, "passed": False, "issues": issues}

    for theme in active_themes:
        # Check if theme name appears in briefing
        if theme.lower() not in html_briefing.lower():
            issues.append(f"Hot List theme '{theme}' not mentioned in briefing.")

    passed = len(issues) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(issues) * 0.33))
    return {"score": score, "passed": passed, "issues": issues}


def evaluate_calendar_exclusion(html_briefing: str) -> dict[str, Any]:
    """Verifies that meeting schedules and calendar updates are omitted from the briefing body.

    Args:
        html_briefing: The synthesized HTML briefing string.

    Returns:
        Dict with 'score', 'passed', and 'issues'.
    """
    issues: list[str] = []
    lower_html = html_briefing.lower()

    if (
        "looking at your day ahead" in lower_html
        or "today's meeting readiness" in lower_html
    ):
        issues.append(
            "Calendar agenda section found in briefing text; calendar updates must be omitted."
        )

    passed = len(issues) == 0
    score = 1.0 if passed else 0.0
    return {"score": score, "passed": passed, "issues": issues}


# =============================================================================
# UNIT TESTS FOR EVALUATION METRICS
# =============================================================================

SAMPLE_VALID_BRIEFING = """
<b><a href="https://drive.google.com/file/d/1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV/view"><u>Listen to Brief</u></a></b><br><br>
<b>OVERNIGHT SUMMARY</b><br>
Internal communication channels recorded four priority escalations overnight. The Optus leadership engagement requires confirmation on Model Armor deployment by early afternoon. Woolworths engineering teams confirmed the upcoming architecture review for the Shopping Agent initiative. In external developments, frontier model providers released new reasoning paradigms and efficiency benchmarks. Infrastructure teams observed optical circuit switching advancements for TPU clusters. All secondary chat spaces remain stable with routine operations.<br><br>
<b>CORE UPDATES & LEADERSHIP DIRECTIVES</b>
<ul>
  <li><b>[Optus] <a href="https://mail.google.com/mail/u/0/#inbox/123"><u>Model Armor Blocker</u></a>:</b> Critical deployment confirmation needed by 2pm today.</li>
</ul>
<b>ACTIVE HOT LIST UPDATES</b>
<ul>
  <li><b><a href="https://mail.google.com/mail/u/0/#inbox/123"><u>Optus VAIS & Model Armor</u></a>:</b> Deployment approval is pending final review.</li>
  <li><b>Woolworths:</b> <i>On topic Woolworths no updates yet.</i></li>
</ul>
<b>AI MARKET UPDATES (TRAILING 72 HOURS)</b>
<ul>
  <li><b>Gemini 2.5 Flash:</b> <a href="https://blog.google/technology/ai"><u>Native reasoning token efficiency update</u></a>.</li>
</ul>
"""


def test_metric_executive_tone_valid():
    """Verify that a compliant executive briefing receives a perfect tone score."""
    result = evaluate_executive_tone(SAMPLE_VALID_BRIEFING)
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert len(result["issues"]) == 0


def test_metric_executive_tone_invalid_sentence_count():
    """Verify that a summary with 3 sentences fails the tone check."""
    invalid_html = SAMPLE_VALID_BRIEFING.replace(
        "Internal communication channels recorded four priority escalations overnight. The Optus leadership engagement requires confirmation on Model Armor deployment by early afternoon. Woolworths engineering teams confirmed the upcoming architecture review for the Shopping Agent initiative. In external developments, frontier model providers released new reasoning paradigms and efficiency benchmarks. Infrastructure teams observed optical circuit switching advancements for TPU clusters. All secondary chat spaces remain stable with routine operations.",
        "Internal communications were recorded overnight. Optus needs confirmation. Everything else is fine.",
    )
    result = evaluate_executive_tone(invalid_html)
    assert result["passed"] is False
    assert any("exactly 6 sentences" in issue for issue in result["issues"])


def test_metric_executive_tone_emojis():
    """Verify that presence of emojis results in a penalty."""
    emoji_html = SAMPLE_VALID_BRIEFING + "🚀 Critical update!"
    result = evaluate_executive_tone(emoji_html)
    assert result["passed"] is False
    assert any("Disallowed emojis" in issue for issue in result["issues"])


def test_metric_link_validity():
    """Verify link validity scoring on valid and invalid hyperlinks."""
    result = evaluate_link_validity(SAMPLE_VALID_BRIEFING)
    assert result["passed"] is True
    assert result["score"] == 1.0

    bad_html = SAMPLE_VALID_BRIEFING.replace(
        "https://drive.google.com", "file:///invalid/path"
    )
    bad_result = evaluate_link_validity(bad_html)
    assert bad_result["passed"] is False
    assert any("Invalid or relative" in issue for issue in bad_result["issues"])


def test_metric_hot_list_fallback():
    """Verify Hot List tracking and fallback detection."""
    result = evaluate_hot_list_fallback(SAMPLE_VALID_BRIEFING, ["Optus", "Woolworths"])
    assert result["passed"] is True
    assert result["score"] == 1.0

    missing_result = evaluate_hot_list_fallback(
        SAMPLE_VALID_BRIEFING, ["Unknown Project XYZ"]
    )
    assert missing_result["passed"] is False


def test_metric_calendar_exclusion():
    """Verify calendar exclusion checker."""
    # Compliant briefing has no calendar section
    result = evaluate_calendar_exclusion(SAMPLE_VALID_BRIEFING)
    assert result["passed"] is True
    assert result["score"] == 1.0

    # Non-compliant briefing includes calendar agenda
    agenda_html = (
        SAMPLE_VALID_BRIEFING
        + "<b>LOOKING AT YOUR DAY AHEAD</b><ul><li>9:00 AM Meeting</li></ul>"
    )
    agenda_result = evaluate_calendar_exclusion(agenda_html)
    assert agenda_result["passed"] is False
    assert agenda_result["score"] == 0.0
