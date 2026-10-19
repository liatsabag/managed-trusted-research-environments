/**
 * Page 2: Dedicated Room Details Page Component
 * Quick room switcher, clean activity banner, stacked researcher roster & audit stream, datasets, notebooks, and air-lock
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatUSD, formatBytes, formatDateTime } from '../config.js';
import { ROOM_ASSET_METADATA } from './roomDetailAssets.js';
import {
  renderBigQueryCard,
  renderResearchersRosterCard,
  renderStorageCard,
  renderNotebooksCard,
  renderAuditEventStreamCard,
  renderExportQuarantineCard
} from './roomDetailCards.js';

export async function renderRoomDetailView(roomId) {
  const container = document.getElementById("view-room-detail");
  if (!container) return;

  if (!roomId) {
    container.innerHTML = `<div class="p-8 text-center text-slate-500 bg-white rounded-xl">No room selected.</div>`;
    return;
  }

  // Loading skeleton
  container.innerHTML = `
    <div class="space-y-6 animate-pulse">
      <div class="h-8 bg-slate-200 rounded w-1/4"></div>
      <div class="h-28 bg-slate-200 rounded-xl"></div>
      <div class="h-16 bg-slate-200 rounded-xl"></div>
      <div class="space-y-6">
        <div class="h-48 bg-slate-200 rounded-xl"></div>
        <div class="h-48 bg-slate-200 rounded-xl"></div>
      </div>
    </div>
  `;

  try {
    const [room, inventory, activity] = await Promise.all([
      api.getRoom(roomId),
      api.getRoomInventory(roomId).catch(() => null),
      api.getRoomActivity(roomId).catch(() => ({ recent_queries: [], recent_audit_events: [] }))
    ]);
    renderRoomDetailContent(container, room, inventory, activity);
  } catch (err) {
    container.innerHTML = `
      <div class="p-8 bg-white rounded-xl border border-rose-200 text-center">
        <h3 class="text-base font-bold text-slate-800">Failed to Load Room Details</h3>
        <p class="text-xs text-slate-500 mt-1">${err.message}</p>
        <button id="btn-err-back" class="mt-4 px-4 py-2 bg-slate-800 text-white text-xs font-semibold rounded-lg">Back to Fleet Table</button>
      </div>
    `;
    document.getElementById("btn-err-back")?.addEventListener("click", () => stateStore.setView("fleet"));
  }
}

function renderRoomDetailContent(container, room, inventory, activity) {
  const state = stateStore.getState();
  const rooms = state.rooms || [];
  
  const isDowngraded = room.status === "SOFT_DOWNGRADED";
  const isSuspended = room.status === "SUSPENDED";
  const statusBadgeClass = isSuspended ? 'status-badge-suspended' : (isDowngraded ? 'status-badge-downgraded' : 'status-badge-active');
  const metadata = ROOM_ASSET_METADATA[room.room_id] || { tables: [], inbound_files: [], export_files: [], notebooks: [] };

  const recentQueries = activity?.recent_queries || [];
  const recentAudits = activity?.recent_audit_events || [];
  const lastActiveTimestamp = activity?.last_active_session || recentAudits[0]?.timestamp || room.last_activity_at;
  
  // Find researcher associated with last activity
  const researcherName = activity?.active_researcher_name || 
                         (activity?.active_researcher_email ? activity.active_researcher_email.split('@')[0] : null) ||
                         ((room.researchers && room.researchers[0]) ? `Dr. ${room.researchers[0].first_name || ''} ${room.researchers[0].last_name || ''}`.trim() : (room.lead_researcher || 'Researcher'));

  const researcherQueriesCount = activity?.researcher_queries_count !== undefined && activity?.researcher_queries_count !== null 
    ? activity.researcher_queries_count 
    : (activity?.total_queries_count ?? recentQueries.length ?? 0);
  
  const totalNotebookRuns = activity?.total_notebook_runs !== undefined && activity?.total_notebook_runs !== null
    ? activity.total_notebook_runs
    : metadata.notebooks.reduce((acc, nb) => acc + (nb.runs || 0), 0);
    
  const totalNotebookHours = activity?.total_notebook_hours || 0.0;
  const totalStorageVolume = (inventory?.inbound_bytes || 0) + (inventory?.export_bytes || 0);
  const roomCost = room.total_cost || 0;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Breadcrumbs & Quick Room Switcher -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div class="flex items-center gap-2 text-xs font-medium text-slate-500">
          <button id="btn-back-fleet" class="hover:text-blue-600 flex items-center gap-1.5 transition">
            <i class="fa-solid fa-arrow-left text-xs"></i><span>Fleet Rooms Table</span>
          </button>
          <span>/</span>
          <span class="text-slate-800 font-semibold font-mono">${room.room_id}</span>
        </div>

        <!-- Quick Room Switcher Dropdown -->
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-slate-500">Quick Switch Room:</span>
          <select id="quick-room-switcher" class="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
            ${rooms.map(r => `
              <option value="${r.room_id}" ${r.room_id === room.room_id ? 'selected' : ''}>
                ${r.room_id} — ${r.room_name}
              </option>
            `).join('')}
          </select>
        </div>
      </div>

      <!-- 1. Room Header Banner -->
      <div class="bg-slate-900 text-white rounded-2xl p-6 shadow-md border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div class="flex items-center gap-2">
            <span class="font-mono text-xs px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">${room.room_id}</span>
            <span class="status-badge ${statusBadgeClass}">
              <span class="w-1.5 h-1.5 rounded-full ${isSuspended ? 'bg-rose-500' : (isDowngraded ? 'bg-amber-500' : 'bg-emerald-500')}"></span>
              ${room.status}
            </span>
          </div>
          <h1 class="text-2xl font-extrabold mt-2 tracking-tight">${room.room_name}</h1>
          <div class="flex flex-wrap items-center gap-4 text-xs text-slate-400 mt-2">
            <span><i class="fa-solid fa-building-columns text-slate-500 mr-1.5"></i>${room.institute_name || room.institute_id}</span>
            <span>•</span>
            <span class="font-mono"><i class="fa-solid fa-layer-group text-slate-500 mr-1.5"></i>${room.spoke_project_id}</span>
            ${room.deployment_date ? `<span>•</span><span class="font-mono"><i class="fa-solid fa-calendar-day text-slate-500 mr-1.5"></i>Deployed: ${room.deployment_date}</span>` : ''}
          </div>
        </div>

        <div class="flex items-center gap-3">
          ${isDowngraded ? `
            <button id="btn-toggle-iam" class="px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm flex items-center gap-2 transition" data-target="ACTIVE">
              <i class="fa-solid fa-lock-open text-xs"></i><span>Reactivate Access</span>
            </button>
          ` : `
            <button id="btn-toggle-iam" class="px-4 py-2 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white shadow-sm flex items-center gap-2 transition" data-target="SOFT_DOWNGRADED">
              <i class="fa-solid fa-lock text-xs"></i><span>Soft Downgrade</span>
            </button>
          `}
        </div>
      </div>

      <!-- 2. Room Top Activity & FinOps Metrics Bar -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        
        <!-- Metric 1: Last Activity -->
        <div class="flex items-center gap-3 border-b sm:border-b-0 sm:border-r border-slate-100 pb-3 sm:pb-0 sm:pr-3">
          <div class="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-clock-rotate-left"></i>
          </div>
          <div class="overflow-hidden">
            <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Last Activity</div>
            <div class="text-xs font-bold text-slate-900 truncate">${formatDateTime(lastActiveTimestamp)}</div>
            <div class="text-[10px] text-slate-500 truncate font-medium">${researcherName}</div>
          </div>
        </div>

        <!-- Metric 2: Room Specific Queries Run -->
        <div class="flex items-center gap-3 border-b sm:border-b-0 sm:border-r border-slate-100 pb-3 sm:pb-0 sm:pr-3">
          <div class="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-terminal"></i>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Researcher Queries</div>
            <div class="text-sm font-extrabold text-slate-900 font-mono">${researcherQueriesCount} queries</div>
            <div class="text-[10px] text-slate-400">By authorized researchers</div>
          </div>
        </div>

        <!-- Metric 3: Notebook Invocations -->
        <div class="flex items-center gap-3 border-b sm:border-b-0 sm:border-r border-slate-100 pb-3 sm:pb-0 sm:pr-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-book-journal-whills"></i>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Notebook Sessions</div>
            <div class="text-sm font-extrabold text-slate-900 font-mono">${totalNotebookRuns} sessions</div>
            <div class="text-[10px] text-slate-400">${Number(totalNotebookHours || 0).toFixed(2)}h Colab runtime</div>
          </div>
        </div>

        <!-- Metric 4: Total Storage Volume -->
        <div class="flex items-center gap-3 border-b sm:border-b-0 sm:border-r border-slate-100 pb-3 sm:pb-0 sm:pr-3">
          <div class="w-10 h-10 rounded-lg bg-cyan-50 text-cyan-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-hard-drive"></i>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Storage Volume</div>
            <div class="text-sm font-extrabold text-slate-900 font-mono">${formatBytes(totalStorageVolume)}</div>
            <div class="text-[10px] text-slate-400">Inbound & Air-lock</div>
          </div>
        </div>

        <!-- Metric 5: Room Cost (Inception-to-Date) -->
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-coins"></i>
          </div>
          <div>
            <div class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Total Room Cost</div>
            <div class="text-sm font-extrabold text-slate-900 font-mono">${formatUSD(roomCost)}</div>
            <div class="text-[10px] text-slate-400">Creation to date</div>
          </div>
        </div>

      </div>

      <!-- 3. Vertically Stacked Full-Width Cards -->
      <div class="space-y-6">
        ${renderResearchersRosterCard(room, activity)}
        ${renderAuditEventStreamCard(activity)}
      </div>

      <!-- 4. 2-Column Grid for Datasets, Storage, Notebooks & Air-Lock -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        <!-- Left Column -->
        <div class="space-y-6">
          ${renderBigQueryCard(room, metadata)}
          ${renderStorageCard(metadata, inventory)}
        </div>

        <!-- Right Column -->
        <div class="space-y-6">
          ${renderNotebooksCard(room, metadata)}
          ${renderExportQuarantineCard(room, metadata)}
        </div>

      </div>

    </div>
  `;

  // Attach Back button
  document.getElementById("btn-back-fleet")?.addEventListener("click", () => stateStore.setView("fleet"));

  // Attach Quick Switcher dropdown
  const switcher = document.getElementById("quick-room-switcher");
  switcher?.addEventListener("change", (e) => {
    stateStore.setView("room-detail", e.target.value);
  });

  // Attach IAM Toggle button
  const toggleBtn = document.getElementById("btn-toggle-iam");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", async () => {
      const targetStatus = toggleBtn.getAttribute("data-target");
      const actionText = targetStatus === "SOFT_DOWNGRADED" ? "soft-downgrade" : "reactivate";

      if (confirm(`Are you sure you want to ${actionText} room ${room.room_id}?`)) {
        try {
          const res = await api.updateRoomStatus(room.room_id, targetStatus, `Administrator action: ${actionText}`);
          stateStore.showToast(res.message || `Room ${room.room_id} updated to ${targetStatus}`, "success");
          renderRoomDetailView(room.room_id);
          const updatedRooms = await api.getRooms();
          stateStore.updateData({ rooms: updatedRooms });
        } catch (e) {
          stateStore.showToast(`Status change failed: ${e.message}`, "error");
        }
      }
    });
  }
}
