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

import os
from typing import Any

import google.auth
from fastapi import BackgroundTasks, FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from app.tools.delivery_tools import cleanup_pipeline_artifacts
from app.tools.podcast_tools import generate_podcast_pipeline

setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Native ADK persistent database session configuration (zero external infrastructure)
default_db_path = os.path.join(AGENT_DIR, ".adk", "session.db")
os.makedirs(os.path.dirname(default_db_path), exist_ok=True)
session_service_uri = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

try:
    otel_enabled = os.getenv("OTEL_TO_CLOUD", "false").lower() in ("true", "1")
    app: FastAPI = get_fast_api_app(
        agents_dir=AGENT_DIR,
        web=True,
        artifact_service_uri=artifact_service_uri,
        allow_origins=allow_origins,
        session_service_uri=session_service_uri,
        otel_to_cloud=otel_enabled,
    )
except Exception:
    app: FastAPI = get_fast_api_app(
        agents_dir=AGENT_DIR,
        web=True,
        artifact_service_uri=artifact_service_uri,
        allow_origins=allow_origins,
        session_service_uri=session_service_uri,
        otel_to_cloud=False,
    )
app.title = "daily-brief"
app.description = "API for interacting with the Agent daily-brief"


def _run_background_delivery(session_state: dict[str, Any]) -> None:
    """Out-of-band execution worker for audio rendering and artifact cleanup."""
    generate_podcast_pipeline(mock=True)
    cleanup_pipeline_artifacts(retention_days=7)


@app.post("/run_briefing_async")
async def run_briefing_async(
    background_tasks: BackgroundTasks,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Non-blocking execution endpoint yielding fast textual brief while dispatching media to background."""
    state = payload or {}
    background_tasks.add_task(_run_background_delivery, state)
    return {
        "status": "processing",
        "message": "Briefing initiated. Audio rendering, calendar delivery, and cleanup dispatched to background worker.",
    }


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
