"""FinOps Hierarchical SKU, Cost Drivers, Capacity, and Telemetry Attribution Engine."""

import calendar
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import bigquery

from backend.app.core.cache import cached_endpoint, cache
from backend.app.core.config import get_settings
from backend.app.models.finops import (
    CapacityTrackingMetrics,
    CostDriversBreakdown,
    FinOpsAllocationMatrixResponse,
    FinOpsAnomalyAlert,
    FinOpsForecastResponse,
    FinOpsSummaryResponse,
    InstituteCostBreakdown,
    ProjectCostItem,
    ResearcherCostDetail,
    ResearcherSKUAttribution,
    ResearcherTelemetryUsage,
    RoomBudgetRunway,
    RoomFinOpsDetailResponse,
    SKUBillingItem,
    SharedOverheadDetail,
)

logger = logging.getLogger("finops_service")


def _clean(val: Any) -> Optional[str]:
    return val if isinstance(val, str) and val.strip() else None


class FinOpsService:
    """FinOps Engine for hierarchical billing SKU, capacity tracking, and telemetry weight attribution."""

    def __init__(self, bq_client: Optional[bigquery.Client] = None):
        settings = get_settings()
        self.hub_project = getattr(settings, "GCP_PROJECT_ID", "gcp-rr-hub-core")
        self.telemetry_dataset = getattr(settings, "HUB_TELEMETRY_DATASET", "hub_telemetry")
        self.registry_dataset = getattr(settings, "HUB_REGISTRY_DATASET", "hub_registry")
        self.client = bq_client or bigquery.Client(project=self.hub_project)

    def _get_current_invoice_month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m")

    def _get_days_context(self, invoice_month: Any) -> Tuple[int, int]:
        if not isinstance(invoice_month, str) or len(invoice_month) < 6 or not invoice_month[:6].isdigit():
            invoice_month = self._get_current_invoice_month()
        year, month = int(invoice_month[:4]), int(invoice_month[4:6])
        days_in_month = calendar.monthrange(year, month)[1]
        now = datetime.now(timezone.utc)
        days_elapsed = max(1, now.day) if (now.year == year and now.month == month) else (1 if datetime(year, month, 1, tzinfo=timezone.utc) > now else days_in_month)
        return days_elapsed, days_in_month

    def _load_topology(self) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, str]]:
        rooms = {r["room_id"]: dict(r) for r in self.client.query(f"SELECT room_id, room_name, institute_id, spoke_project_id, status, IFNULL(budget_limit_usd, 5000.0) AS budget_limit_usd, created_at FROM `{self.hub_project}.{self.registry_dataset}.reg_research_rooms`").result()}
        institutes = {i["institute_id"]: dict(i) for i in self.client.query(f"SELECT institute_id, name, contact_email, country FROM `{self.hub_project}.{self.registry_dataset}.reg_institutes`").result()}
        researchers = [dict(u) for u in self.client.query(f"SELECT researcher_id, first_name, last_name, primary_email, institute_id, room_id, is_active FROM `{self.hub_project}.{self.registry_dataset}.reg_researchers` WHERE is_active = TRUE").result()]
        return rooms, institutes, researchers, {r["spoke_project_id"]: r["room_id"] for r in rooms.values()}

    def _load_billing_data(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        inv_mo, s_date, e_date = _clean(invoice_month), _clean(start_date), _clean(end_date)
        params, where = [], []
        if s_date and e_date:
            where.append("DATE(usage_start_time) >= @start_date AND DATE(usage_end_time) <= @end_date")
            params.extend([bigquery.ScalarQueryParameter("start_date", "STRING", s_date), bigquery.ScalarQueryParameter("end_date", "STRING", e_date)])
        elif inv_mo:
            where.append("invoice_month = @invoice_month")
            params.append(bigquery.ScalarQueryParameter("invoice_month", "STRING", inv_mo))

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        q = f"""
        SELECT project_id, service_id, service_description, sku_id, sku_description, currency,
               SUM(cost) + IFNULL(SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)), 0) AS total_cost,
               SUM(usage_amount) AS total_usage_amount, ANY_VALUE(usage_unit) AS usage_unit
        FROM `{self.hub_project}.{self.telemetry_dataset}.view_billing_export`
        {where_clause}
        GROUP BY project_id, service_id, service_description, sku_id, sku_description, currency
        """
        return [dict(r) for r in self.client.query(q, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()]

    def _load_compute_metrics(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Dict[str, Dict[str, Any]]]:
        inv_mo, s_date, e_date = _clean(invoice_month), _clean(start_date), _clean(end_date)
        params, where = [], []
        if s_date and e_date:
            where.append("usage_date >= @start_date AND usage_date <= @end_date")
            params.extend([bigquery.ScalarQueryParameter("start_date", "STRING", s_date), bigquery.ScalarQueryParameter("end_date", "STRING", e_date)])
        elif inv_mo:
            where.append("FORMAT_DATE('%Y%m', usage_date) = @invoice_month")
            params.append(bigquery.ScalarQueryParameter("invoice_month", "STRING", inv_mo))

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        q = f"""
        SELECT room_id, user_email, SUM(query_count) AS query_count, SUM(total_bytes_billed) AS total_bytes_billed,
               SUM(notebook_runtime_hours) AS notebook_runtime_hours, SUM(ai_token_count) AS ai_token_count,
               SUM(total_slot_hours) AS total_slot_hours,
               MAX(storage_bytes) AS storage_bytes
        FROM `{self.hub_project}.{self.telemetry_dataset}.ops_daily_compute_metrics`
        {where_clause}
        GROUP BY room_id, user_email
        """
        res: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        for r in self.client.query(q, job_config=bigquery.QueryJobConfig(query_parameters=params)).result():
            res[r["room_id"]][r["user_email"]] = {
                "query_count": int(r["query_count"] or 0), "total_bytes_billed": int(r["total_bytes_billed"] or 0),
                "notebook_runtime_hours": float(r["notebook_runtime_hours"] or 0.0),
                "ai_token_count": int(r["ai_token_count"] or 0), "storage_bytes": int(r["storage_bytes"] or 0),
                "total_slot_hours": float(r.get("total_slot_hours") or 0.0),
            }
        return res

    def _determine_category(self, service_desc: str, sku_desc: str) -> str:
        """Classify any GCP line item into the standard 5 service cost drivers.
        
        Evaluates at parent cloud service level, ensuring all VM machine types,
        storage operations, BigQuery queries, and AI models/tokens roll up cleanly.
        """
        s_service = (service_desc or "").lower()
        s_sku = (sku_desc or "").lower()
        s = f"{s_service} {s_sku}"

        if any(k in s for k in ["vertex", "gemini", "ai platform", "token", "generative", "model", "prediction", "inference", "language", "speech", "vision", "translation"]) or "ai" in s_service.split():
            return "ai"
        if "network" in s or "egress" in s or "transfer" in s:
            return "network"
        if "bigquery" in s_service or "analysis" in s_sku:
            return "storage" if any(x in s_sku for x in ["storage", "physical", "logical"]) else "bigquery"
        if "storage" in s_service or "bucket" in s or "gcs" in s or "artifact registry" in s_service:
            return "storage"
        if any(k in s_service for k in ["compute", "cloud run", "app engine", "kubernetes", "gke"]) or any(k in s_sku for k in ["instance", "colab", "notebook", "cpu", "core", "ram", "gpu"]):
            return "compute"
        return "other"

    def _compute_cost_drivers(self, skus: List[SKUBillingItem]) -> CostDriversBreakdown:
        b = CostDriversBreakdown()
        for s in skus:
            c = float(s.cost or 0.0)
            cat = self._determine_category(s.service_description, s.sku_description)
            if cat == "storage": b.storage_cost = round(b.storage_cost + c, 6)
            elif cat == "compute": b.compute_notebooks_cost = round(b.compute_notebooks_cost + c, 6)
            elif cat == "bigquery": b.bigquery_cost = round(b.bigquery_cost + c, 6)
            elif cat == "network": b.network_egress_cost = round(b.network_egress_cost + c, 6)
            elif cat == "ai": b.vertex_ai_cost = round(b.vertex_ai_cost + c, 6)
            else: b.other_cost = round(b.other_cost + c, 6)
        return b

    def _compute_capacity(self, room_metrics: Dict[str, Dict[str, Any]]) -> CapacityTrackingMetrics:
        cap = CapacityTrackingMetrics()
        for m in room_metrics.values():
            cap.bigquery_bytes_scanned += int(m.get("total_bytes_billed") or 0)
            cap.compute_core_hours = round(cap.compute_core_hours + float(m.get("notebook_runtime_hours") or 0.0), 2)
            cap.ai_token_count += int(m.get("ai_token_count") or 0)
            cap.ai_calls_count += int(m.get("ai_inference_count") or (1 if int(m.get("ai_token_count") or 0) > 0 else 0))
            cap.storage_volume_bytes += int(m.get("storage_bytes") or 0)
            cap.bigquery_slot_hours += float(m.get("total_slot_hours") or 0.0)

        cap.bigquery_slot_hours = round(cap.bigquery_slot_hours, 6)
        return cap

    def _compute_attribution_for_sku(
        self, room_researchers: List[Dict[str, Any]], room_metrics: Dict[str, Dict[str, Any]], sku: SKUBillingItem
    ) -> Tuple[Dict[str, ResearcherSKUAttribution], ResearcherSKUAttribution]:
        cost = max(0.0, float(sku.cost))
        emails = [r.get("primary_email", "") for r in room_researchers]
        cat = self._determine_category(sku.service_description, sku.sku_description)
        actor_vals: Dict[str, float] = {}
        for actor in set(emails) | set(room_metrics.keys()):
            m = room_metrics.get(actor, {})
            if cat == "bigquery": actor_vals[actor] = float(m.get("total_bytes_billed", 0))
            elif cat == "compute": actor_vals[actor] = float(m.get("notebook_runtime_hours", 0.0))
            elif cat == "ai": actor_vals[actor] = float(m.get("ai_token_count", 0))
            elif cat == "storage": actor_vals[actor] = float(m.get("storage_bytes", 0))
            else: actor_vals[actor] = 0.0

        formula_map = {"bigquery": "W = bytes_billed(actor) / total_bytes", "compute": "W = notebook_hours(actor) / total_hours", "ai": "W = ai_tokens(actor) / total_tokens", "storage": "W = storage_bytes(actor) / total_storage"}
        formula, tot_usage = formula_map.get(cat, "100% Shared Overhead"), sum(actor_vals.values())
        res_attrs: Dict[str, ResearcherSKUAttribution] = {}
        if tot_usage > 0:
            for e in emails:
                u = actor_vals.get(e, 0.0)
                res_attrs[e] = ResearcherSKUAttribution(sku_id=sku.sku_id, sku_description=sku.sku_description, weight=round(u / tot_usage, 6), formula_applied=formula, allocated_cost=round(cost * (u / tot_usage), 6))
            ovh_cost = round(cost - sum(a.allocated_cost for a in res_attrs.values()), 6)
            ovh_usage = sum(v for k, v in actor_vals.items() if k not in emails)
            ovh_attr = ResearcherSKUAttribution(sku_id=sku.sku_id, sku_description=sku.sku_description, weight=round(ovh_usage / tot_usage, 6), formula_applied=formula, allocated_cost=ovh_cost)
        else:
            for e in emails: res_attrs[e] = ResearcherSKUAttribution(sku_id=sku.sku_id, sku_description=sku.sku_description, weight=0.0, formula_applied="Zero Usage", allocated_cost=0.0)
            ovh_attr = ResearcherSKUAttribution(sku_id=sku.sku_id, sku_description=sku.sku_description, weight=1.0, formula_applied="100% Shared Overhead", allocated_cost=round(cost, 6))
        return res_attrs, ovh_attr

    def _build_room_detail(
        self, room_info: Dict[str, Any], room_researchers: List[Dict[str, Any]],
        room_skus: List[SKUBillingItem], room_metrics: Dict[str, Dict[str, Any]]
    ) -> RoomFinOpsDetailResponse:
        room_id, res_emails = room_info["room_id"], {r["primary_email"] for r in room_researchers}
        res_costs: Dict[str, ResearcherCostDetail] = {}
        for r in room_researchers:
            email = r["primary_email"]
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or r["researcher_id"]
            m = room_metrics.get(email, {})
            usage = ResearcherTelemetryUsage(total_bytes_billed=m.get("total_bytes_billed", 0), query_count=m.get("query_count", 0), notebook_runtime_hours=m.get("notebook_runtime_hours", 0.0), ai_token_count=m.get("ai_token_count", 0), storage_bytes=m.get("storage_bytes", 0))
            res_costs[email] = ResearcherCostDetail(researcher_id=r["researcher_id"], name=name, email=email, institute_id=r["institute_id"], telemetry_usage=usage, sku_attributions=[], total_allocated_cost=0.0)

        admin_usage = ResearcherTelemetryUsage()
        for actor, m in room_metrics.items():
            if actor not in res_emails:
                admin_usage.total_bytes_billed += m.get("total_bytes_billed", 0)
                admin_usage.query_count += m.get("query_count", 0)
                admin_usage.notebook_runtime_hours = round(admin_usage.notebook_runtime_hours + m.get("notebook_runtime_hours", 0.0), 2)
                admin_usage.ai_token_count += m.get("ai_token_count", 0)
                admin_usage.storage_bytes = max(admin_usage.storage_bytes, m.get("storage_bytes", 0))

        ovh_skus: List[ResearcherSKUAttribution] = []
        for sku in room_skus:
            r_attrs, ovh_attr = self._compute_attribution_for_sku(room_researchers, room_metrics, sku)
            ovh_skus.append(ovh_attr)
            for email, attr in r_attrs.items():
                if email in res_costs:
                    res_costs[email].sku_attributions.append(attr)
                    res_costs[email].total_allocated_cost = round(res_costs[email].total_allocated_cost + attr.allocated_cost, 6)

        researchers_list = list(res_costs.values())
        tot_ovh, tot_res, tot_invoiced = round(sum(a.allocated_cost for a in ovh_skus), 6), round(sum(r.total_allocated_cost for r in researchers_list), 6), round(sum(s.cost for s in room_skus), 6)
        variance = round(abs(tot_invoiced - (tot_res + tot_ovh)), 6)
        created_at_val = str(room_info.get("created_at") or "2026-09-24T08:00:00Z")

        return RoomFinOpsDetailResponse(
            room_id=room_id, room_name=room_info.get("room_name", room_id), spoke_project_id=room_info.get("spoke_project_id", ""),
            institute_id=room_info.get("institute_id", ""), budget_limit_usd=float(room_info.get("budget_limit_usd") or 5000.0),
            total_invoiced_cost=tot_invoiced, currency="USD", created_at=created_at_val, spend_since_creation=tot_invoiced,
            cost_drivers=self._compute_cost_drivers(room_skus),
            capacity=self._compute_capacity(room_metrics), skus=room_skus, researchers=researchers_list,
            shared_overhead=SharedOverheadDetail(admin_usage=admin_usage, sku_attributions=ovh_skus, total_shared_overhead_cost=tot_ovh),
            reconciliation_variance=variance, reconciliation_status="BALANCED" if variance < 0.05 else "DISCREPANCY",
        )

    def _build_allocation(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[Dict[str, Any], float, float, float, float]:
        rooms, institutes, researchers, project_to_room = self._load_topology()
        billing_rows = self._load_billing_data(invoice_month, start_date, end_date)
        compute_metrics = self._load_compute_metrics(invoice_month, start_date, end_date)

        project_skus: Dict[str, List[SKUBillingItem]] = defaultdict(list)
        for row in billing_rows:
            project_skus[row["project_id"]].append(SKUBillingItem(
                service_id=row["service_id"], service_description=row["service_description"],
                sku_id=row["sku_id"], sku_description=row["sku_description"],
                cost=round(float(row["total_cost"]), 6), currency=row.get("currency", "USD"),
                usage_amount=float(row.get("total_usage_amount") or 0.0), usage_unit=row.get("usage_unit"),
            ))

        room_researchers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in researchers: room_researchers[r["room_id"]].append(r)

        room_details = {r_id: self._build_room_detail(r_info, room_researchers.get(r_id, []), project_skus.get(r_info["spoke_project_id"], []), compute_metrics.get(r_id, {})) for r_id, r_info in rooms.items()}
        hub_skus = project_skus.get(self.hub_project, [])
        hub_cost, total_fleet = round(sum(s.cost for s in hub_skus), 6), round(sum(float(r["total_cost"]) for r in billing_rows), 6)
        total_res = round(sum(sum(r.total_allocated_cost for r in rd.researchers) for rd in room_details.values()), 6)
        total_ovh = round(sum(rd.shared_overhead.total_shared_overhead_cost for rd in room_details.values()), 6)

        inv_c, s_c, e_c = _clean(invoice_month), _clean(start_date), _clean(end_date)
        mo_label = inv_c or ("CUSTOM_RANGE" if (s_c and e_c) else "ALL_TIME")
        return {"invoice_month": mo_label, "rooms": rooms, "institutes": institutes, "room_details": room_details, "hub_skus": hub_skus, "hub_cost": hub_cost, "project_skus": project_skus, "billing_rows": billing_rows, "compute_metrics": compute_metrics}, total_fleet, total_res, total_ovh, hub_cost

    @cached_endpoint(ttl_seconds=45, key_prefix="finops_summary")
    def get_summary(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> FinOpsSummaryResponse:
        inv_mo = _clean(invoice_month)
        state, total_fleet, total_res, total_ovh, hub_cost = self._build_allocation(inv_mo, start_date, end_date)
        projects_breakdown = [ProjectCostItem(project_id=p_id, room_id=next((r["room_id"] for r in state["rooms"].values() if r["spoke_project_id"] == p_id), None), total_cost=round(sum(s.cost for s in skus), 6), currency="USD") for p_id, skus in state["project_skus"].items()]
        institutes_summary = [self.get_institute_cost(i_id, state=state) for i_id in state["institutes"].keys()]
        active_mo = inv_mo or (self._get_current_invoice_month() if state["invoice_month"] in ("ALL_TIME", "CUSTOM_RANGE") else state["invoice_month"])
        days_el, days_mo = self._get_days_context(active_mo)
        forecast = round((total_fleet / days_el) * days_mo if days_el > 0 else total_fleet, 6)

        all_skus = [s for skus in state["project_skus"].values() for s in skus]
        cost_drivers = self._compute_cost_drivers(all_skus)
        all_metrics = {f"{r_id}_{u}": m for r_id, r_metrics in state["compute_metrics"].items() for u, m in r_metrics.items()}
        fleet_capacity = self._compute_capacity(all_metrics)

        total_grant = sum(float(r.get("budget_limit_usd") or 5000.0) for r in state["rooms"].values())
        min_created = min((str(r.get("created_at") or "2026-09-24T08:00:00Z") for r in state["rooms"].values()), default="2026-09-24T08:00:00Z")

        runways, alerts = [], []
        for r_id, rd in state["room_details"].items():
            b_limit, c_spend = rd.budget_limit_usd, rd.total_invoiced_cost
            util_pct = round((c_spend / b_limit) * 100, 2) if b_limit > 0 else 0.0
            burn_daily = round(c_spend / max(1, days_el), 6)
            rem_runway = round((b_limit - c_spend) / burn_daily, 1) if burn_daily > 0 else None
            status = "OVERRUN" if util_pct >= 100 else ("WARNING" if util_pct >= 80 else "HEALTHY")
            runways.append(RoomBudgetRunway(room_id=r_id, room_name=rd.room_name, budget_limit_usd=b_limit, cumulative_spend_usd=c_spend, budget_utilization_pct=util_pct, daily_burn_rate_usd=burn_daily, projected_runway_days=rem_runway, status=status))
            if util_pct >= 80:
                alerts.append(FinOpsAnomalyAlert(alert_id=f"alt-{r_id}-{uuid.uuid4().hex[:6]}", room_id=r_id, severity="CRITICAL" if util_pct >= 100 else "WARNING", title=f"Grant Budget Exceeded ({util_pct}%)", description=f"Room spend (${c_spend}) approaching grant limit (${b_limit}).", metric_name="budget_utilization_pct", detected_value=util_pct, threshold_value=80.0, created_at=datetime.now(timezone.utc).isoformat()))
            if rd.capacity.compute_core_hours > 50 and rd.capacity.bigquery_bytes_scanned == 0:
                alerts.append(FinOpsAnomalyAlert(alert_id=f"alt-idle-{r_id}-{uuid.uuid4().hex[:6]}", room_id=r_id, severity="WARNING", title="Potential Idle VM Runtime", description=f"Active VM runtime ({rd.capacity.compute_core_hours}h) without BigQuery workload.", metric_name="compute_core_hours", detected_value=rd.capacity.compute_core_hours, threshold_value=50.0, created_at=datetime.now(timezone.utc).isoformat()))

        return FinOpsSummaryResponse(
            invoice_month=state["invoice_month"], start_date=_clean(start_date), end_date=_clean(end_date),
            min_creation_date=min_created, total_grant_budget=round(total_grant, 2),
            total_fleet_cost=round(total_fleet, 6), cumulative_inception_cost=round(total_fleet, 6),
            spend_since_inception=round(total_fleet, 6),
            total_researcher_cost=round(total_res, 6), total_shared_overhead_cost=round(total_ovh, 6),
            hub_infrastructure_cost=round(hub_cost, 6), forecasted_monthly_cost=forecast, currency="USD",
            cost_drivers=cost_drivers, capacity=fleet_capacity, runway_metrics=runways, anomaly_alerts=alerts,
            projects=projects_breakdown, institutes=institutes_summary, rooms=list(state["room_details"].values()),
            sku_summary=all_skus,
        )

    @cached_endpoint(ttl_seconds=45, key_prefix="finops_room")
    def get_room_cost(self, room_id: str, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> RoomFinOpsDetailResponse:
        state, _, _, _, _ = self._build_allocation(_clean(invoice_month), start_date, end_date)
        if room_id not in state["room_details"]: raise ValueError(f"Research room '{room_id}' not found in registry.")
        return state["room_details"][room_id]

    def get_researcher_attributions(self, invoice_month: Optional[str] = None, room_id: Optional[str] = None, institute_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[ResearcherCostDetail]:
        state, _, _, _, _ = self._build_allocation(_clean(invoice_month), start_date, end_date)
        return [r for r_id, r_det in state["room_details"].items() if not (room_id and r_id != room_id) for r in r_det.researchers if not (institute_id and r.institute_id != institute_id)]

    @cached_endpoint(ttl_seconds=45, key_prefix="finops_researcher")
    def get_researcher_cost(self, email: str, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        clean_email = email.strip().lower()
        state, _, _, _, _ = self._build_allocation(_clean(invoice_month), start_date, end_date)
        room_allocations, total_spend, sku_breakdown = [], 0.0, defaultdict(float)
        researcher_name, institute_id = clean_email, ""
        for room_id, r_det in state["room_details"].items():
            for r in r_det.researchers:
                if r.email.strip().lower() == clean_email:
                    researcher_name, institute_id = r.name, r.institute_id
                    total_spend += r.total_allocated_cost
                    room_allocations.append({"room_id": room_id, "room_name": r_det.room_name, "allocated_cost": r.total_allocated_cost, "telemetry_usage": r.telemetry_usage.dict() if hasattr(r.telemetry_usage, "dict") else r.telemetry_usage, "sku_attributions": [s.dict() if hasattr(s, "dict") else s for s in r.sku_attributions]})
                    for s in r.sku_attributions: sku_breakdown[s.sku_description] += s.allocated_cost
        return {"email": clean_email, "name": researcher_name, "institute_id": institute_id, "total_spend": round(total_spend, 6), "currency": "USD", "rooms_count": len(room_allocations), "room_allocations": room_allocations, "sku_breakdown": [{"sku_description": k, "cost": round(v, 6)} for k, v in sku_breakdown.items()]}

    def get_researcher_spend(self, email: str, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        return self.get_researcher_cost(email, invoice_month, start_date, end_date)

    def get_institute_cost(self, institute_id: str, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> InstituteCostBreakdown:
        if not state: state, _, _, _, _ = self._build_allocation(_clean(invoice_month), start_date, end_date)
        if institute_id not in state["institutes"]: raise ValueError(f"Institute '{institute_id}' not found in hub registry.")
        res_list = [r for r_det in state["room_details"].values() for r in r_det.researchers if r.institute_id == institute_id]
        rooms_inv = sorted(list({r_det.room_id for r_det in state["room_details"].values() for r in r_det.researchers if r.institute_id == institute_id}))
        sku_agg: Dict[Tuple[str, str], float] = defaultdict(float)
        for r in res_list:
            for s in r.sku_attributions: sku_agg[("Attributed SKU", s.sku_description)] += s.allocated_cost
        return InstituteCostBreakdown(institute_id=institute_id, institute_name=state["institutes"][institute_id].get("name", institute_id), total_allocated_cost=round(sum(r.total_allocated_cost for r in res_list), 6), currency="USD", invoice_month=state["invoice_month"], researcher_count=len(res_list), rooms_involved=rooms_inv, researchers=res_list, sku_breakdown=[SKUBillingItem(service_description=k[0], sku_description=k[1], cost=round(v, 6), currency="USD") for k, v in sku_agg.items()])

    @cached_endpoint(ttl_seconds=45, key_prefix="finops_matrix")
    def get_allocation_matrix(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> FinOpsAllocationMatrixResponse:
        state, total_fleet, total_res, total_ovh, hub_cost = self._build_allocation(_clean(invoice_month), start_date, end_date)
        matrix: Dict[str, Dict[str, List[ResearcherCostDetail]]] = defaultdict(lambda: defaultdict(list))
        for r_det in state["room_details"].values():
            for r in r_det.researchers: matrix[r.institute_id][r_det.room_id].append(r)
        variance = round(abs(total_fleet - (total_res + total_ovh + hub_cost)), 6)
        return FinOpsAllocationMatrixResponse(invoice_month=state["invoice_month"], total_allocated_cost=round(total_res, 6), currency="USD", reconciliation_status="BALANCED" if variance < 0.05 else "DISCREPANCY", total_invoice_cost=round(total_fleet, 6), total_researcher_allocated_cost=round(total_res, 6), total_shared_overhead_cost=round(total_ovh, 6), total_hub_infrastructure_cost=round(hub_cost, 6), variance=variance, matrix=matrix)

    @cached_endpoint(ttl_seconds=45, key_prefix="finops_forecast")
    def get_forecast(self, invoice_month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> FinOpsForecastResponse:
        inv_mo = _clean(invoice_month)
        state, total_fleet, _, _, _ = self._build_allocation(inv_mo, start_date, end_date)
        active_mo = inv_mo or (self._get_current_invoice_month() if state["invoice_month"] in ("ALL_TIME", "CUSTOM_RANGE") else state["invoice_month"])
        days_el, days_mo = self._get_days_context(active_mo)
        daily = total_fleet / days_el if days_el > 0 else 0.0
        return FinOpsForecastResponse(invoice_month=state["invoice_month"], days_elapsed=days_el, days_in_month=days_mo, current_mtd_cost=round(total_fleet, 6), daily_run_rate=round(daily, 6), forecasted_monthly_cost=round(daily * days_mo, 6), currency="USD", forecast_confidence=0.95)


_finops_service_instance: Optional[FinOpsService] = None


def get_finops_service() -> FinOpsService:
    global _finops_service_instance
    if _finops_service_instance is None: _finops_service_instance = FinOpsService()
    return _finops_service_instance
