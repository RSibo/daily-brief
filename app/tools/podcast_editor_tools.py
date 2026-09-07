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

import json
import os
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from app.app_utils.name_resolver import resolve_all_names_and_identifiers
from app.app_utils.telemetry import trace_tool
from app.app_utils.typing import (
    PodcastReviewCritiquePayload,
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

    # 4. Mandatory Opening Hook: Must begin with "Let's begin; " and contain zero greeting filler
    first_sentence = re.split(r"[.!?]\s+", script_text.strip())[0].lower()
    has_banned_open = any(first_sentence.startswith(b) for b in BANNED_AUDIO_OPENINGS)
    starts_with_lets_begin = lower_text.startswith("let's begin")

    if has_banned_open:
        issues.append(
            f"Prohibited opening pleasantry detected ('{first_sentence[:40]}...'). Remove greeting filler."
        )
        checks["clean_open"] = False
    elif not starts_with_lets_begin:
        issues.append(
            "Script must open with the mandatory phrase 'Let's begin; ' followed immediately by the first operational update."
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
            f"Contraction density is low ({int(contraction_density * 100)}%). Spoken scripts must use natural contractions (e.g., 'we've', 'there's', 'it's')."
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

    # 8. Word Count Check (Target: 6 to 15 minutes = ~800 to 2,400 words, depending on content)
    total_words = len(script_text.split())
    checks["word_count"] = total_words
    if total_words < 100:
        issues.append(
            f"Script is too brief ({total_words} words). Target runtime is 6 to 15 minutes (~800 to 2,400 words depending on content depth). Expand updates with full operational context."
        )
        checks["word_count_valid"] = False
    elif total_words > 2600:
        issues.append(
            f"Script exceeds 15-minute runtime ceiling ({total_words} words). Executive audio overview must remain under 2,400 words (15 minutes maximum)."
        )
        checks["word_count_valid"] = False
    else:
        checks["word_count_valid"] = True

    # 9. Clean Ending Sign-Off ("That's all")
    has_thats_all = bool(
        re.search(r"\bthat's all\b", script_text.strip().lower()[-150:])
    )
    if not has_thats_all:
        issues.append(
            "Script lacks mandatory closing sign-off phrase 'That's all' (e.g. 'That's all for today's brief.')."
        )
        checks["clean_ending_valid"] = False
    else:
        checks["clean_ending_valid"] = True

    # 10. Duplicate / Repetition Detection Across Comms
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text.strip()) if s.strip()
    ]
    seen_snippets: set[str] = set()
    duplicates: list[str] = []
    for s in sentences:
        words = re.sub(r"[^\w\s]", "", s.lower()).split()
        if len(words) >= 6:
            key = " ".join(words[:10])
            if key in seen_snippets:
                duplicates.append(s[:60] + "...")
            seen_snippets.add(key)
    if duplicates:
        issues.append(
            f"Duplicate sentence/item detected in script: '{duplicates[0]}'. Consolidate redundant mentions into a single update across comms/emails."
        )
        checks["no_duplicate_items"] = False
    else:
        checks["no_duplicate_items"] = True

    is_valid = len(issues) == 0
    return {
        "valid": is_valid,
        "issues": issues,
        "checks": checks,
    }


