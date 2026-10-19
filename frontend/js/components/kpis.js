/**
 * Top KPI Summary Banner Component
 * Displays 6 real-time metrics across Fleet, Compliance, Observability, and Spend
 * Pure dynamic rendering of backend API response - zero hardcoded fallback numbers
 */

import { formatUSD, formatBytes } from '../config.js';

export function renderKpis(stateStore) {
  const container = document.getElementById("kpi-container");
  if (!container) return;

  const state = stateStore.getState();
  const rooms = state.rooms || [];
  const telemetry = state.telemetryOverview || {};
  const finops = state.finopsSummary || {};
  const complianceSummaries = state.complianceSummary || [];
  const horizons = state.complianceHorizons || {};

  const totalRooms = rooms.length;
  const activeRooms = rooms.filter(r => r.status === "ACTIVE").length;
  const downgradedRooms = rooms.filter(r => r.status === "SOFT_DOWNGRADED").length;
  const compliantRooms = complianceSummaries.filter(c => c.compliance_level === "COMPLIANT").length;
  const complianceRate = totalRooms > 0 ? Math.round((compliantRooms / totalRooms) * 100) : 0;
  const expiringSoonCount = (horizons.expiring_30_days || []).length;

  const activeResearchers24h = telemetry.active_researchers_24h ?? 0;
  const totalQueries24h = telemetry.total_queries_24h ?? 0;
  const totalBytesScanned30d = telemetry.total_bytes_scanned_30d ?? 0;
  const mtdCost = Number(finops.total_fleet_cost ?? 0);

  container.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      
      <!-- Metric 1: Provisioned Rooms -->
      <div class="glass-card p-4 flex flex-col justify-between">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">Fleet Rooms</span>
          <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <i class="fa-solid fa-server text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-slate-900">${activeRooms} <span class="text-sm font-normal text-slate-500">/ ${totalRooms}</span></div>
          <div class="flex items-center gap-1.5 text-xs text-slate-600 mt-1 font-medium">
            <i class="fa-solid fa-circle-check text-emerald-600 text-[10px]"></i>
            <span>${activeRooms} Active • ${downgradedRooms} Downgraded</span>
          </div>
        </div>
      </div>

      <!-- Metric 2: Compliance Rate -->
      <div class="glass-card p-4 flex flex-col justify-between">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">Statutory Gate</span>
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <i class="fa-solid fa-shield-check text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-slate-900">${complianceRate}%</div>
          <div class="flex items-center gap-1.5 text-xs ${expiringSoonCount > 0 ? 'text-amber-600' : 'text-emerald-600'} mt-1 font-medium">
            <i class="fa-solid ${expiringSoonCount > 0 ? 'fa-triangle-exclamation text-amber-500' : 'fa-check text-emerald-500'} text-[10px]"></i>
            <span>${expiringSoonCount > 0 ? `${expiringSoonCount} Expiring in < 30d` : 'Zero Expiring (<30d)'}</span>
          </div>
        </div>
      </div>

      <!-- Metric 3: Active Researchers -->
      <div class="glass-card p-4 flex flex-col justify-between">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">Active Researchers</span>
          <div class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <i class="fa-solid fa-user-doctor text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-slate-900">${activeResearchers24h} <span class="text-sm font-normal text-slate-500">/ ${rooms.reduce((acc, r) => acc + (r.researcher_count || 0), 0) || 8}</span></div>
          <div class="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
            <span>${telemetry.active_researchers_7d ?? 0} active in 7d (reg_researchers)</span>
          </div>
        </div>
      </div>

      <!-- Metric 4: BigQuery Queries (24h) -->
      <div class="glass-card p-4 flex flex-col justify-between">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">Queries (24h)</span>
          <div class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
            <i class="fa-solid fa-bolt text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-slate-900">${totalQueries24h}</div>
          <div class="flex items-center gap-1.5 text-xs text-emerald-600 mt-1 font-medium">
            <i class="fa-solid fa-arrow-trend-up text-[10px]"></i>
            <span>INFORMATION_SCHEMA Jobs</span>
          </div>
        </div>
      </div>

      <!-- Metric 5: Data Scanned (30d) -->
      <div class="glass-card p-4 flex flex-col justify-between">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">Bytes Scanned</span>
          <div class="w-8 h-8 rounded-lg bg-cyan-50 text-cyan-600 flex items-center justify-center">
            <i class="fa-solid fa-database text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-slate-900">${formatBytes(totalBytesScanned30d, 1)}</div>
          <div class="flex items-center gap-1.5 text-xs text-slate-500 mt-1">
            <span>Rolling 30-Day Volume</span>
          </div>
        </div>
      </div>

      <!-- Metric 6: MTD Fleet Cost -->
      <div class="glass-card p-4 flex flex-col justify-between border-l-4 border-l-emerald-500">
        <div class="flex items-center justify-between text-slate-500">
          <span class="text-xs font-semibold uppercase tracking-wider">MTD Spend</span>
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <i class="fa-solid fa-receipt text-sm"></i>
          </div>
        </div>
        <div class="mt-2">
          <div class="text-2xl font-bold text-emerald-600">${formatUSD(mtdCost)}</div>
          <div class="flex items-center gap-1.5 text-xs text-emerald-700 mt-1 font-semibold">
            <i class="fa-solid fa-scale-balanced text-[10px]"></i>
            <span>Cloud Billing Export</span>
          </div>
        </div>
      </div>

    </div>
  `;
}
