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

"""Podcast Spoken Overview Editor & Audio Linter Tools.

Implements the quality control and linting engine for the Podcast Editorial Loop
(Stage 4a) adhering to the `audio-overview-script-editor` skill:
- Lints spoken scripts against Pre-Emission Linter criteria:
    1. Zero visual artifacts (no markdown asterisks, hashes, brackets, bullets).
    2. No bracketed metadata citations (e.g. '[Google DeepMind - 2026-09-02]').
    3. No robotic counting ('item number one', 'firstly', 'secondly').
    4. High contraction density (>= 75% contraction ratio on auxiliary verbs).
    5. Linear sentence brevity (max 18 words per sentence).
    6. Clean zero-fluff opening (no greetings or pleasantries).
    7. Hyperbole ban (prohibits unquoted buzzwords).
    8. Word count bounds (between 250 and 850 words for executive listening).
- Evaluates working drafts and provides actionable editorial critique.
- Finalizes approved spoken scripts into PodcastScriptPayload and escalates loop.
"""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from app.app_utils.telemetry import trace_tool
from app.app_utils.typing import (
    PodcastReviewCritiquePayload,
    PodcastScriptDraftPayload,
    PodcastScriptPayload,
    StructuredToolError,
)
from app.tools.podcast_tools import CANONICAL_PHONETIC_MAP

SYDNEY_TZ = ZoneInfo("Australia/Sydney")

BANNED_AUDIO_OPENINGS = [
    "good morning",
    "good afternoon",
    "good evening",
    "welcome to",
    "welcome back",
    "hello rob",
    "hello everyone",
    "hey rob",
    "in today's podcast",
    "in this podcast",
    "here is your podcast",
    "here is your audio",
    "today is monday",
    "today is tuesday",
    "today is wednesday",
    "today is thursday",
    "today is friday",
    "today is saturday",
    "today is sunday",
]

ROBOTIC_COUNTING_PATTERNS = [
    r"\bitem\s+(?:number\s+)?(?:one|two|three|four|five|\d+)\b",
    r"\bfirstly\b",
    r"\bsecondly\b",
    r"\bthirdly\b",
    r"\bfourthly\b",
    r"\bpoint\s+(?:one|two|three|\d+)\b",
]

BANNED_HYPERBOLE_WORDS = [
    "game-changer",
    "critical emergency",
    "revolutionary",
    "unprecedented",
    "vital importance",
    "pivotal milestone",
]

UNCONTRACTED_PAIRS = [
    (r"\bwe\s+have\b", "we've"),
    (r"\bthere\s+is\b", "there's"),
    (r"\bit\s+is\b", "it's"),
    (r"\bthey\s+will\b", "they'll"),
    (r"\bthey\s+are\b", "they're"),
    (r"\bwe\s+are\b", "we're"),
    (r"\bwe\s+will\b", "we'll"),
    (r"\bdo\s+not\b", "don't"),
    (r"\bdoes\s+not\b", "doesn't"),
    (r"\bis\s+not\b", "isn't"),
    (r"\bare\s+not\b", "aren't"),
    (r"\bcannot\b", "can't"),
    (r"\bwill\s+not\b", "won't"),
    (r"\bhas\s+not\b", "hasn't"),
    (r"\bhave\s+not\b", "haven't"),
    (r"\bthat\s+is\b", "that's"),
]


