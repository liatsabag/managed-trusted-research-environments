/**
 * Cloud Identity Group & Memberships for Spoke Research Room
 * GCP Health Data Platform POC
 */

# Cloud Identity Group for Room Researchers
resource "google_cloud_identity_group" "room_researchers_group" {
  count        = var.enable_cloud_identity ? 1 : 0
  display_name = "${var.room_name} Researchers"
  description  = "Governed researcher identity group for room ${var.room_id}"

  parent = "customers/my_customer"

  group_key {
    id = local.group_email
  }

  labels = {
    "cloudidentity.googleapis.com/groups.discussion_forum" = ""
  }
}

# Member assignments to the Cloud Identity Group
resource "google_cloud_identity_group_membership" "researcher_memberships" {
  for_each = var.enable_cloud_identity ? { for r in var.researchers : r.primary_email => r } : {}

  group = google_cloud_identity_group.room_researchers_group[0].id

  preferred_member_key {
    id = each.key
  }

  roles {
    name = "MEMBER"
  }
}
