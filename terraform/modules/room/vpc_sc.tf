/**
 * VPC Service Controls Perimeter Attachment & Ingress/Egress Policies for Spoke Research Room
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Spoke Service Perimeter Resource Assignment
# --------------------------------------------------------------------------------------------------

resource "google_access_context_manager_service_perimeter_resource" "spoke_perimeter_resource" {
  count          = var.enable_vpc_sc && var.access_policy_id != null ? 1 : 0
  perimeter_name = "accessPolicies/${var.access_policy_id}/servicePerimeters/hub_mgmt_perimeter"
  resource       = "projects/${var.spoke_project_id}"

  depends_on = [
    google_project_service.spoke_services
  ]
}

# --------------------------------------------------------------------------------------------------
# 2. Spoke-Specific Ingress & Egress Rules Reference
# --------------------------------------------------------------------------------------------------
# When attached to the VPC-SC security perimeter:
# 1. All researcher queries to BigQuery and GCS are restricted to the perimeter boundary.
# 2. Ingress from Hub Gateway is permitted for metadata inspection & Gemini Flash AI scanning.
# 3. Direct Internet egress from notebooks and storage is blocked by default.
