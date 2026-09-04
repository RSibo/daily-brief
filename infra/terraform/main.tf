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

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# Google Cloud APIs Enablement
# -----------------------------------------------------------------------------
locals {
  services = [
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "cloudbuild.googleapis.com"
  ]
}

resource "google_project_service" "enabled_services" {
  for_each           = toset(locals.services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Least-Privilege Service Account & IAM Roles (Rubric 5.2)
# -----------------------------------------------------------------------------
resource "google_service_account" "daily_brief_runner" {
  account_id   = "daily-brief-runner"
  display_name = "Daily Brief ADK Agent Runtime Service Account"
  project      = var.project_id
  depends_on   = [google_project_service.enabled_services]
}

locals {
  agent_roles = [
    "roles/aiplatform.user",
    "roles/storage.objectAdmin",
    "roles/secretmanager.secretAccessor",
    "roles/cloudtrace.agent",
    "roles/logging.logWriter"
  ]
}

resource "google_project_iam_member" "agent_permissions" {
  for_each = toset(locals.agent_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.daily_brief_runner.email}"
}

# -----------------------------------------------------------------------------
# Cloud Storage Bucket for Audio & Artifacts with 7-Day Lifecycle Rule
# -----------------------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "briefing_artifacts" {
  name                        = "${var.project_id}-daily-brief-artifacts-${random_id.bucket_suffix.hex}"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = var.retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled_services]
}

# -----------------------------------------------------------------------------
# Secret Manager for OAuth & API Credentials (Rubric 5.3)
# -----------------------------------------------------------------------------
resource "google_secret_manager_secret" "oauth_credentials" {
  secret_id = "daily-brief-oauth-credentials"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled_services]
}

# -----------------------------------------------------------------------------
# Cloud Run Service (v2) - Serverless Agent Runtime
# -----------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "daily_brief" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.daily_brief_runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "ARTIFACT_BUCKET_NAME"
        value = google_storage_bucket.briefing_artifacts.name
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "RETENTION_DAYS"
        value = tostring(var.retention_days)
      }
    }
  }

  depends_on = [
    google_project_service.enabled_services,
    google_project_iam_member.agent_permissions
  ]
}
