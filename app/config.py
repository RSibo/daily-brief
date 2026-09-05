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

"""Centralized Application Configuration & Strategic Model Routing.

Implements Rubric Item 3.2 (Strategic Model Routing):
- ANALYTICAL_MODEL ('gemini-flash-latest'): Fast reasoning for cross-channel signal correlation,
  Chief of Staff executive synthesis, and strict editorial review gate auditing.
- THROUGHPUT_MODEL ('gemini-flash-latest'): High-speed throughput for Gmail/Chat harvesting,
  live web search extraction, and delivery formatting.
- SPEECH_TTS_MODEL ('gemini-3.1-flash-tts-preview'): Specialized multimodal audio model for
  expressive speech synthesis, speaker tone inflection, and pause-directed audio markdown.
"""

import os

# Strategic Model Routing Aliases (Unversioned)
ANALYTICAL_MODEL: str = os.getenv("ANALYTICAL_MODEL", "gemini-flash-latest")
THROUGHPUT_MODEL: str = os.getenv("THROUGHPUT_MODEL", "gemini-flash-latest")
SPEECH_TTS_MODEL: str = os.getenv("SPEECH_TTS_MODEL", "gemini-3.1-flash-tts-preview")

# Storage & Session Persistence
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '.adk', 'session.db'))}",
)

# Operational Timeouts & Lookback Windows
INTERNAL_COMMS_LOOKBACK_HOURS: int = 24
MARKET_NEWS_LOOKBACK_HOURS: int = 72
HOT_LIST_LOOKBACK_DAYS: int = 3
AUDIO_RETENTION_DAYS: int = 7
