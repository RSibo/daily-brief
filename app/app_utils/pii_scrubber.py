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

"""PII and Sensitive Data Redaction Pipeline.

Implements Rubric Item 4.4 (PII Redaction):
Scrubs sensitive tokens, credentials, phone numbers, and secrets from text,
dictionaries, and payloads before writing to logs, session state, or memory stores.
"""

import re
from typing import Any

# Compiled regex patterns for common sensitive entities
PATTERNS = {
    "OAUTH_TOKEN": re.compile(r"ya29\.[a-zA-Z0-9_\-]+", re.IGNORECASE),
    "GOOGLE_API_KEY": re.compile(r"AIza[0-9A-Za-z_\-]{30,45}", re.IGNORECASE),
    "GENERIC_SECRET": re.compile(
        r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})|(password\s*[:=]\s*['\"][^'\"]+['\"])",
        re.IGNORECASE,
    ),
    "PHONE_NUMBER": re.compile(
        r"(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b"
    ),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
}


def redact_pii_text(text: str) -> str:
    """Scrubs sensitive PII, tokens, and credentials from a text string.

    Args:
        text: Raw input string containing potential PII or secrets.

    Returns:
        Sanitized string with matching entities replaced by [REDACTED_*] tags.
    """
    if not isinstance(text, str) or not text:
        return text

    sanitized = text
    sanitized = PATTERNS["OAUTH_TOKEN"].sub("[REDACTED_OAUTH_TOKEN]", sanitized)
    sanitized = PATTERNS["GOOGLE_API_KEY"].sub("[REDACTED_API_KEY]", sanitized)
    sanitized = PATTERNS["GENERIC_SECRET"].sub("[REDACTED_SECRET]", sanitized)
    sanitized = PATTERNS["CREDIT_CARD"].sub("[REDACTED_CARD]", sanitized)

    # Scrutinize phone numbers while avoiding short 4-digit years/ports
    def phone_replacer(match: re.Match) -> str:
        val = match.group(0).strip()
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 10:
            return "[REDACTED_PHONE]"
        return val

    sanitized = PATTERNS["PHONE_NUMBER"].sub(phone_replacer, sanitized)
    return sanitized


def redact_pii_object(obj: dict[str, Any] | list[Any] | str | Any) -> Any:
    """Recursively redacts PII across nested dictionaries and lists."""
    if isinstance(obj, str):
        return redact_pii_text(obj)
    if isinstance(obj, dict):
        return {k: redact_pii_object(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_pii_object(item) for item in obj]
    return obj