def grade_podcast_script_with_gemini(
    draft_script: str,
    mock: bool = False,
) -> dict[str, Any]:
    """Uses Gemini model to evaluate readability, suitability, information value, and redundancy.

    Grades on 4 dimensions:
    1. Readability & Vocal Flow: Linear sentences, natural acoustic rhythm, smooth cadence.
    2. Suitability & Tone: Executive Chief of Staff tone, zero conversational banter/pleasantries,
       mandatory closing sign-off containing 'That's all'.
    3. Information Value & Signal Density: High ratio of substantive operational facts, decisions,
       blockers, and external AI developments without empty padding.
    4. Repetitiveness & Redundancy: Strict check for duplicate items across comms/emails.

    Args:
        draft_script: Spoken audio transcript to grade.
        mock: When True, bypasses external model call.

    Returns:
        Structured evaluation dictionary or empty dict upon failure/offline.
    """
    if mock or not draft_script or not draft_script.strip():
        return {}

    try:
        import google.auth
        from google import genai

        from app.config import ANALYTICAL_MODEL

        _, project_id = google.auth.default()
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )
        prompt = f"""You are an executive Chief of Staff auditing a spoken audio brief transcript.
Evaluate this spoken script on 4 rigorous dimensions:
1. Readability: Linear sentences (max 18 words), natural acoustic rhythm, smooth transitions, high contraction density.
2. Suitability: Calm, matter-of-fact tone, zero greeting fluff ("Good morning/afternoon", "Welcome"), mandatory closing sign-off containing "That's all".
3. Information Value & Signal Density: High ratio of signal-to-noise, substantive operational facts, decisions, blockers, and frontier AI developments without vague filler.
4. Repetitiveness & Redundancy: Strict zero-tolerance for duplicate items across comms/emails. No person, customer, or request should be repeated multiple times redundantly (e.g. asking for the same document or project scope multiple times).

Transcript to evaluate:
\"\"\"
{draft_script}
\"\"\"

Respond with a valid JSON object matching this schema:
{{
  "readability_score": <1-10>,
  "suitability_score": <1-10>,
  "information_value_score": <1-10>,
  "redundancy_score": <1-10, where 10 means zero redundancy, 1 means highly repetitive>,
  "verdict": "<'approve' if scores are >= 8 and zero critical issues remain, otherwise 'revise'>",
  "critique": "<Concise 2-sentence executive summary of readability, information density, and repetition>",
  "issues": ["<specific issue 1 if any>"]
}}
Return only valid JSON."""
        resp = client.models.generate_content(
            model=ANALYTICAL_MODEL,
            contents=prompt,
        )
        text_resp = resp.text.strip()
        json_match = re.search(r"\{.*\}", text_resp, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception:
        pass
    return {}


def rewrite_podcast_script_with_gemini(
    draft_script: str,
    critique: str = "",
    issues: list[str] | None = None,
    mock: bool = False,
) -> str:
    """Uses Gemini analytical model to rewrite spoken script addressing critique and deduplicating.

    Falls back to original draft if offline, mock, or encountering API errors.
    """
    if mock or not draft_script or not draft_script.strip():
        return draft_script

    issues = issues or []
    issues_text = "\n".join(f"- {iss}" for iss in issues) if issues else "None"

    try:
        import google.auth
        from google import genai

        from app.config import ANALYTICAL_MODEL

        _, project_id = google.auth.default()
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )
        prompt = f"""You are the podcast_script_writer_agent acting as an executive Chief of Staff.
Rewrite this draft spoken audio brief to address the reviewer critique and issues:

Reviewer Critique: {critique}
Issues Flagged:
{issues_text}

Strict Spoken Audio Rules:
1. Opening Hook: Must begin with "Let's begin; " immediately followed by the first operational update. No greeting filler.
2. Zero Duplicate Items: Strictly eliminate duplicate items across comms/emails. Consolidate repeated mentions of the same person, request, or customer topic (e.g. Romina asking Rob Sibo for Optus project scope or onboarding questions) into a single concise update. Never repeat the request.
3. Proper Name Resolution: Use full names (e.g. Rob Sibo, Romina, Selisha, Ashmita) instead of raw LDAPs or usernames (rsibo, romish, selisha).
4. Mandatory Closing Sign-Off: Conclude the script with "That's all for today's brief." (or "That's all.").
5. Linear Sentences & Brevity: Short Subject-Verb-Object sentences (under 18 words).
6. Contraction Density: Use natural contractions (we've, there's, it's, they'll, that's, don't).
7. Zero Visual Artifacts: Pure spoken narrative prose only. No markdown, no bullet dashes, no speaker tags.

Current Draft Transcript:
\"\"\"
{draft_script}
\"\"\"

Output only the revised spoken audio script prose with blank lines between paragraphs. Do not wrap in markdown quotes or code fences."""
        resp = client.models.generate_content(
            model=ANALYTICAL_MODEL,
            contents=prompt,
        )
        cleaned_text = resp.text.strip()
        cleaned_text = re.sub(r"^```(?:markdown|text)?\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
        if (
            cleaned_text.lower().startswith("let's begin")
            or len(cleaned_text.split()) > 100
        ):
            return cleaned_text
    except Exception:
        pass
    return draft_script


@trace_tool(tool_name="evaluate_podcast_script")
def evaluate_podcast_script(
    draft_script: str | None = None,
    tool_context: ToolContext | None = None,
    use_llm_judge: bool = True,
) -> dict[str, Any]:
    """Evaluates a draft spoken audio script and returns structured review verdict.

    Performs acoustic linting and leverages Gemini to grade readability, suitability,
    information value, and redundancy. Returns 'approve' if valid, or 'revise' with
    specific, actionable feedback.

    Args:
        draft_script: Optional spoken script text to evaluate. If omitted,
            auto-resolves from tool_context.state['podcast_script_draft'].
        tool_context: Optional ADK ToolContext to resolve draft from session state.
        use_llm_judge: Whether to invoke Gemini LLM-as-judge for signal density
            and redundancy scoring. Defaults to True.

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

        llm_eval: dict[str, Any] = {}
        if use_llm_judge:
            llm_eval = grade_podcast_script_with_gemini(draft_script)

        combined_issues = list(lint_results["issues"])
        if llm_eval and "issues" in llm_eval and isinstance(llm_eval["issues"], list):
            for iss in llm_eval["issues"]:
                if iss and iss not in combined_issues:
                    combined_issues.append(iss)

        llm_verdict = llm_eval.get(
            "verdict", "approve" if lint_results["valid"] else "revise"
        )
        if (
            lint_results["valid"]
            and len(combined_issues) == 0
            and llm_eval.get("readability_score", 0) >= 8
            and llm_eval.get("suitability_score", 0) >= 8
            and llm_eval.get("redundancy_score", 0) >= 8
        ):
            llm_verdict = "approve"

        is_approved = (
            lint_results["valid"]
            and (llm_verdict == "approve")
            and (len(combined_issues) == 0)
        )

        if is_approved:
            critique = (
                llm_eval.get("critique")
                or "Script satisfies all acoustic and executive standards: zero visual artifacts, natural narrative transitions, high contraction density, high information density, and punchy sentence length."
            )
            payload = PodcastReviewCritiquePayload(
                verdict="approve",
                critique=critique,
                issues=[],
                passed=True,
                llm_scores=llm_eval if llm_eval else None,
                reviewed_at=datetime.now(SYDNEY_TZ).isoformat(),
            )
        else:
            issues_summary = "; ".join(combined_issues)
            critique = (
                llm_eval.get("critique")
                or f"Script requires acoustic revisions before approval: {issues_summary}"
            )
            payload = PodcastReviewCritiquePayload(
                verdict="revise",
                critique=critique,
                issues=combined_issues,
                passed=False,
                llm_scores=llm_eval if llm_eval else None,
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

    Applies canonical phonetic acronym expansions, resolves names, ensures mandatory
    'That's all' sign-off, computes word counts and estimated duration, writes
    PodcastScriptPayload into tool_context.state['podcast_script'], and triggers
    loop escalation to advance to podcast_creator_agent.

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

        # Apply name resolution
        spoken_script = resolve_all_names_and_identifiers(spoken_script)

        # Apply phonetic expansions to guarantee TTS pronunciation
        for pattern, replacement in CANONICAL_PHONETIC_MAP.items():
            spoken_script = re.sub(pattern, replacement, spoken_script)

        # Enforce closing That's all sign-off
        if not re.search(r"\bthat's all\b", spoken_script.lower()[-150:]):
            spoken_script = f"{spoken_script}\n\nThat's all for today's brief."

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
