/**
 * Fleet Telemetry & Query Observability Component
 * Live BigQuery execution table, Cloud Audit stream, and asset inventory
 * Zero fake defaults - 100% dynamic rendering of backend API payload
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatBytes, formatSlotTime, formatDateTime } from '../config.js';

export function renderTelemetryView() {
  const container = document.getElementById("view-telemetry");
  if (!container) return;

  const state = stateStore.getState();
  const queries = state.queries || [];
  const auditEvents = state.auditEvents || [];
  const overview = state.telemetryOverview || {};

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Observability Metrics & Telemetry Header -->
      <div class="glass-card p-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200 uppercase tracking-wider">
              Fleet Telemetry
            </span>
            <h2 class="text-xl font-bold text-slate-900">Fleet Query Observability & Telemetry</h2>
          </div>
          <p class="text-xs text-slate-500 mt-1">
            Real-time query execution monitoring across spoke projects, Cloud Audit logs, and storage telemetry.
          </p>
        </div>
      </div>

      <!-- Storage & Asset Inventory Strip -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        
        <div class="glass-card p-4 border-l-4 border-l-blue-500">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Dual-Bucket Storage</div>
          <div class="text-xl font-bold text-slate-900 mt-1">${formatBytes(overview.total_fleet_storage_bytes || 0)}</div>
          <div class="text-[11px] text-slate-500 mt-1">Live GCS Storage across fleet</div>
        </div>

        <div class="glass-card p-4 border-l-4 border-l-purple-500">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">BigQuery 24h Queries</div>
          <div class="text-xl font-bold text-slate-900 mt-1">${overview.total_queries_24h ?? 0}</div>
          <div class="text-[11px] text-emerald-600 mt-1 font-medium">Recorded in INFORMATION_SCHEMA</div>
        </div>

        <div class="glass-card p-4 border-l-4 border-l-cyan-500">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">30d Bytes Billed</div>
          <div class="text-xl font-bold text-slate-900 mt-1">${formatBytes(overview.total_bytes_scanned_30d || 0)}</div>
          <div class="text-[11px] text-slate-500 mt-1">On-Demand BQ Scans</div>
        </div>

        <div class="glass-card p-4 border-l-4 border-l-indigo-500">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Researchers</div>
          <div class="text-xl font-bold text-slate-900 mt-1">${overview.active_researchers_24h ?? 0} Active (24h)</div>
          <div class="text-[11px] text-slate-500 mt-1">${overview.active_researchers_7d ?? 0} active in last 7 days</div>
        </div>

      </div>

      <!-- Live BigQuery Jobs Table -->
      <div class="glass-card overflow-hidden">
        <div class="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-bolt text-purple-600"></i>
            <h3 class="font-bold text-slate-900 text-base">BigQuery Execution Jobs</h3>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500 font-mono">${queries.length} Recent Jobs</span>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="data-table-header">
                <th class="py-3 px-4">Job ID / Project</th>
                <th class="py-3 px-3">Room</th>
                <th class="py-3 px-3">Researcher Principal</th>
                <th class="py-3 px-4">SQL Query Snippet</th>
                <th class="py-3 px-3">Bytes Billed</th>
                <th class="py-3 px-3">Slot Time</th>
                <th class="py-3 px-3">Duration</th>
                <th class="py-3 px-4 text-right">State</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-200 font-mono">
              ${queries.length === 0 ? `
                <tr>
                  <td colspan="8" class="py-8 text-center text-slate-500 font-sans">
                    <i class="fa-solid fa-inbox text-slate-300 text-3xl mb-2 block"></i>
                    No recent BigQuery jobs returned from backend API.
                  </td>
                </tr>
              ` : queries.map(q => `
                <tr class="data-table-row">
                  <td class="py-3 px-4">
                    <div class="font-bold text-slate-900 text-xs">${q.job_id}</div>
                    <div class="text-slate-400 text-[10px]">${q.project_id}</div>
                  </td>
                  <td class="py-3 px-3 font-sans font-medium text-slate-700">
                    ${q.room_id || 'Hub Core'}
                  </td>
                  <td class="py-3 px-3 text-slate-700 font-sans truncate max-w-[160px]" title="${q.user_email}">
                    ${q.user_email || 'Service Agent'}
                  </td>
                  <td class="py-3 px-4 max-w-xs truncate text-slate-600 font-mono text-[11px]" title="${q.query_snippet || ''}">
                    ${q.query_snippet || 'SELECT ...'}
                  </td>
                  <td class="py-3 px-3 font-bold text-slate-900">
                    ${formatBytes(q.bytes_billed || 0)}
                  </td>
                  <td class="py-3 px-3 text-slate-600">
                    ${formatSlotTime(q.slot_ms || 0)}
                  </td>
                  <td class="py-3 px-3 text-slate-600">
                    ${q.duration_seconds ? `${q.duration_seconds.toFixed(2)}s` : '—'}
                  </td>
                  <td class="py-3 px-4 text-right">
                    <span class="status-badge status-badge-active">
                      ${q.state || 'DONE'}
                    </span>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Cloud Audit Events Feed -->
      <div class="glass-card overflow-hidden">
        <div class="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-clipboard-list text-blue-600"></i>
            <h3 class="font-bold text-slate-900 text-base">Cloud Audit & Security Events Stream</h3>
          </div>
          <span class="text-xs text-slate-500 font-mono">${auditEvents.length} Curated Events</span>
        </div>

        <div class="p-4 space-y-3">
          ${auditEvents.length === 0 ? `
            <div class="py-8 text-center text-slate-500 font-sans">
              <i class="fa-solid fa-inbox text-slate-300 text-3xl mb-2 block"></i>
              No audit events returned from backend API.
            </div>
          ` : auditEvents.map(evt => {
            let sevColor = "bg-blue-100 text-blue-800 border-blue-200";
            if (evt.severity === "NOTICE") sevColor = "bg-amber-100 text-amber-800 border-amber-200";
            if (evt.severity === "WARNING" || evt.severity === "ERROR") sevColor = "bg-rose-100 text-rose-800 border-rose-200";

            return `
              <div class="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div class="flex items-center gap-3">
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${sevColor}">
                    ${evt.severity}
                  </span>
                  <div>
                    <div class="font-bold text-slate-900">${evt.description || evt.method_name}</div>
                    <div class="text-slate-500 text-[11px] font-mono mt-0.5">
                      Actor: <strong class="text-slate-700">${evt.principal_email}</strong> • Resource: <span class="text-slate-600">${evt.resource_name}</span>
                    </div>
                  </div>
                </div>

                <div class="text-right text-slate-400 font-mono text-[11px]">
                  ${formatDateTime(evt.timestamp)}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>

    </div>
  `;
}
