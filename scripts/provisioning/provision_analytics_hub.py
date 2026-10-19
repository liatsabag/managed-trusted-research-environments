"""BigQuery Analytics Hub Data Exchange and Linked Dataset Subscriptions."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import logging
from typing import Any, Dict

logger = logging.getLogger("provision_analytics_hub")


def provision_analytics_hub(
    topology: Dict[str, Any],
    region: str = "me-west1",
) -> Dict[str, Any]:
    """Create BigQuery Analytics Hub Exchange & Listings in Hub, and subscribe Spoke projects."""
    hub_proj = topology.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    exchange_id = "rr_central_exchange"
    summary: Dict[str, Any] = {
        "exchange": None,
        "listings": [],
        "subscriptions": [],
    }

    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, _ = google.auth.default()
        hub_service = build("analyticshub", "v1", credentials=creds)
        logger.info("Connected to Analytics Hub API for central data sharing (Region: %s)", region)
    except Exception as exc:
        logger.warning("Could not initialize Analytics Hub client: %s", exc)
        return summary

    # 1. Create or Verify Central Data Exchange in Hub Project
    parent_loc = f"projects/{hub_proj}/locations/{region}"
    exchange_name = f"{parent_loc}/dataExchanges/{exchange_id}"
    try:
        try:
            hub_service.projects().locations().dataExchanges().get(name=exchange_name).execute()
            logger.info("Analytics Hub Data Exchange already exists: %s", exchange_name)
        except Exception:
            logger.info("Creating Analytics Hub Data Exchange: %s...", exchange_id)
            body = {
                "displayName": "Research Room Central Data Exchange",
                "description": "Central catalog sharing clinical and reference datasets across research room fleet",
            }
            hub_service.projects().locations().dataExchanges().create(
                parent=parent_loc,
                dataExchangeId=exchange_id,
                body=body,
            ).execute()
            logger.info("Created Analytics Hub Data Exchange: %s", exchange_name)
        summary["exchange"] = exchange_name
    except Exception as exc:
        logger.warning("Data Exchange provisioning notice for %s: %s", exchange_id, exc)

    # 2. Create Listings for Shared Datasets
    shared_listings = [
        {
            "id": "hub_shared_clinical",
            "displayName": "Hub Shared Clinical Catalogs",
            "description": "Standardized ICD-10 and OMOP Common Data Model concept vocabularies",
            "dataset": f"projects/{hub_proj}/datasets/hub_shared_clinical",
        },
        {
            "id": "hub_shared_reference",
            "displayName": "Hub Shared Reference Biomarker Panels",
            "description": "ClinVar and ACMG actionable biomarker panel and standard lab ranges",
            "dataset": f"projects/{hub_proj}/datasets/hub_shared_reference",
        },
    ]

    for item in shared_listings:
        listing_id = item["id"]
        listing_name = f"{exchange_name}/listings/{listing_id}"
        try:
            try:
                hub_service.projects().locations().dataExchanges().listings().get(name=listing_name).execute()
                logger.info("Analytics Hub Listing already exists: %s", listing_name)
            except Exception:
                logger.info("Creating Analytics Hub Listing: %s...", listing_id)
                body = {
                    "displayName": item["displayName"],
                    "description": item["description"],
                    "bigqueryDataset": {
                        "dataset": item["dataset"],
                    },
                }
                hub_service.projects().locations().dataExchanges().listings().create(
                    parent=exchange_name,
                    listingId=listing_id,
                    body=body,
                ).execute()
                logger.info("Created Analytics Hub Listing: %s", listing_name)
            summary["listings"].append(listing_name)
        except Exception as exc:
            logger.warning("Listing creation notice for %s: %s", listing_id, exc)

    # 3. Grant Spoke / Organization subscribers permission on the exchange
    try:
        policy = hub_service.projects().locations().dataExchanges().getIamPolicy(resource=exchange_name).execute()
        bindings = policy.get("bindings", [])
        org_domain = topology.get("organization", {}).get("domain", "liatsabag.altostrat.com")
        domain_member = f"domain:{org_domain}"
        subscriber_role = "roles/analyticshub.subscriber"
        
        sub_binding = next((b for b in bindings if b.get("role") == subscriber_role), None)
        if sub_binding:
            if domain_member not in sub_binding.get("members", []):
                sub_binding.setdefault("members", []).append(domain_member)
        else:
            bindings.append({"role": subscriber_role, "members": [domain_member]})
        
        policy["bindings"] = bindings
        hub_service.projects().locations().dataExchanges().setIamPolicy(resource=exchange_name, body={"policy": policy}).execute()
        logger.info("Granted Analytics Hub subscriber role to domain '%s' on %s", org_domain, exchange_name)
    except Exception as exc:
        logger.warning("Analytics Hub IAM policy update notice: %s", exc)

    # 4. Subscribe each Spoke project to the shared listings
    for room in topology.get("research_rooms", []):
        spoke_proj = room.get("spoke_project_id")
        if not spoke_proj:
            continue
        subscriptions_wanted = room.get("shared_dataset_subscriptions", ["hub_shared_clinical", "hub_shared_reference"])
        for ds_id in subscriptions_wanted:
            listing_name = f"{exchange_name}/listings/{ds_id}"
            try:
                sub_body = {
                    "destinationDataset": {
                        "datasetReference": {
                            "projectId": spoke_proj,
                            "datasetId": ds_id,
                        },
                        "description": f"Linked shared dataset ({ds_id}) from Hub Analytics Hub",
                        "location": region,
                    }
                }
                hub_service.projects().locations().dataExchanges().listings().subscribe(
                    name=listing_name,
                    body=sub_body,
                ).execute()
                logger.info("Successfully subscribed spoke project %s to %s -> %s.%s", spoke_proj, ds_id, spoke_proj, ds_id)
                summary["subscriptions"].append({"spoke": spoke_proj, "dataset": ds_id, "status": "SUBSCRIBED"})
            except Exception as exc:
                if "already exists" in str(exc).lower() or "409" in str(exc):
                    logger.info("Spoke project %s already subscribed to %s (%s.%s)", spoke_proj, ds_id, spoke_proj, ds_id)
                    summary["subscriptions"].append({"spoke": spoke_proj, "dataset": ds_id, "status": "ALREADY_EXISTS"})
                else:
                    logger.warning("Could not subscribe %s to %s: %s", spoke_proj, ds_id, exc)

    return summary
