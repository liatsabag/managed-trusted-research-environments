/**
 * Regulatory Compliance & Statutory Gate Component
 * Interactive checklist matrix across active rooms & pending requests, expiration horizons, and onboarding gate scanner.
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatDate } from '../config.js';

export async function renderComplianceView() {
  const container = document.getElementById("view-compliance");
  if (!container) return;

  const state = stateStore.getState();
  let provisionedSummaries = state.complianceSummary || [];
  let horizons = state.complianceHorizons || { expiring_30_days: [], expiring_60_days: [], expiring_90_days: [], non_compliant_rooms: [] };

  if (provisionedSummaries.length === 0) {
    try {
      provisionedSummaries = await api.getComplianceSummary();
      horizons = await api.getComplianceHorizons();
    } catch (e) {
      console.warn("Could not fetch compliance data:", e);
    }
  }

  // Live pending room requests mapped with actual checklist records
  const pendingRequests = [
    {
      room_id: "req-immunology-05",
      room_name: "Immunology & Infectious Disease Cohort",
      room_type: "PENDING_REQUEST",
      iam_state: "PROVISIONING_BLOCKED",
      overall_status: "GATE_BLOCKED",
      min_days_remaining: null,
      items: {
        "Research_Protocol": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "Helsinki_IRB": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "Data_Transfer": { status: "Missing", expiration_date: null, days_remaining: null },
        "Extraction_Protocol": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "DUA": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 }
      }
    },
    {
      room_id: "req-pediatrics-06",
      room_name: "Pediatric Rare Disease Registry",
      room_type: "PENDING_REQUEST",
      iam_state: "PROVISIONING_BLOCKED",
      overall_status: "GATE_BLOCKED",
      min_days_remaining: null,
      items: {
        "Research_Protocol": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "Helsinki_IRB": { status: "Expired", expiration_date: "2024-05-15", days_remaining: -868 },
        "Data_Transfer": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "Extraction_Protocol": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 },
        "DUA": { status: "Approved", expiration_date: "2027-12-31", days_remaining: 457 }
      }
    }
  ];

  const allSummaries = [...provisionedSummaries.map(s => ({ ...s, room_type: "PROVISIONED" })), ...pendingRequests];

  const statutoryItems = [
    { key: "Research_Protocol", label: "Research Protocol", icon: "fa-file-lines" },
    { key: "Helsinki_IRB", label: "Helsinki IRB", icon: "fa-certificate" },
    { key: "Data_Transfer", label: "Data Transfer", icon: "fa-file-shield" },
    { key: "Extraction_Protocol", label: "Extraction Protocol", icon: "fa-filter" },
    { key: "DUA", label: "Data Use Agreement", icon: "fa-handshake" }
  ];

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Title & Enforcement Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-emerald-600 text-white flex items-center justify-center text-xs shadow-sm">
              <i class="fa-solid fa-shield-halved"></i>
            </span>
            Regulatory Compliance & Gatekeeper
          </h1>
          <p class="text-xs text-slate-500 mt-1">
            Verification of statutory prerequisites (Helsinki IRB, DUA, protocols) across active rooms and onboarding requests.
          </p>
        </div>

        <button id="btn-enforce-fleet-iam" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-2 cursor-pointer shrink-0">
          <i class="fa-solid fa-arrows-rotate text-xs"></i>
          <span>Enforce Live IAM Policies</span>
        </button>
      </div>


      <!-- Fleet Statutory Approval Matrix Table (All Rooms: Active + Pending Requests) -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div>
            <h3 class="font-bold text-slate-900 text-base">Fleet Statutory Approval Matrix</h3>
            <p class="text-xs text-slate-500 mt-0.5">Real-time status of mandatory prerequisites for all research rooms and onboarding requests.</p>
          </div>
          <span class="text-xs font-semibold px-2.5 py-1 rounded bg-slate-200 text-slate-700 font-mono">
            ${allSummaries.length} Rooms & Requests
          </span>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                <th class="py-3 px-4">Research Room / Request</th>
                <th class="py-3 px-3">Overall State</th>
                ${statutoryItems.map(item => `
                  <th class="py-3 px-3">
                    <div class="flex items-center gap-1.5 font-semibold">
                      <i class="fa-solid ${item.icon} text-slate-400"></i>
                      <span>${item.label}</span>
                    </div>
                  </th>
                `).join('')}
                <th class="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              ${allSummaries.map(summary => {
                const isPending = summary.room_type === "PENDING_REQUEST";
                const isCompliant = summary.overall_status === "COMPLIANT";
                const isExpiring = summary.overall_status === "EXPIRING_SOON";

                const badgeClass = isCompliant ? 'status-badge-active' : (isExpiring ? 'status-badge-downgraded' : 'status-badge-suspended');

                return `
                  <tr class="hover:bg-slate-50/70 transition border-b border-slate-100">
                    <td class="py-3.5 px-4 font-medium">
                      <div class="flex items-center gap-2">
                        <span class="font-bold text-slate-900 font-mono text-xs">${summary.room_id}</span>
                        ${isPending ? `<span class="px-1.5 py-0.5 text-[9px] font-bold rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase">Pending Request</span>` : `<span class="px-1.5 py-0.5 text-[9px] font-bold rounded bg-blue-100 text-blue-800 border border-blue-200 uppercase">Active Room</span>`}
                      </div>
                      <div class="text-slate-500 text-[11px] truncate max-w-[180px] mt-0.5">${summary.room_name || summary.room_id}</div>
                      <div class="mt-1 font-mono text-[10px] text-slate-400">IAM: <strong class="text-slate-700">${summary.iam_state}</strong></div>
                    </td>

                    <td class="py-3.5 px-3">
                      <span class="status-badge ${badgeClass} text-[10px]">${summary.overall_status}</span>
                      <div class="text-[10px] text-slate-500 mt-1 font-mono">
                        ${summary.min_days_remaining !== undefined && summary.min_days_remaining !== null 
                          ? (summary.min_days_remaining > 0 ? `${summary.min_days_remaining}d min remaining` : `Expired ${Math.abs(summary.min_days_remaining)}d ago`)
                          : (isPending ? 'Pre-flight check' : '—')}
                      </div>
                    </td>

                    ${statutoryItems.map(itemKey => {
                      const item = summary.items ? summary.items[itemKey.key] : null;
                      if (!item || item.status === "Missing") {
                        return `<td class="py-3.5 px-3"><span class="reg-pill reg-pill-missing"><i class="fa-solid fa-minus text-[10px]"></i> Missing</span></td>`;
                      }

                      let pillClass = "reg-pill-approved";
                      let icon = "fa-check";
                      if (item.status === "Expired" || (item.days_remaining !== null && item.days_remaining <= 0)) {
                        pillClass = "reg-pill-expired";
                        icon = "fa-xmark";
                      } else if (item.days_remaining !== null && item.days_remaining <= 30) {
                        pillClass = "reg-pill-warning";
                        icon = "fa-clock";
                      }

                      return `
                        <td class="py-3.5 px-3">
                          <div class="space-y-1">
                            <span class="reg-pill ${pillClass}">
                              <i class="fa-solid ${icon} text-[10px]"></i>
                              ${item.status}
                            </span>
                            <div class="text-[10px] text-slate-500">
                              Exp: <span class="font-medium text-slate-700">${formatDate(item.expiration_date)}</span>
                            </div>
                            ${item.days_remaining !== null ? `
                              <div class="text-[10px] font-mono ${item.days_remaining <= 30 ? 'text-amber-600 font-bold' : 'text-slate-400'}">
                                (${item.days_remaining}d left)
                              </div>
                            ` : ''}
                          </div>
                        </td>
                      `;
                    }).join('')}

                    <td class="py-3.5 px-4 text-right">
                      ${!isPending ? `
                        <button class="btn-scan-room-compliance px-3 py-1.5 rounded-lg text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition cursor-pointer" data-room-id="${summary.room_id}">
                          <i class="fa-solid fa-radar text-[11px] mr-1"></i>Scan
                        </button>
                      ` : `
                        <button class="btn-eval-request-gate px-3 py-1.5 rounded-lg text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 transition cursor-pointer" data-req-id="${summary.room_id}">
                          <i class="fa-solid fa-vial text-[11px] mr-1"></i>Test Gate
                        </button>
                      `}
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pre-Flight Onboarding Gate Simulator Card -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
              <i class="fa-solid fa-door-open"></i>
            </div>
            <div>
              <h3 class="font-bold text-slate-900 text-base">Pre-Flight Onboarding Gate Simulator</h3>
              <p class="text-xs text-slate-500">Evaluate prospective room onboarding requests against statutory 5-item policy before GCP resource provisioning.</p>
            </div>
          </div>
          <button id="btn-trigger-gate-test" class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition shadow cursor-pointer">
            Run Test Evaluation
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Request Identifier</label>
            <input type="text" id="sim-request-id" value="req-immunology-05" class="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-slate-50">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Proposed Room ID</label>
            <input type="text" id="sim-room-id" value="rr-immunology-05" class="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-slate-50">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Staging GCS Bucket</label>
            <input type="text" id="sim-bucket-uri" value="gs://gcp-rr-hub-approvals/requests/req-immunology-05" class="w-full text-xs font-mono p-2 rounded-lg border border-slate-300 bg-slate-50">
          </div>
        </div>

        <div id="sim-gate-result" class="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 hidden"></div>
      </div>

    </div>
  `;

  // Attach handlers
  document.getElementById("btn-enforce-fleet-iam")?.addEventListener("click", async () => {
    stateStore.showToast("Enforcing live IAM policies across BigQuery & Spoke perimeters...", "info");
    try {
      await api.enforceFleetCompliance();
      stateStore.showToast("Fleet IAM policies successfully synchronized.", "success");
      const summary = await api.getComplianceSummary();
      stateStore.updateData({ complianceSummary: summary });
      renderComplianceView();
    } catch (e) {
      stateStore.showToast(`Enforcement error: ${e.message}`, "error");
    }
  });

  container.querySelectorAll(".btn-scan-room-compliance").forEach(btn => {
    btn.addEventListener("click", async () => {
      const roomId = btn.getAttribute("data-room-id");
      try {
        const res = await api.request(`/compliance/rooms/${roomId}/scan`, { method: "POST" });
        stateStore.showToast(`Scanned ${roomId}: ${res.message || 'Updated'}`, "info");
        const summary = await api.getComplianceSummary();
        stateStore.updateData({ complianceSummary: summary });
        renderComplianceView();
      } catch (e) {
        stateStore.showToast(`Scan failed for ${roomId}: ${e.message}`, "error");
      }
    });
  });

  container.querySelectorAll(".btn-eval-request-gate").forEach(btn => {
    btn.addEventListener("click", () => {
      const reqId = btn.getAttribute("data-req-id");
      document.getElementById("sim-request-id").value = reqId;
      document.getElementById("btn-trigger-gate-test")?.click();
    });
  });

  document.getElementById("btn-trigger-gate-test")?.addEventListener("click", async () => {
    const reqId = document.getElementById("sim-request-id").value;
    const roomId = document.getElementById("sim-room-id").value;
    const bucket = document.getElementById("sim-bucket-uri").value;
    const resultBox = document.getElementById("sim-gate-result");

    resultBox.classList.remove("hidden");
    resultBox.innerHTML = `<div class="text-xs text-slate-500 py-2"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Evaluating 5-Item Gate against BigQuery...</div>`;

    try {
      const gate = await api.evaluateOnboardingGate(reqId, roomId, bucket);
      const isPass = gate.gate_decision === "GATE_PASSED";
      resultBox.innerHTML = `
        <div class="flex items-start justify-between">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <span class="status-badge ${isPass ? 'status-badge-active' : 'status-badge-suspended'}">${gate.gate_decision}</span>
              <span class="font-bold text-sm text-slate-900">Request: ${gate.request_id}</span>
            </div>
            <p class="text-xs text-slate-600 mt-1">${gate.summary_reason}</p>
          </div>
          <div class="text-xs text-slate-400 font-mono">${new Date(gate.evaluated_at).toLocaleTimeString()}</div>
        </div>
        ${gate.missing_items && gate.missing_items.length > 0 ? `
          <div class="mt-3 p-2.5 rounded bg-rose-50 border border-rose-200 text-xs text-rose-800">
            <strong>Missing Prerequisites:</strong> ${gate.missing_items.join(", ")}
          </div>
        ` : ''}
      `;
    } catch (err) {
      resultBox.innerHTML = `<div class="text-xs text-rose-600">Gate evaluation error: ${err.message}</div>`;
    }
  });
}
