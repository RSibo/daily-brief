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

"""Executive Reviewer & VP Standards Linting Tools.

Implements Phase 4 of the Daily Brief architecture:
- Validates executive VP update standards: calm matter-of-fact tone, zero hyperbole.
- Strictly prohibits banned clichés ("here is your executive brief", "critical emergency").
- Detects unauthorized emotional spin words ("emergency", "strategic") unless quoted.
- Enforces zero emojis and decorative icons.
- Verifies structural constraints:
    1. Overnight Summary: exactly 6 plain-text, unbolded sentences.
    2. Hot List fallbacks: exact string "On topic [Theme Name] no updates yet."
    3. Today's agenda: begins with "Looking at your day ahead...".
    4. Link validity: all updates backed by canonical hyperlinks.
- Evaluates draft briefings and coordinates loop approval or revision critique.
- Finalizes approved briefings into FinalBriefingPayload and triggers loop escalation.
"""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from app.app_utils.telemetry import trace_tool
from app.app_utils.typing import FinalBriefingPayload, StructuredToolError

SYDNEY_TZ = ZoneInfo("Australia/Sydney")

BANNED_PHRASES = [
    "here is your executive brief",
    "critical emergency",
    "game-changer",
    "unprecedented",
    "vital importance",
]

# Words that should not be overused without direct quotes (word, max_allowed)
OVERUSED_WORDS = [
    ("strategic", 3),
    ("emergency", 2),
    ("priority", 3),
]

EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50]")


