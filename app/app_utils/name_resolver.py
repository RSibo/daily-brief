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

"""Name and identifier resolution utility for internal communications.

Resolves Google usernames/LDAPs, email addresses, @mentions, and raw space hashes
into clean, human-readable executive names and space titles (e.g. "rsibo" -> "Rob Sibo").
"""

import re

# Canonical LDAP to Full Name directory
LDAP_NAME_MAP: dict[str, str] = {
    "rsibo": "Rob Sibo",
    "robert sibo": "Rob Sibo",
    "selisha": "Simon Elisha",
    "simon elisha": "Simon Elisha",
    "romish": "Romina Sharifpour",
    "romina sharifpour": "Romina Sharifpour",
    "ashmitak": "Ashmita Kapoor",
    "ashmita kapoor": "Ashmita Kapoor",
    "zaracraig": "Zara Craig",
    "zara craig": "Zara Craig",
    "mjmathew": "MJ Mathew",
    "mj mathew": "MJ Mathew",
    "michaelscutt": "Michael Scutt",
    "michael scutt": "Michael Scutt",
    "nickjenkins": "Nick Jenkins",
    "nick jenkins": "Nick Jenkins",
    "dfernandezcao": "Dan Fernandez Cao",
    "dan fernandez cao": "Dan Fernandez Cao",
    "ivanliu": "Ivan Liu",
    "ivan liu": "Ivan Liu",
    "pcorreia": "Pedro Correia",
    "pedro correia": "Pedro Correia",
    "nakulgowdra": "Nakul Gowdra",
    "nakul gowdra": "Nakul Gowdra",
    "jerryyip": "Jerry Yip",
    "jerry yip": "Jerry Yip",
    "yunyiliu": "Alex Liu",
    "alex liu": "Alex Liu",
    "dsearle": "David Searle",
    "david searle": "David Searle",
    "kevinkw": "Kevin Wang",
    "kevin wang": "Kevin Wang",
    "jordanfrance": "Jordan France",
    "jordan france": "Jordan France",
    "lewiswsmith": "Lewis Smith",
    "lewis smith": "Lewis Smith",
    "rodwilliams": "Rod Williams",
    "rod williams": "Rod Williams",
    "pgomran": "Pouya Gomran",
    "pouya gomran": "Pouya Gomran",
    "miteshagarwal": "Mitesh Agarwal",
    "mitesh agarwal": "Mitesh Agarwal",
    "mattpancino": "Matt Pancino",
    "matt pancino": "Matt Pancino",
    "cambridged": "David Cambridge",
    "david cambridge": "David Cambridge",
    "juliezheng": "Julie Zheng",
    "julie zheng": "Julie Zheng",
}

# Known Space ID to Human Label mapping
SPACE_LABEL_MAP: dict[str, str] = {
    "spaces/sUqvFKAAAAE": "Optus",
    "sUqvFKAAAAE": "Optus",
    "spaces/AAQASxODUp8": "Onboarding",
    "AAQASxODUp8": "Onboarding",
    "spaces/AAQA8rtaK_k": "BigW",
    "AAQA8rtaK_k": "BigW",
    "spaces/AAQAP1KTpYQ": "BigW / Rama",
    "AAQAP1KTpYQ": "BigW / Rama",
    "spaces/qUvE2KAAAAE": "Serko",
    "qUvE2KAAAAE": "Serko",
    "spaces/AAQAm7fBHAY": "AUNZ AISS",
    "AAQAm7fBHAY": "AUNZ AISS",
    "spaces/AAQAlcokf0k": "AuNZ AI Tech Team",
    "AAQAlcokf0k": "AuNZ AI Tech Team",
    "spaces/AAQAAc0KM_E": "AuNZ AI Tech Managers",
    "AAQAAc0KM_E": "AuNZ AI Tech Managers",
    "spaces/AAAA_gX6ESA": "AI GTM Specialists",
    "AAAA_gX6ESA": "AI GTM Specialists",
    "spaces/AAAAHD8qbfA": "Global GenAI FDE Team",
    "AAAAHD8qbfA": "Global GenAI FDE Team",
}


def resolve_ldap_or_email_to_name(identifier: str | None) -> str:
    """Resolves an email, LDAP username, or handle to a clean proper name.

    Args:
        identifier: Email address (e.g. "rsibo@google.com"), LDAP ("rsibo"),
            or handle ("@Robert Sibo").

    Returns:
        Clean full name (e.g. "Rob Sibo").
    """
    if not identifier:
        return ""

    raw = identifier.strip().lstrip("@")
    email_match = re.match(r"^([a-zA-Z0-9._-]+)@(?:google\.com|.*)$", raw)
    ldap = email_match.group(1).lower() if email_match else raw.lower()

    if ldap in LDAP_NAME_MAP:
        return LDAP_NAME_MAP[ldap]

    # If format is firstname.lastname, convert to Title Case
    if "." in ldap:
        parts = ldap.split(".")
        return " ".join(p.capitalize() for p in parts)

    # Return capitalized word if standard alphanumeric
    if ldap.isalpha():
        return ldap.capitalize()

    return raw


