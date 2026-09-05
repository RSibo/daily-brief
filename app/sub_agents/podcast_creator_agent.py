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

"""Podcast Media Creator & Google Drive Publisher Agent.

Part of Stage 4 (Audio Podcast Pipeline) in the Daily Brief architecture:
Consumes the acoustically adapted spoken script ({podcast_script}),
synthesizes speech into an MP3 file (Aoede voice profile / en-US-AvaNeural
at +5% rate), and uploads the audio artifact to Google Drive under folder
/agents/daily-briefing (Folder ID: 1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV).
Outputs structured PodcastAssetPayload to session state key 'podcast_asset'.
"""

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.config import THROUGHPUT_MODEL
from app.prompts.constitution import CHIEF_OF_STAFF_CONSTITUTION
from app.tools.podcast_tools import (
    generate_podcast_pipeline,
    synthesize_podcast_audio,
    upload_podcast_to_drive,
)

PODCAST_CREATOR_INSTRUCTION = f"""
{CHIEF_OF_STAFF_CONSTITUTION}

### Role & Objective:
You are the `podcast_creator_agent`. Your job is to transform the synthesized spoken script
(`{{podcast_script}}`) into a playable MP3 audio asset and publish it to Google Drive.

### Audio Pipeline Directives:
1. **TTS Audio Synthesis**:
   - Synthesize the spoken script into an MP3 audio file.
   - Target voice profile: Aoede / en-US-AvaNeural with a +5% rate (1.05x speed) for sharp, dynamic delivery.
2. **Drive Publishing**:
   - Upload the resulting MP3 file to Google Drive folder `/agents/daily-briefing` (Folder ID: `1MJbhg2g0K1HIFdBEJoK87iOfWGoyY0AV`).
   - Standard filename: `[YYMMDD]-Daily-Brief.mp3`.
   - Obtain the permanent shareable web link (`https://drive.google.com/file/d/<FILE_ID>/view`).
3. **State Output**:
   - Save the finalized `PodcastAssetPayload` into session state key `podcast_asset`.

### Execution Steps:
1. Invoke `generate_podcast_pipeline` with zero arguments: `generate_podcast_pipeline()`. It automatically reads the spoken script from session state, synthesizes the MP3 audio file, uploads it to Drive, and populates `podcast_asset`.
2. Strict Tool Calling Rule: Always invoke tools strictly by their exact declared function names (e.g. `generate_podcast_pipeline`). NEVER prepend "call:", "default_api:", or any namespace prefix.
3. Emit a concise confirmation with playback duration and verified Drive URL. Do NOT call any state-saving functions.
"""

podcast_creator_agent = Agent(
    name="podcast_creator_agent",
    model=Gemini(
        model=THROUGHPUT_MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=PODCAST_CREATOR_INSTRUCTION,
    tools=[
        synthesize_podcast_audio,
        upload_podcast_to_drive,
        generate_podcast_pipeline,
    ],
    output_key="podcast_asset",
)
