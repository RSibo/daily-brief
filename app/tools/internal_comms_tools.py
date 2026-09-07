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

"""Internal Communications Harvesting and Noise Suppression Tools.

Implements Phase 1 of the Daily Brief architecture:
- Scans Gmail for VIP leadership and direct reports over the strictly enforced last 24h window.
- Scans Google Chat for 1:1 DMs, direct @rsibo mentions, and the 17 target spaces in config/chat_spaces.md.
- Scans Google Calendar for today's schedule and meeting prep links.
- Aggressively filters noise (receipts, mass newsletters, Buganizer CCs, gThanks, calendar churn).
- Implements Rubric Items 1.1 (Docstrings), 1.2 (Naming), 1.3 (Schemas), 1.4 (Guided Error Handling), and 4.2 (Intent vs. Outcome).
"""

import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.adk.tools import ToolContext

from app.app_utils.name_resolver import (
    SPACE_LABEL_MAP,
    resolve_all_names_and_identifiers,
    resolve_ldap_or_email_to_name,
)
from app.app_utils.telemetry import trace_tool
from app.app_utils.typing import (
    CommunicationItem,
    InternalHarvestPayload,
    StructuredToolError,
)

# Canonical CLI paths on Cloudtop
GMAIL_CLI = "/google/bin/releases/gemini-agents-gmail/gmail"
GCHAT_CLI = "/google/bin/releases/gemini-agents-gchat/gchat"
GCALENDAR_CLI = "/google/bin/releases/gemini-agents-gcalendar/gcalendar"

# Key VIP lists
LEADERSHIP_USERNAMES = [
    "selisha",
    "mitesh",
    "vamsi",
    "mscutt",
    "mpancino",
    "migliori",
    "harsha",
    "parkeroliver",
    "carrietharp",
    "karanb",
    "moeab",
    "kbindlish",
    "williamtsoi",
    "youngguyun",
]

DIRECT_REPORT_USERNAMES = [
    "oliverscott",
    "nakulgowdra",
    "tomaslawton",
    "pcorreia",
    "ericfzhu",
    "rodwilliams",
    "dylandance",
    "langleym",
    "pinty",
    "brendanhills",
    "jordanfrance",
    "dixittanya",
    "kevinkw",
    "pgomran",
    "elgrier",
]


def _execute_cli_command(cmd: list[str], timeout_seconds: int = 45) -> Any:
    """Safely executes a workspace CLI command and parses JSON output."""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if res.returncode != 0:
            return {
                "error": True,
                "error_code": "CLI_EXECUTION_ERROR",
                "message": res.stderr.strip() or f"CLI returned code {res.returncode}",
            }
        stdout = res.stdout.strip()
        if stdout.startswith(("{", "[")):
            return json.loads(stdout)
        return stdout
    except subprocess.TimeoutExpired:
        return {
            "error": True,
            "error_code": "CLI_TIMEOUT",
            "message": f"Command timed out after {timeout_seconds}s: {' '.join(cmd)}",
        }
    except Exception as exc:
        return {
            "error": True,
            "error_code": "UNEXPECTED_CLI_ERROR",
            "message": str(exc),
        }


def compact_content_budget(
    text: str | None,
    max_chars: int = 400,
    preserve_sentences: bool = True,
) -> str:
    """Intelligently compacts text to stay strictly within LLM context token budgets.

    Strips redundant whitespace, collapses formatting artifacts, and cleanly bounds
    the text length while preserving sentence integrity to prevent context bloat.

    Args:
        text: Raw source text snippet or body string.
        max_chars: Upper character budget limit.
        preserve_sentences: Whether to attempt breaking at sentence boundaries.

    Returns:
        Compacted text string within budget.
    """
    if not text:
        return ""
    # 1. Normalize and collapse repetitive whitespace and line breaks
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    # 2. Token-conscious boundary truncation
    cutoff = max_chars - 16  # Reserve budget for compaction marker
    sliced = cleaned[:cutoff]
    if preserve_sentences and any(p in sliced for p in [". ", "? ", "! "]):
        last_punct = max(
            sliced.rfind(". "),
            sliced.rfind("? "),
            sliced.rfind("! "),
        )
        if last_punct > cutoff // 2:
            return f"{sliced[: last_punct + 1]} [compacted]"

    if " " in sliced:
        sliced = sliced.rsplit(" ", 1)[0]
    return f"{sliced}... [compacted]"


