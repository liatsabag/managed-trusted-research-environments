/**
 * GCP Health Data Platform - REST API Client
 * Connects directly to Google Cloud Run FastAPI Backend
 * ZERO mock data fallback - throws genuine errors on failure
 */

import { CONFIG } from './config.js';

class ApiClient {
  constructor() {
    const defaultBase = CONFIG.DEFAULT_API_BASE;
    const storedBase = localStorage.getItem("gcp_api_base");
    if (storedBase === "/api/v1" && typeof window !== "undefined" && window.location.hostname.includes("run.app")) {
      this.baseUrl = defaultBase;
      localStorage.setItem("gcp_api_base", this.baseUrl);
    } else {
      this.baseUrl = storedBase || defaultBase;
    }
    this.authToken = localStorage.getItem("gcp_auth_token") || "";
    this.isConnected = false;
    this.lastLatency = null;
  }

  setBaseUrl(url) {
    this.baseUrl = url.replace(/\/+$/, "");
    localStorage.setItem("gcp_api_base", this.baseUrl);
  }

  setAuthToken(token) {
    this.authToken = token.trim();
    localStorage.setItem("gcp_auth_token", this.authToken);
  }

  async request(path, options = {}) {
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    const url = `${this.baseUrl}${cleanPath}`;
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (this.authToken) headers["Authorization"] = `Bearer ${this.authToken}`;

    const startTime = performance.now();
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), options.timeout || 15000);
      const res = await fetch(url, { ...options, headers, signal: controller.signal });
      clearTimeout(timeoutId);

      this.lastLatency = Math.round(performance.now() - startTime);
      this.isConnected = true;

      const rawText = await res.text();
      if (!res.ok) {
        let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
        try {
          const parsed = JSON.parse(rawText);
          errorDetail = parsed.detail || errorDetail;
        } catch {
          errorDetail = rawText.slice(0, 150) || errorDetail;
        }
        throw new Error(errorDetail);
      }

      try {
        return JSON.parse(rawText);
      } catch (parseErr) {
        throw new Error(`Invalid JSON response from ${url}: ${rawText.slice(0, 100)}`);
      }
    } catch (err) {
      this.lastLatency = Math.round(performance.now() - startTime);
      this.isConnected = false;
      console.error(`[API Error] ${options.method || 'GET'} ${url}:`, err);
      throw err;
    }
  }

  /* ---------------- Fleet & Rooms ---------------- */

  async getRooms() {
    return await this.request('/rooms');
  }

  async getRoom(roomId) {
    return await this.request(`/rooms/${roomId}`);
  }

  async getRoomPackages(roomId) {
    return await this.request(`/rooms/${roomId}/packages`);
  }

  async updateRoomStatus(roomId, newStatus, reason = "Administrator manual trigger") {
    return await this.request(`/rooms/${roomId}/status`, {
      method: "POST",
      body: JSON.stringify({ new_status: newStatus, reason })
    });
  }

  async downgradeRoom(roomId, reason = "Compliance enforcement: Helsinki/DUA expiration") {
    return await this.request(`/rooms/${roomId}/downgrade`, {
      method: "POST",
      body: JSON.stringify({ reason })
    });
  }

  async reactivateRoom(roomId) {
    return await this.request(`/rooms/${roomId}/reactivate`, {
      method: "POST"
    });
  }

  async addResearcher(roomId, researcherEmail, role = "Researcher") {
    return await this.request(`/rooms/${roomId}/researchers`, {
      method: "POST",
      body: JSON.stringify({
        researcher_email: researcherEmail,
        role: role
      })
    });
  }

  /* ---------------- Partner Institutes ---------------- */

  async getInstitutes() {
    return await this.request('/institutes');
  }

  async getInstitute(instituteId) {
    return await this.request(`/institutes/${instituteId}`);
  }

  /* ---------------- Compliance & Regulatory Gate ---------------- */

  async getComplianceSummary() {
    return await this.request('/compliance/summary');
  }

  async getRoomCompliance(roomId) {
    return await this.request(`/compliance/rooms/${roomId}`);
  }

  async getComplianceHorizons() {
    return await this.request('/compliance/horizons');
  }

  async getExpirationHorizons() {
    return await this.getComplianceHorizons();
  }

  async evaluateOnboardingGate(requestId, proposedRoomId = null, bucketUri = null) {
    if (proposedRoomId || bucketUri) {
      return await this.request(`/requests/${requestId}/evaluate-gate`, {
        method: "POST",
        body: JSON.stringify({
          request_id: requestId,
          proposed_room_id: proposedRoomId,
          document_bucket_uri: bucketUri
        })
      });
    }
    return await this.request(`/compliance/requests/${requestId}/gate`);
  }

  async createRoomRequest(payload) {
    return await this.request('/compliance/requests', {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async enforceCompliance(autoDowngrade = true) {
    return await this.request('/compliance/enforce', {
      method: "POST",
      body: JSON.stringify({ auto_downgrade: autoDowngrade })
    });
  }

  async enforceFleetCompliance() {
    return await this.request('/compliance/enforce', { method: "POST" });
  }

  /* ---------------- Fleet Telemetry & Observability ---------------- */

  async getTelemetryOverview() {
    return await this.request('/telemetry/overview');
  }

  async getQueries(roomId = null, userEmail = null, limit = 50) {
    const params = new URLSearchParams();
    if (roomId) params.append("room_id", roomId);
    if (userEmail) params.append("user_email", userEmail);
    if (limit) params.append("limit", limit.toString());
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/telemetry/queries${qs}`);
  }

  async getAuditFeed(roomId = null, principalEmail = null, limit = null, category = null, researchersOnly = false) {
    const params = new URLSearchParams();
    if (roomId && roomId !== 'ALL') params.append("room_id", roomId);
    if (principalEmail && principalEmail !== 'ALL') params.append("principal_email", principalEmail);
    if (category && category !== 'ALL') params.append("category", category);
    if (researchersOnly) params.append("researchers_only", "true");
    if (limit && limit > 0) params.append("limit", limit.toString());
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/telemetry/audit-feed${qs}`);
  }

  async getRoomInventory(roomId) {
    return await this.request(`/telemetry/rooms/${roomId}/inventory`);
  }

  async getRoomActivity(roomId, limit = 50, researchersOnly = true) {
    const params = new URLSearchParams();
    if (limit) params.append("limit", limit.toString());
    if (researchersOnly !== undefined) params.append("researchers_only", researchersOnly.toString());
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/telemetry/rooms/${roomId}/activity${qs}`);
  }

  async getMonthlyMetrics() {
    return await this.request('/telemetry/metrics/monthly');
  }

  /* ---------------- FinOps & Cost Attribution ---------------- */

  async getFinOpsSummary(invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/summary${qs}`);
  }

  async getResearchers(invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/researchers${qs}`);
  }

  async getResearcherSpend(email, invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/researchers/${encodeURIComponent(email)}/spend${qs}`);
  }

  async getRoomFinOps(roomId, invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/rooms/${roomId}${qs}`);
  }

  async getFinOpsMatrix(invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/matrix${qs}`);
  }

  async getFinOpsForecast(invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/forecast${qs}`);
  }

  /* ---------------- Cloud Infrastructure, Buckets & Environments ---------------- */

  async getInfrastructureOverview() {
    return await this.request('/resources/overview');
  }

  async listStorageBuckets() {
    return await this.request('/resources/buckets');
  }

  async listSharedDatasets() {
    return await this.request('/resources/datasets');
  }

  async listNotebookTemplates() {
    return await this.request('/resources/templates');
  }

  async linkBucket(roomId, bucketName, roleType = "INBOUND") {
    return await this.request('/resources/buckets/link', {
      method: 'POST',
      body: JSON.stringify({
        room_id: roomId,
        bucket_name: bucketName,
        role_type: roleType
      })
    });
  }

  async detachBucket(roomId, bucketName) {
    return await this.request('/resources/buckets/detach', {
      method: 'POST',
      body: JSON.stringify({
        room_id: roomId,
        bucket_name: bucketName
      })
    });
  }

  /* ---------------- Airlock & Data Egress Governance ---------------- */

  async getAirlockCandidates(roomId = null) {
    const qs = roomId ? `?room_id=${roomId}` : "";
    return await this.request(`/airlock/candidates${qs}`);
  }

  async scanAirlockFile(roomId, fileName) {
    return await this.request('/airlock/scan', {
      method: 'POST',
      body: JSON.stringify({
        room_id: roomId,
        file_name: fileName
      })
    });
  }

  async takeAirlockAction(roomId, fileName, action, comment = "") {
    return await this.request('/airlock/action', {
      method: 'POST',
      body: JSON.stringify({
        room_id: roomId,
        file_name: fileName,
        action: action,
        comment: comment
      })
    });
  }

  async getFinOpsSummary(invoiceMonth = null, startDate = null, endDate = null) {
    const params = new URLSearchParams();
    if (invoiceMonth) params.append("invoice_month", invoiceMonth);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.request(`/finops/summary${qs}`);
  }

  /* ---------------- Reports & Governance Documentation ---------------- */

  async getReportsList() {
    return await this.request('/reports/list');
  }

  async getReport(reportType, format = "json") {
    const endpointMap = {
      FLEET_INVENTORY: '/reports/fleet-inventory',
      COMPLIANCE_EXCEPTIONS: '/reports/compliance-exceptions',
      APPROVAL_HORIZON: '/reports/approval-horizon',
      FINOPS_BILLING: '/reports/cost-finops',
      EGRESS_AUDIT: '/reports/egress-audit',
    };
    const endpoint = endpointMap[reportType] || `/reports/${reportType.toLowerCase().replace(/_/g, '-')}`;
    return await this.request(`${endpoint}?format=${format}`);
  }

  getReportDownloadUrl(reportType, format = "csv") {
    const endpointMap = {
      FLEET_INVENTORY: '/reports/fleet-inventory',
      COMPLIANCE_EXCEPTIONS: '/reports/compliance-exceptions',
      APPROVAL_HORIZON: '/reports/approval-horizon',
      FINOPS_BILLING: '/reports/cost-finops',
      EGRESS_AUDIT: '/reports/egress-audit',
    };
    const endpoint = endpointMap[reportType] || `/reports/${reportType.toLowerCase().replace(/_/g, '-')}`;
    return `${this.baseUrl}${endpoint}?format=${format}`;
  }

  /* ---------------- Health & Diagnostics ---------------- */

  async checkHealth() {
    return await this.request('/health');
  }
}

export const api = new ApiClient();
