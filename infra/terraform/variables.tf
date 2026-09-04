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

variable "project_id" {
  description = "The Google Cloud Project ID where the Daily Brief agent resources are deployed."
  type        = string
}

variable "region" {
  description = "The primary Google Cloud region for compute and storage resources."
  type        = string
  default     = "australia-southeast1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "service_name" {
  description = "The application name for Cloud Run and resource naming."
  type        = string
  default     = "daily-brief"
}

variable "container_image" {
  description = "The container image URI for the ADK agent Cloud Run service."
  type        = string
  default     = "australia-southeast1-docker.pkg.dev/daily-brief-project/daily-brief/agent:latest"
}

variable "retention_days" {
  description = "GCS lifecycle retention window in days for audio podcast files and cached artifacts."
  type        = number
  default     = 7
}