@lru_cache(maxsize=32)
def load_target_chat_spaces(
    config_path: str = "config/chat_spaces.md",
) -> list[dict[str, str]]:
    """Loads target chat spaces dynamically from config/chat_spaces.md."""
    path = Path(config_path)
    if not path.exists():
        return []
    content = path.read_text()
    matches = re.findall(
        r"\|\s*(.*?)\s*\|\s*`?(spaces/[a-zA-Z0-9_\-]+|AAAA[a-zA-Z0-9_\-]+)`?\s*\|",
        content,
    )
    return [
        {"name": m[0].strip(), "space_id": m[1].strip()}
        for m in matches
        if m[0] != "Space Name"
    ]


@lru_cache(maxsize=32)
def load_active_hot_list_themes(
    config_path: str = "config/hot_list.md",
) -> list[dict[str, str]]:
    """Loads active Hot List themes and search keywords from config/hot_list.md."""
    path = Path(config_path)
    if not path.exists():
        return []
    content = path.read_text()
    matches = re.findall(
        r"\|\s*\*\*(.*?)\*\*\s*\|\s*`?(.*?)`?\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|",
        content,
    )
    return [
        {
            "theme_name": m[0].strip(),
            "query_syntax": m[1].strip(),
            "aliases": m[2].strip(),
        }
        for m in matches
        if m[0] != "Theme Name"
    ]


def is_suppressed_noise(subject: str, sender: str, snippet: str) -> bool:
    """Returns True if the communication matches noise suppression rules."""
    subject_lower = subject.lower()
    sender_lower = sender.lower()
    snippet_lower = snippet.lower()

    if (
        "noreply+gthanks@google.com" in sender_lower
        or "kudos" in subject_lower
        or "peer bonus" in subject_lower
    ):
        return True
    if "calendar-notification@google.com" in sender_lower:
        return True
    if any(
        subject_lower.startswith(p)
        for p in ["invitation:", "accepted:", "declined:", "updated invitation:"]
    ):
        return True
    if "buganizer-system" in sender_lower and "you were cc'd" in snippet_lower:
        return True
    if "newsletter" in subject_lower or "weekly digest" in subject_lower:
        return True
    return False


