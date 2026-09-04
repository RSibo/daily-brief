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

output "cloud_run_service_url" {
  description = "The public/internal URL of the deployed Daily Brief Cloud Run service."
  value       = google_cloud_run_v2_service.daily_brief.uri
}

output "artifact_bucket_name" {
  description = "The GCS bucket dedicated to audio briefing assets and session backups."
  value       = google_storage_bucket.briefing_artifacts.name
}

output "service_account_email" {
  description = "The email of the least-privilege service account running the agent."
  value       = google_service_account.daily_brief_runner.email
}