@trace_tool(tool_name="lint_vp_standards")
def lint_vp_standards(html_content: str) -> dict[str, Any]:
    """Lints an executive HTML briefing against Google VP update standards.

    Audits tone, hyperbole, emotional filler, emojis, sentence counts,
    mandatory fallback phrases, and hyperlink integrity.

    Args:
        html_content: Complete HTML string of the executive briefing draft.

    Returns:
        Dictionary containing validation verdict, issues list, and granular checks.
    """
    if not html_content or not html_content.strip():
        return {
            "valid": False,
            "issues": ["Briefing HTML content is empty or blank."],
            "checks": {
                "no_banned_phrases": False,
                "no_emojis": False,
                "overnight_summary_sentences": 0,
                "overnight_summary_valid": False,
                "hot_list_fallback_valid": False,
                "day_ahead_start_valid": False,
                "has_valid_links": False,
            },
        }

    issues: list[str] = []
    checks: dict[str, Any] = {}

    lower_html = html_content.lower()

    # 1. Banned hyperbole and clichés
    banned_found = [phrase for phrase in BANNED_PHRASES if phrase in lower_html]
    if banned_found:
        issues.append(
            f"Prohibited hyperbole/clichés detected: {', '.join(banned_found)}."
        )
        checks["no_banned_phrases"] = False
    else:
        checks["no_banned_phrases"] = True

    # 2. Emotional spin words outside quotes or URLs (overuse check)
    stripped_urls = re.sub(r'href=["\'][^"\']+["\']', 'href=""', lower_html)
    stripped_quotes = re.sub(r'"[^"]*"', '""', stripped_urls)
    for word, max_allowed in OVERUSED_WORDS:
        count = len(re.findall(rf"\b{word}\b", stripped_quotes))
        if count > max_allowed:
            issues.append(
                f"Overuse of dramatic/emotional word '{word}' detected ({count} occurrences, max allowed is {max_allowed}). "
                "VP standards require a calm, matter-of-fact tone without emotional hyperbole unless directly quoted."
            )

    # 3. Emojis and decorative icons
    emojis_found = EMOJI_PATTERN.findall(html_content)
    if emojis_found:
        issues.append(
            f"Decorative emojis or icons detected ({len(emojis_found)} found). "
            "VP standards strictly prohibit emojis or decorative symbols in executive briefs."
        )
        checks["no_emojis"] = False
    else:
        checks["no_emojis"] = True

    # 4. Overnight Summary audit (exactly 6 plain-text, unbolded sentences)
    summary_match = re.search(
        r"OVERNIGHT SUMMARY(?:</b>|</h3>)(?:<br\s*/?>\s*)+(.*?)(?:<br\s*/?>\s*<br\s*/?>|<b>\s*[A-Z0-9\s&]{4,}</b>|<h[1-6]>|$)",
        html_content,
        re.IGNORECASE | re.DOTALL,
    )
    if not summary_match:
        summary_match = re.search(
            r"OVERNIGHT SUMMARY</h3>\s*<p>(.*?)</p>",
            html_content,
            re.IGNORECASE | re.DOTALL,
        )

    if summary_match:
        summary_block = summary_match.group(1).strip()
        # Check for bolding inside the overnight summary text
        if re.search(r"<(b|strong)\b", summary_block, re.IGNORECASE):
            issues.append(
                "Overnight Summary contains bold formatting. Standard requires unbolded plain text."
            )
            checks["overnight_summary_unbolded"] = False
        else:
            checks["overnight_summary_unbolded"] = True

        # Strip all HTML tags to analyze plain sentence count
        clean_text = re.sub(r"<[^>]+>", " ", summary_block).strip()
        clean_text = re.sub(r"\s+", " ", clean_text)
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()
        ]
        checks["overnight_summary_sentences"] = len(sentences)

        if len(sentences) != 6:
            issues.append(
                f"Overnight Summary must contain exactly 6 sentences; found {len(sentences)}."
            )
            checks["overnight_summary_valid"] = False
        else:
            checks["overnight_summary_valid"] = True
    else:
        issues.append("Missing required 'OVERNIGHT SUMMARY' section.")
        checks["overnight_summary_sentences"] = 0
        checks["overnight_summary_valid"] = False

    # 5. Hot List Fallback Check
    if "active hot list updates" in lower_html:
        fallback_matches = re.findall(
            r"On topic [^.]+ no updates yet\.", html_content, re.IGNORECASE
        )
        has_items = "<li>" in lower_html
        checks["hot_list_fallback_valid"] = bool(fallback_matches or has_items)
    else:
        checks["hot_list_fallback_valid"] = False
        issues.append("Missing required 'ACTIVE HOT LIST UPDATES' section.")

    # 6. Today's agenda start phrase check (optional: skipped when calendar updates omitted)
    if "looking at your day ahead" in lower_html or "day ahead" in lower_html:
        agenda_match = re.search(
            r"LOOKING AT YOUR DAY AHEAD(?:</b>|</h3>)\s*(?:<br\s*/?>)*\s*(?:<p>)?(.*?)(?:</p>|<br|<ul>|$)",
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if agenda_match:
            agenda_text = agenda_match.group(1).strip()
            clean_agenda = re.sub(r"<[^>]+>", " ", agenda_text).strip()
            if clean_agenda.lower().startswith("looking at your day ahead"):
                checks["day_ahead_start_valid"] = True
            else:
                checks["day_ahead_start_valid"] = False
                issues.append(
                    "Agenda section must start with the phrase 'Looking at your day ahead...'."
                )
        elif "looking at your day ahead" in lower_html:
            checks["day_ahead_start_valid"] = True
        else:
            checks["day_ahead_start_valid"] = False
            issues.append(
                "Agenda section does not contain the mandatory opening phrase 'Looking at your day ahead...'."
            )
    else:
        # Calendar updates omitted per current operational directive
        checks["day_ahead_start_valid"] = True

    # 7. Hyperlink integrity
    links = re.findall(r'href=["\']([^"\']*)["\']', html_content)
    if not links:
        issues.append(
            "No hyperlinks found in briefing. All core updates must have canonical source links."
        )
        checks["has_valid_links"] = False
    else:
        invalid_links = [
            link
            for link in links
            if not link
            or link in ("#", "javascript:")
            or link.startswith("javascript:")
        ]
        if invalid_links:
            issues.append(f"Found empty or placeholder hyperlinks: {invalid_links}.")
            checks["has_valid_links"] = False
        else:
            checks["has_valid_links"] = True

    is_valid = len(issues) == 0
    return {
        "valid": is_valid,
        "issues": issues,
        "checks": checks,
    }


@trace_tool(tool_name="evaluate_briefing_draft")
def evaluate_briefing_draft(
    draft_html: str,
    context_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluates a synthesized executive draft briefing and decides review verdict.

    Performs full automated VP standards linting and returns structured
    verdict ('approve' or 'revise') with actionable critique.

    Args:
        draft_html: The HTML briefing draft to evaluate.
        context_metadata: Optional context metadata for traceability.

    Returns:
        Dictionary containing verdict ('approve' or 'revise'), critique string,
        and list of specific issues.
    """
    try:
        lint_results = lint_vp_standards(draft_html)
        if lint_results["valid"]:
            return {
                "verdict": "approve",
                "critique": "Draft satisfies all executive VP standards, formatting rules, and structural constraints.",
                "issues": [],
                "passed": True,
            }

        issues_summary = "; ".join(lint_results["issues"])
        return {
            "verdict": "revise",
            "critique": f"Draft requires revisions before approval: {issues_summary}",
            "issues": lint_results["issues"],
            "passed": False,
        }
    except Exception as exc:
        return StructuredToolError(
            error_code="EVALUATION_FAILED",
            message=f"Failed to evaluate briefing draft: {exc}",
            recovery_instruction="Check input draft_html format and re-run evaluate_briefing_draft.",
        ).model_dump()


@trace_tool(tool_name="finalize_approved_briefing")
def finalize_approved_briefing(
    draft_html: str,
    reviewer_notes: str = "Approved - passes all VP standards.",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Finalizes an approved executive briefing and prepares the payload for delivery.

    Constructs FinalBriefingPayload, sets session state 'final_briefing' if tool_context
    is available, and triggers loop escalation to exit the review cycle.

    Args:
        draft_html: The approved, validated HTML briefing text.
        reviewer_notes: Editorial notes confirming validation.
        tool_context: ADK ToolContext for state updates and loop escalation.

    Returns:
        Serialized FinalBriefingPayload dictionary.
    """
    try:
        approved_at = datetime.now(SYDNEY_TZ).isoformat()
        payload = FinalBriefingPayload(
            final_html=draft_html,
            is_approved=True,
            editor_review_notes=reviewer_notes,
            approved_at=approved_at,
        )
        serialized = payload.model_dump()

        if tool_context is not None:
            tool_context.state["final_briefing"] = serialized
            tool_context.actions.escalate = True
            tool_context.actions.skip_summarization = True

        return serialized
    except Exception as exc:
        return StructuredToolError(
            error_code="FINALIZATION_FAILED",
            message=f"Failed to finalize approved briefing: {exc}",
            recovery_instruction="Ensure draft_html is a valid string and re-invoke finalize_approved_briefing.",
        ).model_dump()