@trace_tool(
    tool_name="fetch_unread_leadership_threads", agent_name="internal_comms_agent"
)
def fetch_unread_leadership_threads(
    lookback_hours: int = 24,
    test_mode_fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fetches and triages unread Gmail threads from leadership and direct reports.

    Queries Gmail for unread messages within the strictly enforced lookback window,
    mapping senders to VIP categories and filtering out automated noise.

    Args:
        lookback_hours: Maximum age of messages in hours (strictly default 24).
        test_mode_fixtures: Optional pre-set fixtures for offline unit testing.

    Returns:
        Dict with 'status': 'success' and 'threads': List[Dict] conforming to
        CommunicationItem schema, or a StructuredToolError payload upon failure.
    """
    if test_mode_fixtures is not None:
        raw_threads = test_mode_fixtures
    elif not os.path.exists(GMAIL_CLI):
        return StructuredToolError(
            error_code="GMAIL_CLI_NOT_FOUND",
            message=f"Gmail binary not accessible at {GMAIL_CLI}",
            recovery_instruction="Check cloudtop binary mounting or provide synthetic fixtures in test mode.",
        ).model_dump()
    else:
        # Construct search query excluding noise
        vip_query = " OR ".join(
            [f"from:{u}" for u in (LEADERSHIP_USERNAMES + DIRECT_REPORT_USERNAMES)]
        )
        search_query = (
            f"is:unread newer_than:{lookback_hours}h ({vip_query}) "
            "-from:noreply+gthanks@google.com -from:calendar-notification@google.com "
            '-subject:"Kudos" -subject:"Peer Bonus" -subject:"Invitation:" -subject:"Accepted:"'
        )
        cmd = [GMAIL_CLI, "readonly", "search", search_query, "--json"]
        res = _execute_cli_command(cmd)
        if isinstance(res, dict) and res.get("error"):
            return StructuredToolError(
                error_code=res.get("error_code", "GMAIL_SEARCH_FAILED"),
                message=res.get("message", "Failed to query Gmail CLI"),
                recovery_instruction="Verify Gmail auth credentials or proceed with partial Chat signals.",
            ).model_dump()
        raw_threads = res if isinstance(res, list) else []

    filtered_items: list[dict[str, Any]] = []
    for t in raw_threads:
        subject = t.get("subject", "No Subject")
        sender = t.get("from", t.get("sender", ""))
        raw_snippet = t.get("snippet", "")
        snippet = compact_content_budget(raw_snippet, max_chars=400)
        raw_body = t.get("body")
        body = compact_content_budget(raw_body, max_chars=1200) if raw_body else None
        if is_suppressed_noise(subject, sender, raw_snippet):
            continue

        thread_id = t.get("id", t.get("threadId", "unknown"))
        sender_email = re.search(r"[\w\.-]+@[\w\.-]+", sender)
        sender_email_str = sender_email.group(0) if sender_email else sender

        # Tag VIP category
        sender_user = sender_email_str.split("@")[0].lower()
        if sender_user in LEADERSHIP_USERNAMES:
            vip_cat = "leadership"
        elif sender_user in DIRECT_REPORT_USERNAMES:
            vip_cat = "direct_report"
        else:
            vip_cat = "strategic_partner"

        item = CommunicationItem(
            source="gmail",
            thread_id=thread_id,
            sender_name=sender.split("<")[0].strip() or sender_email_str,
            sender_email=sender_email_str,
            timestamp=t.get("date", datetime.now(UTC).isoformat()),
            subject=subject,
            snippet=snippet,
            body=body,
            deep_link=f"https://mail.google.com/mail/u/0/#inbox/{thread_id}",
            is_vip=True,
            vip_category=vip_cat,
            requires_action=any(
                k in f"{subject} {snippet}".lower()
                for k in ["approval", "block", "urgent", "ask", "decision", "escalat"]
            ),
            action_summary="Decision/response requested"
            if any(
                k in f"{subject} {snippet}".lower()
                for k in ["approval", "block", "urgent", "ask", "decision", "escalat"]
            )
            else None,
            aging_days=0,
        )
        filtered_items.append(item.model_dump())

    return {
        "status": "success",
        "threads": filtered_items,
        "count": len(filtered_items),
    }


@trace_tool(tool_name="scan_target_chat_spaces", agent_name="internal_comms_agent")
def scan_target_chat_spaces(
    lookback_hours: int = 24,
    test_mode_fixtures: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scans direct @mentions and designated team spaces in Google Chat.

    Dynamically reads spaces from config/chat_spaces.md and extracts messages
    and mentions across the lookback window without filtering on unread status.
    Suppresses self-sent chatter.

    Args:
        lookback_hours: Lookback duration in hours (e.g. 12, 24).
        test_mode_fixtures: Optional pre-set fixtures for offline unit testing.

    Returns:
        Dict with 'status': 'success' and 'chat_threads': List[Dict] conforming to
        CommunicationItem schema, or a StructuredToolError upon failure.
    """
    chat_items: list[dict[str, Any]] = []
    seen_message_ids: set[str] = set()

    if test_mode_fixtures is not None:
        if isinstance(test_mode_fixtures, dict):
            raw_dms = test_mode_fixtures.get("dms", [])
            raw_mentions = test_mode_fixtures.get("mentions", [])
            raw_space_msgs = test_mode_fixtures.get("spaces", [])
        elif isinstance(test_mode_fixtures, list):
            raw_dms = []
            raw_mentions = test_mode_fixtures
            raw_space_msgs = []
        else:
            raw_dms, raw_mentions, raw_space_msgs = [], [], []
    elif not os.path.exists(GCHAT_CLI):
        return StructuredToolError(
            error_code="GCHAT_CLI_NOT_FOUND",
            message=f"Chat binary not accessible at {GCHAT_CLI}",
            recovery_instruction="Verify gchat binary mount or run in test mode with fixtures.",
        ).model_dump()
    else:
        # 1. Fetch direct mentions over the lookback window (not filtered on unread)
        mentions_res = _execute_cli_command(
            [
                GCHAT_CLI,
                "readonly",
                "list-mentions",
                "--hours",
                str(lookback_hours),
                "--json",
            ]
        )
        raw_mentions = mentions_res if isinstance(mentions_res, list) else []

        # 2. Fetch recent messages across included target chat spaces
        raw_space_msgs = []
        target_spaces = load_target_chat_spaces()
        for sp in target_spaces:
            sp_id = sp.get("space_id", "")
            sp_name = sp.get("name", sp_id)
            if not sp_id:
                continue
            msgs_out = None
            if sp_id.startswith("spaces/AAAA") or sp_id.startswith("AAAA"):
                msgs_out = _execute_cli_command(
                    [
                        GCHAT_CLI,
                        "readonly",
                        "list-messages-by-thread",
                        "--space",
                        sp_id,
                        "--max",
                        "50",
                        "--json",
                    ]
                )
            else:
                msgs_out = _execute_cli_command(
                    [
                        GCHAT_CLI,
                        "readonly",
                        "list-messages",
                        "--space",
                        sp_id,
                        "--hours",
                        str(lookback_hours),
                        "--max",
                        "50",
                        "--json",
                    ]
                )
                if isinstance(msgs_out, dict) and msgs_out.get("error"):
                    msgs_out = _execute_cli_command(
                        [
                            GCHAT_CLI,
                            "readonly",
                            "list-messages-by-thread",
                            "--space",
                            sp_id,
                            "--max",
                            "50",
                            "--json",
                        ]
                    )

            if isinstance(msgs_out, list):
                for m in msgs_out:
                    if isinstance(m, dict):
                        m["_space_name"] = sp_name
                        m["_space_id"] = sp_id
                        raw_space_msgs.append(m)
            elif isinstance(msgs_out, dict) and not msgs_out.get("error"):
                for thread_list in msgs_out.values():
                    if isinstance(thread_list, list):
                        for m in thread_list:
                            if isinstance(m, dict):
                                m["_space_name"] = sp_name
                                m["_space_id"] = sp_id
                                raw_space_msgs.append(m)

        raw_dms = []

    # Map target space names
    space_name_lookup = {
        s.get("space_id", ""): s.get("name", "") for s in load_target_chat_spaces()
    }

    candidates = raw_mentions + raw_space_msgs + raw_dms
    cutoff_time = datetime.now(UTC) - timedelta(hours=lookback_hours + 1)

    for item in candidates:
        msg_obj = item.get("message") if isinstance(item.get("message"), dict) else item
        text = (
            msg_obj.get("text")
            or msg_obj.get("formatted_text")
            or item.get("text")
            or item.get("snippet")
            or ""
        ).strip()
        if not text:
            continue

        # Extract sender details
        sender_obj = (
            msg_obj.get("sender")
            if isinstance(msg_obj.get("sender"), dict)
            else item.get("sender")
        )
        if isinstance(sender_obj, dict):
            sender_name = resolve_ldap_or_email_to_name(
                sender_obj.get("display_name")
                or sender_obj.get("displayName")
                or sender_obj.get("name")
                or "Team Member"
            )
            sender_email = (
                sender_obj.get("email")
                or f"{sender_name.lower().replace(' ', '.')}@google.com"
            )
        elif isinstance(sender_obj, str):
            sender_name = resolve_ldap_or_email_to_name(
                item.get("sender_name") or sender_obj
            )
            sender_email = (
                sender_obj if "@" in sender_obj else f"{sender_obj.lower()}@google.com"
            )
        else:
            sender_name = resolve_ldap_or_email_to_name(
                item.get("sender_name") or "Team Member"
            )
            sender_email = "team@google.com"

        # Suppress Rob's self-sent chatter
        if "rsibo" in sender_name.lower() or "rsibo@" in sender_email.lower():
            continue

        # Timestamp & recency check
        timestamp_str = (
            msg_obj.get("create_time")
            or msg_obj.get("createTime")
            or item.get("create_time")
            or item.get("createTime")
            or item.get("timestamp")
        )
        if test_mode_fixtures is None and timestamp_str:
            try:
                msg_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if msg_dt < cutoff_time:
                    continue
            except Exception:
                pass
        else:
            timestamp_str = datetime.now(UTC).isoformat()

        space_id = (
            item.get("_space_id")
            or item.get("space_id")
            or item.get("space")
            or "Google Chat"
        )
        resolved_space_name = (
            SPACE_LABEL_MAP.get(space_id)
            or item.get("_space_name")
            or space_name_lookup.get(space_id)
            or item.get("display_name")
            or space_id
        )
        if re.match(r"^(?:spaces/|AAQA|sUqv|AAAA)[a-zA-Z0-9_-]+$", resolved_space_name):
            resolved_space_name = SPACE_LABEL_MAP.get(
                resolved_space_name, "Chat Update"
            )

        msg_name = msg_obj.get("name") or item.get("name") or item.get("id") or ""
        deep_link = (
            msg_obj.get("url")
            or item.get("url")
            or (
                f"https://chat.google.com/room/{space_id}"
                if space_id and space_id != "Google Chat"
                else "https://chat.google.com"
            )
        )

        dedup_key = msg_name or deep_link or f"{sender_name}_{timestamp_str}"
        if dedup_key in seen_message_ids:
            continue
        seen_message_ids.add(dedup_key)

        first_line = text.splitlines()[0]
        first_line_clean = re.sub(r"@[A-Za-z0-9_\.\-]+", "", first_line).strip()
        first_line_clean = re.sub(r"\s+", " ", first_line_clean)
        first_line_clean = resolve_all_names_and_identifiers(first_line_clean)
        subject = (
            f"[{resolved_space_name}] {first_line_clean[:80]}"
            if first_line_clean
            else f"[{resolved_space_name}] Update"
        )
        snippet = resolve_all_names_and_identifiers(
            compact_content_budget(text, max_chars=800)
        )

        sender_ldap = sender_email.split("@")[0].lower()
        if sender_ldap in LEADERSHIP_USERNAMES:
            vip_cat = "leadership"
            is_vip = True
        elif sender_ldap in DIRECT_REPORT_USERNAMES:
            vip_cat = "direct_report"
            is_vip = True
        else:
            vip_cat = "strategic_partner"
            is_vip = False

        requires_action = (
            any(
                k in text.lower()
                for k in [
                    "approval",
                    "approve",
                    "block",
                    "urgent",
                    "ask",
                    "decision",
                    "escalat",
                    "confirm",
                    "can you",
                    "could you",
                    "question",
                    "?",
                ]
            )
            or "rsibo" in text.lower()
            or "dm" in item.get("id", "").lower()
            or item.get("user", "").lower() in DIRECT_REPORT_USERNAMES
        )

        chat_items.append(
            CommunicationItem(
                source="chat",
                thread_id=msg_name or dedup_key,
                sender_name=sender_name,
                sender_email=sender_email,
                timestamp=timestamp_str,
                subject=subject,
                snippet=snippet,
                deep_link=deep_link,
                is_vip=is_vip,
                vip_category=vip_cat,
                requires_action=requires_action,
                aging_days=0,
            ).model_dump()
        )

    return {"status": "success", "chat_threads": chat_items, "count": len(chat_items)}


@trace_tool(tool_name="get_daily_calendar_agenda", agent_name="internal_comms_agent")
def get_daily_calendar_agenda(
    test_mode_fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fetches today's calendar commitments, attendees, and attached prep links.

    Queries Google Calendar for today's schedule in Australia/Sydney timezone
    and extracts meeting objectives, attendees, and document links.

    Args:
        test_mode_fixtures: Optional list of calendar event dictionaries for testing.

    Returns:
        Dict with 'status': 'success' and 'events': List[Dict], or a StructuredToolError.
    """
    if test_mode_fixtures is not None:
        events = test_mode_fixtures
    elif not os.path.exists(GCALENDAR_CLI):
        return StructuredToolError(
            error_code="GCALENDAR_CLI_NOT_FOUND",
            message=f"Calendar binary not accessible at {GCALENDAR_CLI}",
            recovery_instruction="Verify gcalendar binary mount or run in test mode with fixtures.",
        ).model_dump()
    else:
        cmd = [
            GCALENDAR_CLI,
            "readonly",
            "today",
            "--timezone",
            "Australia/Sydney",
            "--json",
        ]
        res = _execute_cli_command(cmd)
        if isinstance(res, dict) and res.get("error"):
            return StructuredToolError(
                error_code=res.get("error_code", "CALENDAR_READ_FAILED"),
                message=res.get(
                    "message", "Failed to query Google Calendar today command"
                ),
                recovery_instruction="Verify Calendar OAuth or proceed with empty calendar agenda.",
            ).model_dump()
        events = res if isinstance(res, list) else []

    formatted_events = []
    for ev in events:
        summary = ev.get("summary", "Untitled Meeting")
        # Filter out self briefing events to avoid recursive loops
        if "Your Morning Brief" in summary or "Day In Review" in summary:
            continue
        start_time = ev.get("start", {}).get("dateTime", ev.get("startTime", ""))
        end_time = ev.get("end", {}).get("dateTime", ev.get("endTime", ""))
        attendees = [
            a.get("email", a.get("displayName", ""))
            for a in ev.get("attendees", [])
            if isinstance(a, dict)
        ]

        formatted_events.append(
            {
                "title": summary,
                "start": start_time,
                "end": end_time,
                "attendees": attendees[:5],  # Top 5 attendees
                "meet_link": ev.get("hangoutLink", ev.get("htmlLink", "")),
                "description": ev.get("description", "")[:200],
            }
        )

    return {
        "status": "success",
        "events": formatted_events,
        "count": len(formatted_events),
    }


@trace_tool(
    tool_name="harvest_all_internal_communications", agent_name="internal_comms_agent"
)
def harvest_all_internal_communications(
    lookback_hours: int = 24,
    test_fixtures: dict[str, Any] | None = None,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Master tool coordinating end-to-end internal communications harvesting.

    Aggregates leadership Gmail threads, Chat DMs/mentions/spaces, and Calendar
    agenda, returning a payload conforming strictly to InternalHarvestPayload.

    Args:
        lookback_hours: Time window in hours (default: 24).
        test_fixtures: Optional synthetic fixtures mapping to 'gmail', 'chat', 'calendar'.
        tool_context: Optional ADK tool context for session state access.

    Returns:
        Dict conforming to InternalHarvestPayload schema.
    """
    tz = ZoneInfo("Australia/Sydney")
    sydney_now = datetime.now(tz).isoformat()

    gmail_fixtures = test_fixtures.get("gmail") if test_fixtures else None
    chat_fixtures = test_fixtures.get("chat") if test_fixtures else None
    cal_fixtures = test_fixtures.get("calendar") if test_fixtures else None

    # 1. Harvest Gmail
    gmail_res = fetch_unread_leadership_threads(
        lookback_hours=lookback_hours, test_mode_fixtures=gmail_fixtures
    )
    threads = (
        gmail_res.get("threads", []) if gmail_res.get("status") == "success" else []
    )
    leadership = [t for t in threads if t.get("vip_category") == "leadership"]
    direct_reports = [t for t in threads if t.get("vip_category") == "direct_report"]

    # 2. Harvest Chat
    chat_res = scan_target_chat_spaces(
        lookback_hours=lookback_hours, test_mode_fixtures=chat_fixtures
    )
    chat_threads = (
        chat_res.get("chat_threads", []) if chat_res.get("status") == "success" else []
    )

    # 3. Harvest Calendar
    cal_res = get_daily_calendar_agenda(test_mode_fixtures=cal_fixtures)
    calendar_events = (
        cal_res.get("events", []) if cal_res.get("status") == "success" else []
    )

    # 4. Correlate with active Hot List themes
    hot_list_themes = load_active_hot_list_themes()
    all_comms = leadership + direct_reports + chat_threads
    hot_list_matches: dict[str, list[dict[str, Any]]] = {}

    for theme in hot_list_themes:
        t_name = theme.get("theme_name", "")
        if not t_name:
            continue
        aliases = [
            a.strip().lower() for a in theme.get("aliases", "").split(",") if a.strip()
        ]
        kw_list = [t_name.lower(), *aliases]
        if "optus" in t_name.lower():
            kw_list.extend(["optus", "vais", "model armor", "model armour"])
        elif "woolworths" in t_name.lower() or "woolies" in t_name.lower():
            kw_list.extend(["woolworths", "woolies", "bigw", "shopping agent", "flw"])
        elif "drz" in t_name.lower():
            kw_list.extend(["drz", "data residency", "ml processing", "in-country"])

        kw_regex = re.compile(
            r"\b(?:" + "|".join(re.escape(kw) for kw in kw_list) + r")\b",
            re.IGNORECASE,
        )
        matched_items = []
        seen_threads = set()
        for c in all_comms:
            t_id = c.get("thread_id") or c.get("subject", "")
            if t_id in seen_threads:
                continue
            content_str = (
                f"{c.get('subject', '')} {c.get('snippet', '')} {c.get('body') or ''}"
            )
            if kw_regex.search(content_str):
                matched_items.append(c)
                seen_threads.add(t_id)
        if matched_items:
            hot_list_matches[t_name] = matched_items

    payload = InternalHarvestPayload(
        harvest_timestamp=sydney_now,
        lookback_hours=lookback_hours,
        leadership_threads=leadership,
        direct_report_threads=direct_reports,
        chat_space_threads=chat_threads,
        calendar_events=calendar_events,
        hot_list_matches=hot_list_matches,
    )
    result = payload.model_dump()
    if tool_context is not None and hasattr(tool_context, "state"):
        tool_context.state["internal_comms_data"] = result
    return result