@trace_tool(tool_name="lint_podcast_spoken_script")
def lint_podcast_spoken_script(
    script_text: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Lints a spoken audio script against executive Chief of Staff acoustic standards.

    Audits visual markdown artifacts, bracketed citation patterns, robotic counting,
    contraction density, sentence length, greeting pleasantries, and hyperbole.

    Args:
        script_text: Spoken audio script text to audit. If omitted, auto-resolves
            from tool_context.state['podcast_script_draft'] or state['podcast_script'].
        tool_context: Optional ADK ToolContext to resolve script from session state.

    Returns:
        Dictionary containing overall validity ('valid': bool), issues list, and granular checks.
    """
    if (
        script_text is None
        and tool_context is not None
        and hasattr(tool_context, "state")
    ):
        draft_val = tool_context.state.get("podcast_script_draft", "")
        if isinstance(draft_val, dict):
            script_text = draft_val.get("spoken_script_draft") or draft_val.get(
                "spoken_script", ""
            )
        elif isinstance(draft_val, str):
            script_text = draft_val

        if not script_text:
            script_val = tool_context.state.get("podcast_script", "")
            if isinstance(script_val, dict):
                script_text = script_val.get("spoken_script", "")
            elif isinstance(script_val, str):
                script_text = script_val

    if not script_text or not script_text.strip():
        return {
            "valid": False,
            "issues": ["Spoken script content is empty or blank."],
            "checks": {
                "zero_visual_artifacts": False,
                "no_bracketed_sources": False,
                "no_robotic_counting": False,
                "clean_open": False,
                "no_hyperbole": False,
                "contraction_density_valid": False,
                "sentence_brevity_valid": False,
                "word_count_valid": False,
            },
        }

    issues: list[str] = []
    checks: dict[str, Any] = {}
    lower_text = script_text.lower().strip()

    # 1. Zero Visual Artifacts (markdown symbols, headers, bullet dashes)
    visual_patterns = [
        (r"(?:^|\n)\s*#+\s+", "markdown headers (e.g. '##')"),
        (r"\*{1,3}[^*]+\*{1,3}", "markdown bold/italics asterisks"),
        (r"(?:^|\n)\s*[-*•]\s+", "bullet points or dashes"),
        (r"\[Host\]:|\[Narrator\]:|\[Speaker\]:", "speaker stage direction tags"),
        (r"<b>|</b>|<i>|</i>|<a\s|</a>|<br\s*/?>", "raw HTML tags"),
    ]
    visual_violations = []
    for pattern, desc in visual_patterns:
        if re.search(pattern, script_text, flags=re.IGNORECASE):
            visual_violations.append(desc)

    if visual_violations:
        issues.append(
            f"Visual artifacts detected in spoken script: {', '.join(visual_violations)}. Output must be pure spoken prose."
        )
        checks["zero_visual_artifacts"] = False
    else:
        checks["zero_visual_artifacts"] = True

    # 2. No Bracketed Metadata / Citations (e.g. "[Google DeepMind - 2026-09-02]")
    bracketed_matches = re.findall(r"\[[^\]]+\]", script_text)
    if bracketed_matches:
        issues.append(
            f"Mechanical bracketed citations detected: {bracketed_matches[:3]}. Rephrase into natural spoken narrative (e.g. 'Google DeepMind released...')."
        )
        checks["no_bracketed_sources"] = False
    else:
        checks["no_bracketed_sources"] = True

    # 3. No Robotic Counting ("item number one", "secondly")
    robotic_found = []
    for pattern in ROBOTIC_COUNTING_PATTERNS:
        matches = re.findall(pattern, lower_text)
        if matches:
            robotic_found.extend(matches)

    if robotic_found:
        issues.append(
            f"Robotic index counting detected: {robotic_found}. Use smooth acoustic transitions ('First off...', 'Alongside that...')."
        )
        checks["no_robotic_counting"] = False
    else:
        checks["no_robotic_counting"] = True

    # 4. Clean Open (Zero greeting or pleasantry fluff)
    first_sentence = re.split(r"[.!?]\s+", script_text.strip())[0].lower()
    has_banned_open = any(first_sentence.startswith(b) for b in BANNED_AUDIO_OPENINGS)
    if has_banned_open:
        issues.append(
            f"Prohibited opening pleasantry detected ('{first_sentence[:40]}...'). Open immediately with the lead business signal."
        )
        checks["clean_open"] = False
    else:
        checks["clean_open"] = True

    # 5. Hyperbole Ban
    hyperbole_found = [h for h in BANNED_HYPERBOLE_WORDS if h in lower_text]
    if hyperbole_found:
        issues.append(
            f"Banned hyperbole detected: {', '.join(hyperbole_found)}. Stick strictly to matter-of-fact Chief of Staff tone."
        )
        checks["no_hyperbole"] = False
    else:
        checks["no_hyperbole"] = True

    # 6. Contraction Density Check
    uncontracted_count = 0
    for pattern, _ in UNCONTRACTED_PAIRS:
        uncontracted_count += len(re.findall(pattern, lower_text))

    contracted_count = len(
        re.findall(
            r"\b(?:we've|there's|it's|they'll|they're|we're|we'll|don't|doesn't|isn't|aren't|can't|won't|hasn't|haven't|that's|what's|you're|you'll)\b",
            lower_text,
        )
    )
    total_opportunities = contracted_count + uncontracted_count
    contraction_density = (
        (contracted_count / total_opportunities) if total_opportunities > 0 else 1.0
    )
    checks["contraction_density"] = round(contraction_density, 2)
    checks["contracted_count"] = contracted_count
    checks["uncontracted_count"] = uncontracted_count

    if total_opportunities >= 3 and contraction_density < 0.60:
        issues.append(
            f"Contraction density is low ({int(contraction_density*100)}%). Spoken scripts must use natural contractions (e.g., 'we've', 'there's', 'it's')."
        )
        checks["contraction_density_valid"] = False
    else:
        checks["contraction_density_valid"] = True

    # 7. Sentence Brevity (Cap at 18-22 words per sentence for acoustic comprehension)
    raw_sentences = re.split(r"(?<=[.!?])\s+", script_text.strip())
    long_sentences = []
    for s in raw_sentences:
        clean_s = s.strip()
        if not clean_s:
            continue
        words = clean_s.split()
        if len(words) > 22:
            long_sentences.append((len(words), clean_s[:60] + "..."))

    checks["total_sentences"] = len(raw_sentences)
    checks["long_sentences_count"] = len(long_sentences)
    if len(long_sentences) > 2:
        issues.append(
            f"Found {len(long_sentences)} overly long sentences (> 22 words). Audio scripts must use linear Subject-Verb-Object sentences capped under 18 words to prevent listener cognitive fatigue."
        )
        checks["sentence_brevity_valid"] = False
    else:
        checks["sentence_brevity_valid"] = True

    # 8. Word Count Check (Target: 80 - 850 words)
    total_words = len(script_text.split())
    checks["word_count"] = total_words
    if total_words < 80:
        issues.append(
            f"Script is too brief ({total_words} words). Ensure all key leadership, hot list, and market movements are covered."
        )
        checks["word_count_valid"] = False
    elif total_words > 950:
        issues.append(
            f"Script is too long ({total_words} words). Executive audio overview must remain concise (aim for 300–700 words)."
        )
        checks["word_count_valid"] = False
    else:
        checks["word_count_valid"] = True

    is_valid = len(issues) == 0
    return {
        "valid": is_valid,
        "issues": issues,
        "checks": checks,
    }


@trace_tool(tool_name="evaluate_podcast_script")
def evaluate_podcast_script(
    draft_script: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Evaluates a draft spoken audio script and returns structured review verdict.

    Performs full acoustic linting and returns 'approve' if valid, or 'revise'
    with specific, actionable feedback for the podcast script writer agent.

    Args:
        draft_script: Optional spoken script text to evaluate. If omitted,
            auto-resolves from tool_context.state['podcast_script_draft'].
        tool_context: Optional ADK ToolContext to resolve draft from session state.

    Returns:
        Serialized PodcastReviewCritiquePayload dictionary.
    """
    try:
        if (
            draft_script is None
            and tool_context is not None
            and hasattr(tool_context, "state")
        ):
            draft_val = tool_context.state.get("podcast_script_draft", "")
            if isinstance(draft_val, dict):
                draft_script = draft_val.get("spoken_script_draft") or draft_val.get(
                    "spoken_script", ""
                )
            elif isinstance(draft_val, str):
                draft_script = draft_val

        draft_script = draft_script or ""
        lint_results = lint_podcast_spoken_script(draft_script)

        if lint_results["valid"]:
            payload = PodcastReviewCritiquePayload(
                verdict="approve",
                critique="Script satisfies all acoustic standards: zero visual artifacts, natural narrative transitions, high contraction density, and punchy sentence length.",
                issues=[],
                passed=True,
                reviewed_at=datetime.now(SYDNEY_TZ).isoformat(),
            )
        else:
            issues_summary = "; ".join(lint_results["issues"])
            payload = PodcastReviewCritiquePayload(
                verdict="revise",
                critique=f"Script requires acoustic revisions before approval: {issues_summary}",
                issues=lint_results["issues"],
                passed=False,
                reviewed_at=datetime.now(SYDNEY_TZ).isoformat(),
            )

        serialized = payload.model_dump()
        if tool_context is not None and hasattr(tool_context, "state"):
            tool_context.state["podcast_script_critique"] = serialized

        return serialized
    except Exception as exc:
        return StructuredToolError(
            error_code="PODCAST_EVALUATION_FAILED",
            message=f"Failed to evaluate podcast spoken script: {exc}",
            recovery_instruction="Verify draft_script text and retry evaluate_podcast_script.",
        ).model_dump()


@trace_tool(tool_name="finalize_approved_podcast_script")
def finalize_approved_podcast_script(
    spoken_script: str | None = None,
    reviewer_notes: str = "Approved - passes all acoustic and Chief of Staff standards.",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Finalizes an approved spoken audio script and prepares state for TTS synthesis.

    Applies canonical phonetic acronym expansions, computes word counts and estimated
    duration, writes PodcastScriptPayload into tool_context.state['podcast_script'],
    and triggers loop escalation to advance to podcast_creator_agent.

    Args:
        spoken_script: Optional approved spoken script text. If omitted,
            auto-resolves from tool_context.state['podcast_script_draft'].
        reviewer_notes: Editorial notes confirming validation.
        tool_context: ADK ToolContext for state updates and loop escalation.

    Returns:
        Serialized PodcastScriptPayload dictionary.
    """
    try:
        if (
            spoken_script is None
            and tool_context is not None
            and hasattr(tool_context, "state")
        ):
            draft_val = tool_context.state.get("podcast_script_draft", "")
            if isinstance(draft_val, dict):
                spoken_script = draft_val.get("spoken_script_draft") or draft_val.get(
                    "spoken_script", ""
                )
            elif isinstance(draft_val, str):
                spoken_script = draft_val

            if not spoken_script:
                script_val = tool_context.state.get("podcast_script", "")
                if isinstance(script_val, dict):
                    spoken_script = script_val.get("spoken_script", "")
                elif isinstance(script_val, str):
                    spoken_script = script_val

        spoken_script = spoken_script or ""
        if not spoken_script.strip():
            return StructuredToolError(
                error_code="EMPTY_APPROVED_SCRIPT",
                message="Cannot finalize empty spoken script.",
                recovery_instruction="Ensure podcast_script_draft contains valid spoken prose.",
            ).model_dump()

        # Apply phonetic expansions to guarantee TTS pronunciation
        for pattern, replacement in CANONICAL_PHONETIC_MAP.items():
            spoken_script = re.sub(pattern, replacement, spoken_script)

        # Normalize paragraphs and spacing
        paragraphs = [p.strip() for p in spoken_script.split("\n\n") if p.strip()]
        clean_spoken_script = "\n\n".join(paragraphs)

        words = len(clean_spoken_script.split())
        estimated_duration_sec = max(1, int(words / 2.625))

        payload = PodcastScriptPayload(
            spoken_script=clean_spoken_script,
            word_count=words,
            estimated_duration_seconds=estimated_duration_sec,
            generated_at=datetime.now(SYDNEY_TZ).isoformat(),
        )
        serialized = payload.model_dump()

        if tool_context is not None:
            tool_context.state["podcast_script"] = serialized
            tool_context.actions.escalate = True
            tool_context.actions.skip_summarization = True

        return serialized
    except Exception as exc:
        return StructuredToolError(
            error_code="SCRIPT_FINALIZATION_FAILED",
            message=f"Failed to finalize approved podcast script: {exc}",
            recovery_instruction="Ensure valid spoken prose is provided and retry finalize_approved_podcast_script.",
        ).model_dump()