def resolve_all_names_and_identifiers(text: str) -> str:
    """Replaces raw LDAPs, email addresses, @mentions, and space hashes in text.

    Args:
        text: Input string containing possible raw identifiers.

    Returns:
        Transformed string with proper human names and clean space titles.
    """
    if not text:
        return ""

    result = text

    # 1. Resolve raw space brackets like [sUqvFKAAAAE] or [AAQASxODUp8]
    def _replace_space_bracket(match: re.Match[str]) -> str:
        space_id = match.group(1).strip()
        if space_id in SPACE_LABEL_MAP:
            return f"[{SPACE_LABEL_MAP[space_id]}]"
        # If unknown hash like AAQ..., strip the hash bracket entirely
        if re.match(r"^(?:spaces/|AAQA|sUqv|AAAA)[a-zA-Z0-9_-]+$", space_id):
            return ""
        return match.group(0)

    result = re.sub(r"\[([a-zA-Z0-9/_ -]+)\]", _replace_space_bracket, result)

    # 2. Resolve email addresses like username@google.com
    def _replace_email(match: re.Match[str]) -> str:
        ldap = match.group(1).lower()
        if ldap in LDAP_NAME_MAP:
            return LDAP_NAME_MAP[ldap]
        if "." in ldap:
            return " ".join(p.capitalize() for p in ldap.split("."))
        return match.group(0)

    result = re.sub(
        r"\b([a-zA-Z0-9._-]+)@google\.com\b",
        _replace_email,
        result,
        flags=re.IGNORECASE,
    )

    # 3. Resolve @mentions like @Robert Sibo, @Simon Elisha, @rsibo, @Ivan Liu
    def _replace_mention(match: re.Match[str]) -> str:
        mention_body = match.group(1).strip()
        lower_body = mention_body.lower()
        if lower_body in LDAP_NAME_MAP:
            return LDAP_NAME_MAP[lower_body]
        return mention_body

    result = re.sub(r"@([a-zA-Z0-9._ -]+?)(?=\s|[.,;:!?]|$)", _replace_mention, result)

    # 4. Resolve standalone known LDAPs when isolated as words
    for ldap_key, full_name in LDAP_NAME_MAP.items():
        if len(ldap_key) >= 4:  # Avoid replacing short 2-3 char common words
            pattern = rf"\b{re.escape(ldap_key)}\b"
            result = re.sub(pattern, full_name, result, flags=re.IGNORECASE)

    # 5. Clean up awkward artifacts like "Hi Sibo" or "Elisha Sibo"
    result = re.sub(r"\bHi\s+Sibo\b", "Hi Rob", result, flags=re.IGNORECASE)
    result = re.sub(
        r"\bElisha\s+Sibo\b", "Simon Elisha and Rob Sibo", result, flags=re.IGNORECASE
    )
    result = re.sub(r"\bSibo\s+Rob\b", "Rob Sibo", result, flags=re.IGNORECASE)
    # Collapse any recursive name duplicates like "Rob Rob Sibo" or "Rob Rob"
    result = re.sub(r"\b(?:Rob\s+)+Sibo\b", "Rob Sibo", result)
    result = re.sub(r"\b(?:Rob\s+){2,}", "Rob ", result)
    result = re.sub(r"\b(?:Simon\s+)+Elisha\b", "Simon Elisha", result)

    return result


def detect_unresolved_identifiers(text: str) -> list[str]:
    """Detects unresolved email addresses, raw LDAPs, or space hashes in text.

    Ignores URLs and href links.

    Args:
        text: Text string to audit.

    Returns:
        List of unresolved identifier strings found.
    """
    if not text:
        return []

    # Strip URLs and href tags so valid hyperlinks are not flagged
    cleaned = re.sub(r'href="[^"]+"', "", text)
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    unresolved: list[str] = []

    # 1. Unresolved Google email addresses
    email_matches = re.findall(
        r"\b[a-zA-Z0-9._-]+@google\.com\b", cleaned, flags=re.IGNORECASE
    )
    if email_matches:
        unresolved.extend(email_matches)

    # 2. Raw space ID brackets like [sUqvFKAAAAE] or [AAQASxODUp8]
    space_hash_matches = re.findall(
        r"\[(?:spaces/|AAQA|sUqv|AAAA)[a-zA-Z0-9_-]+\]", cleaned
    )
    if space_hash_matches:
        unresolved.extend(space_hash_matches)

    # 3. Raw rsibo or @rsibo in visible text
    if re.search(r"\b(?:@?rsibo)\b", cleaned, flags=re.IGNORECASE):
        unresolved.append("rsibo")

    return list(dict.fromkeys(unresolved))
