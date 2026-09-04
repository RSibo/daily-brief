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

"""Unit tests for Phase 1 Internal Comms Harvest Agent and tools."""

import inspect

from app.sub_agents.internal_comms_agent import internal_comms_agent
from app.tools.internal_comms_tools import (
    fetch_unread_leadership_threads,
    get_daily_calendar_agenda,
    harvest_all_internal_communications,
    is_suppressed_noise,
    scan_target_chat_spaces,
)


def test_noise_suppression_logic():
    """Verifies that automated receipts, gThanks, Buganizer CCs, and calendar churn are dropped."""
    assert is_suppressed_noise(
        "Thanks for your work", "noreply+gthanks@google.com", "You received a kudos"
    )
    assert is_suppressed_noise(
        "Accepted: Sync", "calendar-notification@google.com", "Accepted your invitation"
    )
    assert is_suppressed_noise("Declined: Sync", "test@google.com", "Declined")
    assert is_suppressed_noise(
        "Issue 123456", "buganizer-system@google.com", "You were CC'd on this issue"
    )
    assert is_suppressed_noise(
        "Google Cloud Weekly Digest", "news@google.com", "Newsletter content"
    )

    # Legitimate emails must NOT be suppressed
    assert not is_suppressed_noise(
        "Q3 AI GTM Strategy", "selisha@google.com", "Let's review the staffing model"
    )
    assert not is_suppressed_noise(
        "Optus Blocker Update",
        "oliverscott@google.com",
        "We need an approval on this ask",
    )


def test_fetch_unread_leadership_threads_with_fixtures():
    """Verifies Gmail harvester filters noise and tags VIP categories."""
    fixtures = [
        {
            "id": "thread_lead_1",
            "from": "Simon Elisha <selisha@google.com>",
            "subject": "Q3 Priorities",
            "snippet": "Need an urgent approval on this team ask.",
            "date": "2026-09-04T07:00:00Z",
        },
        {
            "id": "thread_dr_1",
            "from": "Ollie Scott <oliverscott@google.com>",
            "subject": "Optus VAIS Escalation",
            "snippet": "Customer is blocked on Model Armor configuration.",
            "date": "2026-09-04T07:15:00Z",
        },
        {
            "id": "thread_spam",
            "from": "Kudos <noreply+gthanks@google.com>",
            "subject": "You received a Peer Bonus!",
            "snippet": "Congratulations!",
            "date": "2026-09-04T06:00:00Z",
        },
    ]

    res = fetch_unread_leadership_threads(
        lookback_hours=24, test_mode_fixtures=fixtures
    )
    assert res["status"] == "success"
    threads = res["threads"]
    assert len(threads) == 2  # Spam dropped

    lead_thread = next(t for t in threads if t["thread_id"] == "thread_lead_1")
    assert lead_thread["vip_category"] == "leadership"
    assert lead_thread["requires_action"] is True
    assert "https://mail.google.com" in lead_thread["deep_link"]

    dr_thread = next(t for t in threads if t["thread_id"] == "thread_dr_1")
    assert dr_thread["vip_category"] == "direct_report"
    assert dr_thread["requires_action"] is True


def test_scan_target_chat_spaces_with_fixtures():
    """Verifies Chat harvester extracts DMs, @mentions, and drops self-sent messages."""
    fixtures = {
        "dms": [
            {
                "id": "dm_1",
                "sender": "Pedro Correia",
                "user": "pcorreia",
                "text": "Hey Rob, quick question on the Woolies DP Agent architecture.",
                "createTime": "2026-09-04T06:30:00Z",
            },
            {
                "id": "dm_self",
                "sender": "rsibo",
                "user": "rsibo",
                "text": "I sent this to myself",
                "createTime": "2026-09-04T06:00:00Z",
            },
        ],
        "mentions": [
            {
                "id": "mention_1",
                "sender": "Vamsi Ramakrishnan",
                "space": "spaces/AAQAWmL5O_g",
                "text": "@rsibo please review this regional AI announcement.",
                "createTime": "2026-09-04T05:00:00Z",
            }
        ],
    }

    res = scan_target_chat_spaces(lookback_hours=24, test_mode_fixtures=fixtures)
    assert res["status"] == "success"
    chat_threads = res["chat_threads"]
    assert len(chat_threads) == 2  # Self-DM dropped

    dm_item = next(c for c in chat_threads if "Pedro" in c["sender_name"])
    assert dm_item["source"] == "chat"
    assert dm_item["requires_action"] is True

    mention_item = next(c for c in chat_threads if "Vamsi" in c["sender_name"])
    assert "AAQAWmL5O_g" in mention_item["deep_link"]


def test_get_daily_calendar_agenda_with_fixtures():
    """Verifies calendar reader extracts today's schedule and suppresses briefing events."""
    fixtures = [
        {
            "summary": "AuNZ AI CE LT Weekly Sync",
            "start": {"dateTime": "2026-09-04T09:00:00+10:00"},
            "end": {"dateTime": "2026-09-04T10:00:00+10:00"},
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "attendees": [
                {"email": "selisha@google.com"},
                {"email": "rsibo@google.com"},
            ],
        },
        {
            "summary": "Your Morning Brief",
            "start": {"dateTime": "2026-09-04T06:00:00+10:00"},
            "end": {"dateTime": "2026-09-04T06:30:00+10:00"},
        },
    ]

    res = get_daily_calendar_agenda(test_mode_fixtures=fixtures)
    assert res["status"] == "success"
    events = res["events"]
    assert len(events) == 1  # "Your Morning Brief" suppressed
    assert events[0]["title"] == "AuNZ AI CE LT Weekly Sync"
    assert "https://meet.google.com" in events[0]["meet_link"]


def test_harvest_all_internal_communications_contract():
    """Verifies end-to-end master harvest tool produces valid InternalHarvestPayload."""
    synthetic_fixtures = {
        "gmail": [
            {
                "id": "t1",
                "from": "Simon Elisha <selisha@google.com>",
                "subject": "Q3 Direction",
                "snippet": "Key deliverables",
            }
        ],
        "chat": {
            "dms": [
                {
                    "id": "dm1",
                    "sender": "Ollie Scott",
                    "text": "Optus call at 2pm",
                }
            ],
            "mentions": [],
        },
        "calendar": [
            {
                "summary": "Customer Exec Briefing",
                "start": {"dateTime": "2026-09-04T14:00:00+10:00"},
                "end": {"dateTime": "2026-09-04T15:00:00+10:00"},
            }
        ],
    }

    payload = harvest_all_internal_communications(
        lookback_hours=24, test_fixtures=synthetic_fixtures
    )
    assert payload["lookback_hours"] == 24
    assert len(payload["leadership_threads"]) == 1
    assert len(payload["chat_space_threads"]) == 1
    assert len(payload["calendar_events"]) == 1
    assert "harvest_timestamp" in payload


def test_internal_comms_agent_structure_and_docstrings():
    """Rubric 1.1, 1.2: Checks agent tools for docstrings and descriptive names."""
    assert internal_comms_agent.name == "internal_comms_agent"
    assert internal_comms_agent.output_key == "internal_comms_data"

    for tool in internal_comms_agent.tools:
        doc = inspect.getdoc(tool)
        assert doc is not None, f"Tool '{tool.__name__}' missing docstring"
        assert "Args:" in doc
        assert "Returns:" in doc
        assert "_" in tool.__name__
