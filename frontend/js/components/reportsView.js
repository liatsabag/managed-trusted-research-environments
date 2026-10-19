/**
 * Standardized & Ad-Hoc Governance Reports Component
 * Generates and downloads reports in CSV, PDF (Printable), and JSON formats
 */

import { api } from '../api.js';
import { formatUSD, formatBytes, formatDate } from '../config.js';
import { stateStore } from '../state.js';

let activeReportType = 'FLEET_INVENTORY';
let currentReportData = null;
let reportFilterText = '';

export async function renderReportsView() {
  const container = document.getElementById("view-reports");
  if (!container) return;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Banner -->
      <div class="glass-card p-6 bg-gradient-to-r from-slate-900 to-indigo-950 text-white border-slate-800">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                Statutory Governance Engine
              </span>
              <span class="text-xs text-indigo-300 font-mono">Multi-Format Compliance Exports</span>
            </div>
            <h2 class="text-xl md:text-2xl font-black tracking-tight text-white mt-1">
              Standardized & Ad-Hoc Governance Reports
            </h2>
            <p class="text-xs text-indigo-200/80 mt-1 max-w-2xl">
              Export institutional audit reports, compliance exception logs, Helsinki/ethics renewal horizons, multi-tenant billing sheets, and airlock egress forensic audits.
            </p>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <button id="btn-export-csv" class="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 shadow-md transition cursor-pointer">
              <i class="fa-solid fa-file-csv text-sm"></i>
              <span>Download CSV</span>
            </button>
            <button id="btn-export-json" class="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center gap-2 shadow-md transition cursor-pointer">
              <i class="fa-solid fa-code text-sm"></i>
              <span>Export JSON</span>
            </button>
            <button id="btn-print-pdf" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white font-semibold text-xs border border-slate-700 flex items-center gap-2 transition cursor-pointer">
              <i class="fa-solid fa-print text-sm"></i>
              <span>Print / PDF</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Report Type Selector Tabs -->
      <div class="flex items-center gap-2 overflow-x-auto pb-1" id="report-tabs-nav">
        ${renderReportTabButton('FLEET_INVENTORY', 'fa-hospital', 'Room Fleet Inventory')}
        ${renderReportTabButton('COMPLIANCE_EXCEPTIONS', 'fa-triangle-exclamation', 'Compliance Exceptions')}
        ${renderReportTabButton('APPROVAL_HORIZON', 'fa-calendar-days', 'Approval Expirations Horizon')}
        ${renderReportTabButton('FINOPS_BILLING', 'fa-coins', 'Cost & FinOps Report')}
        ${renderReportTabButton('EGRESS_AUDIT', 'fa-shield-virus', 'Egress Audit Report')}
      </div>

      <!-- Search & Report Metadata Bar -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-card p-4">
        <div id="report-meta-header" class="text-xs text-slate-600">
          <span class="font-bold text-slate-900" id="report-title-label">Loading report...</span>
          <span class="mx-2 text-slate-300">•</span>
          <span id="report-record-count-label">0 records</span>
        </div>

        <div class="relative w-full sm:w-72">
          <input 
            type="text" 
            id="report-search-input" 
            placeholder="Search report records..." 
            value="${reportFilterText}"
            class="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
          />
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
        </div>
      </div>

      <!-- Main Report Tabular Dataset -->
      <div class="glass-card overflow-hidden shadow-sm" id="report-content-card">
        <div class="p-8 text-center text-slate-400" id="report-table-container">
          <i class="fa-solid fa-circle-notch fa-spin text-2xl mb-2 text-blue-600"></i>
          <p class="text-xs font-medium">Generating report dataset from BigQuery telemetry...</p>
        </div>
      </div>

    </div>
  `;

  // Attach tab navigation listeners
  ['FLEET_INVENTORY', 'COMPLIANCE_EXCEPTIONS', 'APPROVAL_HORIZON', 'FINOPS_BILLING', 'EGRESS_AUDIT'].forEach(type => {
    document.getElementById(`tab-rep-${type}`)?.addEventListener('click', () => {
      activeReportType = type;
      reportFilterText = '';
      renderReportsView();
    });
  });

  // Attach search filter
  document.getElementById("report-search-input")?.addEventListener("input", (e) => {
    reportFilterText = e.target.value.toLowerCase();
    renderReportTable(currentReportData);
  });

  // Attach download handlers
  document.getElementById("btn-export-csv")?.addEventListener("click", () => downloadCSV());
  document.getElementById("btn-export-json")?.addEventListener("click", () => downloadJSON());
  document.getElementById("btn-print-pdf")?.addEventListener("click", () => window.print());

  // Fetch report data from backend API
  await loadReportData(activeReportType);
}

function renderReportTabButton(type, icon, label) {
  const isActive = activeReportType === type;
  return `
    <button 
      id="tab-rep-${type}"
      class="px-4 py-2.5 rounded-xl text-xs font-semibold whitespace-nowrap transition flex items-center gap-2 cursor-pointer ${
        isActive 
          ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20 ring-1 ring-blue-500' 
          : 'bg-white/80 hover:bg-slate-100 text-slate-700 border border-slate-200'
      }"
    >
      <i class="fa-solid ${icon} text-xs"></i>
      <span>${label}</span>
    </button>
  `;
}

async function loadReportData(type) {
  const tableContainer = document.getElementById("report-table-container");
  const metaTitle = document.getElementById("report-title-label");
  const metaCount = document.getElementById("report-record-count-label");

  try {
    const data = await api.getReport(type, 'json');
    currentReportData = data;

    if (metaTitle) metaTitle.textContent = data.metadata?.title || type;
    if (metaCount) metaCount.textContent = `${data.records?.length || 0} records (Generated ${formatDate(data.metadata?.generated_at)})`;

    renderReportTable(data);
  } catch (err) {
    if (tableContainer) {
      tableContainer.innerHTML = `
        <div class="text-rose-600 p-6">
          <i class="fa-solid fa-triangle-exclamation text-2xl mb-2"></i>
          <p class="text-xs font-bold">Failed to load report dataset</p>
          <p class="text-[11px] text-slate-500 mt-1">${err.message}</p>
        </div>
      `;
    }
  }
}

function renderReportTable(data) {
  const tableContainer = document.getElementById("report-table-container");
  if (!tableContainer || !data || !data.records) return;

  const records = data.records.filter(r => {
    if (!reportFilterText) return true;
    return JSON.stringify(r).toLowerCase().includes(reportFilterText);
  });

  if (records.length === 0) {
    tableContainer.innerHTML = `
      <div class="py-12 text-center text-slate-400">
        <i class="fa-solid fa-folder-open text-3xl mb-2 text-slate-300"></i>
        <p class="text-xs font-semibold text-slate-600">No matching records found</p>
      </div>
    `;
    return;
  }

  const columns = Object.keys(records[0]);

  tableContainer.innerHTML = `
    <div class="overflow-x-auto">
      <table class="w-full text-left border-collapse text-xs">
        <thead>
          <tr class="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
            ${columns.map(col => `<th class="py-3 px-4">${col.replace(/_/g, ' ')}</th>`).join('')}
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100 font-normal">
          ${records.map(r => `
            <tr class="hover:bg-blue-50/40 transition">
              ${columns.map(col => {
                const val = r[col];
                return `<td class="py-3 px-4">${formatCell(col, val)}</td>`;
              }).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function formatCell(col, val) {
  if (val === null || val === undefined) return '<span class="text-slate-300">—</span>';
  if (Array.isArray(val)) return `<div class="flex flex-wrap gap-1">${val.map(v => `<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono">${v}</span>`).join('')}</div>`;
  if (col.includes('usd') || col.includes('spend') || col.includes('budget') || col.includes('cost')) {
    return `<span class="font-mono font-bold text-slate-900">${formatUSD(val)}</span>`;
  }
  if (col.includes('pct') || col.includes('percent')) {
    const num = Number(val);
    const color = num >= 100 ? 'text-rose-600' : (num >= 80 ? 'text-amber-600' : 'text-emerald-600');
    return `<span class="font-mono font-bold ${color}">${num}%</span>`;
  }
  if (col === 'status' || col === 'decision') {
    const isGood = ['ACTIVE', 'APPROVED', 'COMPLETED', 'HEALTHY'].includes(String(val).toUpperCase());
    const isBad = ['BLOCKED', 'QUARANTINED', 'SUSPENDED', 'EXPIRED', 'MISSING', 'CRITICAL'].includes(String(val).toUpperCase());
    const badgeColor = isGood ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : (isBad ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-amber-50 text-amber-700 border-amber-200');
    return `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}">${val}</span>`;
  }
  if (col === 'risk_level') {
    const color = val === 'HIGH' ? 'bg-rose-100 text-rose-800' : (val === 'MEDIUM' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800');
    return `<span class="px-2 py-0.5 rounded text-[10px] font-bold ${color}">${val}</span>`;
  }
  if (col.includes('date') || col.includes('at')) {
    return `<span class="font-mono text-slate-600">${formatDate(val)}</span>`;
  }
  return `<span class="text-slate-800">${val}</span>`;
}

function downloadCSV() {
  if (!currentReportData || !currentReportData.records) return;
  const url = api.getReportDownloadUrl(activeReportType, 'csv');
  window.open(url, '_blank');
}

function downloadJSON() {
  if (!currentReportData) return;
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentReportData, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `${activeReportType.toLowerCase()}_report.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}
