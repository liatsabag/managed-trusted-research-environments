/**
 * VPC Service Controls Perimeter Configuration for Central Management Hub
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Access Level Definition for Trusted Hub Administrators
# --------------------------------------------------------------------------------------------------

resource "google_access_context_manager_access_level" "hub_admin_access" {
  count       = var.enable_vpc_sc && var.access_policy_id != null ? 1 : 0
  parent      = "accessPolicies/${var.access_policy_id}"
  name        = "accessPolicies/${var.access_policy_id}/accessLevels/hub_admin_trusted_access"
  title       = "Hub Admin Trusted Access Level"
  description = "Allows central administrators access to the Hub management perimeter"

  basic {
    combining_function = "AND"
    conditions {
      members = [
        "serviceAccount:${google_service_account.hub_backend.email}"
      ]
    }
  }
}

# --------------------------------------------------------------------------------------------------
# 2. Hub Management Core Service Perimeter
# --------------------------------------------------------------------------------------------------

resource "google_access_context_manager_service_perimeter" "hub_perimeter" {
  count          = var.enable_vpc_sc && var.access_policy_id != null ? 1 : 0
  parent         = "accessPolicies/${var.access_policy_id}"
  name           = "accessPolicies/${var.access_policy_id}/servicePerimeters/hub_mgmt_perimeter"
  title          = "Hub Management Core Service Perimeter"
  description    = "Isolates Hub BigQuery telemetry, registry datasets, and Vertex AI models"
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  status {
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "aiplatform.googleapis.com"
    ]

    resources = [
      "projects/${var.hub_project_id}"
    ]

    access_levels = [
      google_access_context_manager_access_level.hub_admin_access[0].name
    ]

    # Ingress policy: Allow Spoke projects to stream audit logs and query shared datasets
    ingress_policies {
      ingress_from {
        identity_type = "ANY_IDENTITY"
        sources {
          access_level = "*"
        }
      }
      ingress_to {
        resources = ["projects/${var.hub_project_id}"]
        operations {
          service_name = "bigquery.googleapis.com"
          method_selectors {
            method = "TableService.GetData"
          }
        }
      }
    }

    # Egress policy: Allow Hub backend service account to inspect spoke quarantine buckets for Gemini scanning
    egress_policies {
      egress_from {
        identity_type = "ANY_IDENTITY"
        identities = [
          "serviceAccount:${google_service_account.hub_backend.email}"
        ]
      }
      egress_to {
        resources = ["*"]
        operations {
          service_name = "storage.googleapis.com"
          method_selectors {
            method = "storage.objects.get"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.hub_services
  ]
}
