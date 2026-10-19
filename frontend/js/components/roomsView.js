/**
 * Page 1: Main Fleet Rooms Table Page Component
 * Renders 10 exact columns with persistent search inputs and table-only DOM row updates
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatUSD, formatDateTime, formatDate } from '../config.js';

export function renderRoomsView() {
  const container = document.getElementById("view-fleet");
  if (!container) return;

  const state = stateStore.getState();
  const rooms = state.rooms || [];
  const searchQuery = state.searchQuery || '';
  const statusFilter = state.statusFilter || 'ALL';

  // If container is already populated with the shell, just update the table rows
  if (container.querySelector("#rooms-table-body")) {
    updateTableRows(rooms, searchQuery, statusFilter);
    updateMetricPills(rooms);
    return;
  }

  // Initial Full Shell Render
  const totalCount = rooms.length;
  const activeCount = rooms.filter(r => r.status === 'ACTIVE').length;
  const downgradedCount = rooms.filter(r => r.status === 'SOFT_DOWNGRADED').length;
  const suspendedCount = rooms.filter(r => r.status === 'SUSPENDED').length;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Header & Metric Counters + Request Room Button -->
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 class="text-xl font-extrabold text-slate-900 tracking-tight">Research Rooms Fleet</h1>
          <p class="text-xs text-slate-500 mt-0.5">Enterprise tenant management, security posture, and DUA lifecycle monitoring.</p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <div id="metric-pills-container" class="flex items-center gap-2 text-xs font-semibold">
            <span class="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 border border-slate-200">
              Total: <span id="cnt-total" class="font-mono font-bold">${totalCount}</span>
            </span>
            <span class="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200">
              Active: <span id="cnt-active" class="font-mono font-bold">${activeCount}</span>
            </span>
            <span class="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200">
              Downgraded: <span id="cnt-downgraded" class="font-mono font-bold">${downgradedCount}</span>
            </span>
            <span class="px-2.5 py-1 rounded-lg bg-rose-50 text-rose-800 border border-rose-200">
              Suspended: <span id="cnt-suspended" class="font-mono font-bold">${suspendedCount}</span>
            </span>
          </div>

          <button id="btn-open-room-request" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-md flex items-center gap-2 transition">
            <i class="fa-solid fa-plus text-xs"></i>
            <span>Request Research Room</span>
          </button>
        </div>
      </div>

      <!-- Search & Filters Toolbar -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        
        <!-- Search Input -->
        <div class="relative w-full sm:w-96">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-slate-400 text-xs"></i>
          <input 
            type="text" 
            id="fleet-search-input" 
            placeholder="Search by Room ID, Name, PI, or Spoke Project..." 
            value="${searchQuery}"
            class="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
          >
        </div>

        <!-- Status Filter Dropdown -->
        <div class="flex items-center gap-3 w-full sm:w-auto justify-end">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold text-slate-500">Status:</span>
            <select id="fleet-status-filter" class="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-semibold text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
              <option value="ALL" ${statusFilter === 'ALL' ? 'selected' : ''}>All Operational States</option>
              <option value="ACTIVE" ${statusFilter === 'ACTIVE' ? 'selected' : ''}>Active Rooms</option>
              <option value="SOFT_DOWNGRADED" ${statusFilter === 'SOFT_DOWNGRADED' ? 'selected' : ''}>Soft Downgraded</option>
              <option value="SUSPENDED" ${statusFilter === 'SUSPENDED' ? 'selected' : ''}>Suspended</option>
            </select>
          </div>
        </div>

      </div>

      <!-- 10-Column Fleet Data Table -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse min-w-[950px]">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold text-[11px] uppercase tracking-wider">
              <tr>
                <th class="py-3 px-3">Room ID</th>
                <th class="py-3 px-3">Research Name</th>
                <th class="py-3 px-3">Lead Researcher</th>
                <th class="py-3 px-2 text-center">Researchers</th>
                <th class="py-3 px-3">Status</th>
                <th class="py-3 px-3">Deployment</th>
                <th class="py-3 px-3">DUA Expiration</th>
                <th class="py-3 px-3 text-right">Spend / Budget</th>
                <th class="py-3 px-3">Last Activity</th>
                <th class="py-3 px-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody id="rooms-table-body" class="divide-y divide-slate-200 text-xs text-slate-700">
            </tbody>
          </table>
        </div>
      </div>

    </div>
  `;

  // Attach event listeners once
  const searchInput = document.getElementById("fleet-search-input");
  searchInput?.addEventListener("input", (e) => {
    stateStore.setFilters(e.target.value, stateStore.getState().statusFilter);
  });

  const statusSelect = document.getElementById("fleet-status-filter");
  statusSelect?.addEventListener("change", (e) => {
    stateStore.setFilters(stateStore.getState().searchQuery, e.target.value);
  });

  document.getElementById("btn-open-room-request")?.addEventListener("click", () => {
    if (window.openRoomRequestModal) window.openRoomRequestModal();
  });

  // Render rows
  updateTableRows(rooms, searchQuery, statusFilter);
}

function updateMetricPills(rooms) {
  const totalEl = document.getElementById("cnt-total");
  const activeEl = document.getElementById("cnt-active");
  const downEl = document.getElementById("cnt-downgraded");
  const suspEl = document.getElementById("cnt-suspended");
  if (totalEl) totalEl.innerText = rooms.length;
  if (activeEl) activeEl.innerText = rooms.filter(r => r.status === 'ACTIVE').length;
  if (downEl) downEl.innerText = rooms.filter(r => r.status === 'SOFT_DOWNGRADED').length;
  if (suspEl) suspEl.innerText = rooms.filter(r => r.status === 'SUSPENDED').length;
}

function updateTableRows(rooms, searchQuery, statusFilter) {
  const tbody = document.getElementById("rooms-table-body");
  if (!tbody) return;

  const query = (searchQuery || '').toLowerCase().trim();
  const filteredRooms = rooms.filter(room => {
    const leadName = (room.lead_researcher || '').toLowerCase();
    const matchQuery = !query || 
      room.room_id?.toLowerCase().includes(query) ||
      room.room_name?.toLowerCase().includes(query) ||
      room.institute_name?.toLowerCase().includes(query) ||
      room.spoke_project_id?.toLowerCase().includes(query) ||
      leadName.includes(query);
    const matchStatus = statusFilter === 'ALL' || room.status === statusFilter;
    return matchQuery && matchStatus;
  });

  if (filteredRooms.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" class="py-12 text-center text-slate-400">
          <i class="fa-solid fa-magnifying-glass text-xl mb-2 text-slate-300 block"></i>
          No research rooms found matching the selected filters.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filteredRooms.map(room => {
    const isDowngraded = room.status === 'SOFT_DOWNGRADED';
    const isSuspended = room.status === 'SUSPENDED';
    const statusBadgeClass = isSuspended ? 'status-badge-suspended' : (isDowngraded ? 'status-badge-downgraded' : 'status-badge-active');
    
    const leadName = room.lead_researcher ? `Dr. ${room.lead_researcher.replace(/^Dr\.?\s*/i, '')}` : 'Dr. Researcher';
    const resCount = room.researcher_count || (room.researchers?.length || 0);
    const totalSpend = room.total_cost || 0;
    const deploymentDate = room.deployment_date ? formatDate(room.deployment_date) : 'Sep 24, 2026';
    
    // DUA expiration pill
    const duaRemaining = room.compliance?.dua_days_remaining ?? 0;
    const duaExpiryDate = room.compliance?.dua_expiry_date ? formatDate(room.compliance.dua_expiry_date) : '—';
    const duaPillClass = duaRemaining < 30 ? 'countdown-urgent' : (duaRemaining < 90 ? 'countdown-warning' : 'countdown-safe');

    // Real per-room activity timestamp
    const lastActivity = room.last_activity_at ? formatDateTime(room.last_activity_at) : 'Active Today';

    return `
      <tr class="hover:bg-blue-50/40 transition group">
        <!-- 1. Room ID -->
        <td class="py-3 px-3 font-mono font-bold text-slate-900 whitespace-nowrap">
          <span class="text-blue-600">${room.room_id}</span>
          <div class="text-[10px] text-slate-400 font-mono truncate max-w-[130px]" title="${room.spoke_project_id}">${room.spoke_project_id}</div>
        </td>

        <!-- 2. Research Name -->
        <td class="py-3 px-3">
          <div class="font-bold text-slate-900 group-hover:text-blue-600 transition line-clamp-1" title="${room.room_name}">${room.room_name}</div>
          <div class="text-[11px] text-slate-500 truncate max-w-[180px]">${room.institute_name || room.institute_id}</div>
        </td>

        <!-- 3. Lead Researcher -->
        <td class="py-3 px-3 whitespace-nowrap">
          <div class="font-semibold text-slate-800 flex items-center gap-1.5">
            <i class="fa-solid fa-user-doctor text-indigo-500 text-xs"></i>
            <span>${leadName}</span>
          </div>
        </td>

        <!-- 4. Researchers Counter -->
        <td class="py-3 px-2 text-center whitespace-nowrap">
          <span class="inline-flex items-center gap-1 font-semibold text-slate-800 bg-slate-100 px-2 py-0.5 rounded-full">
            <i class="fa-solid fa-users text-slate-400 text-[10px]"></i>
            <span>${resCount}</span>
          </span>
        </td>

        <!-- 5. Status -->
        <td class="py-3 px-3 whitespace-nowrap">
          <span class="status-badge ${statusBadgeClass}">
            <span class="w-1.5 h-1.5 rounded-full ${isSuspended ? 'bg-rose-500' : (isDowngraded ? 'bg-amber-500' : 'bg-emerald-500')}"></span>
            ${room.status}
          </span>
        </td>

        <!-- 6. Deployment Date -->
        <td class="py-3 px-3 whitespace-nowrap font-mono text-[11px] text-slate-600">
          ${deploymentDate}
        </td>

        <!-- 7. DUA Expiration -->
        <td class="py-3 px-3 whitespace-nowrap">
          <div class="text-slate-800 font-medium">${duaExpiryDate}</div>
          <div class="mt-0.5"><span class="countdown-pill ${duaPillClass}">${duaRemaining}d remaining</span></div>
        </td>

        <!-- 8. Spend / Budget -->
        <td class="py-3 px-3 text-right whitespace-nowrap">
          <div class="font-mono font-bold text-slate-900">${formatUSD(totalSpend)}</div>
          <div class="text-[10px] font-mono text-slate-500">of ${formatUSD(room.budget_limit_usd || 5000.0)}</div>
          <div class="w-20 ml-auto bg-slate-200 h-1.5 rounded-full mt-1 overflow-hidden" title="${((totalSpend / (room.budget_limit_usd || 5000.0)) * 100).toFixed(1)}% of budget spent">
            <div class="h-full ${(totalSpend / (room.budget_limit_usd || 5000.0)) * 100 > 90 ? 'bg-rose-500' : (totalSpend / (room.budget_limit_usd || 5000.0)) * 100 > 75 ? 'bg-amber-500' : 'bg-blue-600'}" style="width: ${Math.min(100, Math.max(2, (totalSpend / (room.budget_limit_usd || 5000.0)) * 100))}%"></div>
          </div>
        </td>

        <!-- 9. Last Activity -->
        <td class="py-3 px-3 whitespace-nowrap text-[11px] font-mono text-slate-500">
          ${lastActivity}
        </td>

        <!-- 10. Action Buttons -->
        <td class="py-3 px-3 text-center whitespace-nowrap">
          <div class="flex items-center justify-center gap-1.5">
            <button class="btn-action-view px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-blue-600 text-white transition flex items-center gap-1" data-room-id="${room.room_id}" title="View Details">
              <span>View</span>
              <i class="fa-solid fa-arrow-right text-[10px]"></i>
            </button>
            <button class="btn-action-downgrade px-2 py-1.5 rounded-lg text-xs font-semibold ${isDowngraded ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-amber-50 text-amber-700 hover:bg-amber-100'} border transition" data-room-id="${room.room_id}" data-action="${isDowngraded ? 'reactivate' : 'downgrade'}" title="${isDowngraded ? 'Reactivate Room' : 'Downgrade Room'}">
              <i class="fa-solid ${isDowngraded ? 'fa-unlock' : 'fa-lock'} text-[10px]"></i>
            </button>
            <button class="btn-action-suspend px-2 py-1.5 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition" data-room-id="${room.room_id}" title="Suspend Room">
              <i class="fa-solid fa-ban text-[10px]"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Attach button click events
  tbody.querySelectorAll(".btn-action-view").forEach(btn => {
    btn.addEventListener("click", () => {
      const roomId = btn.getAttribute("data-room-id");
      stateStore.setView("room-detail", roomId);
    });
  });

  tbody.querySelectorAll(".btn-action-downgrade").forEach(btn => {
    btn.addEventListener("click", async () => {
      const roomId = btn.getAttribute("data-room-id");
      const action = btn.getAttribute("data-action");
      try {
        if (action === "reactivate") {
          await api.reactivateRoom(roomId);
          stateStore.showToast(`Reactivated room ${roomId}`, "success");
        } else {
          await api.downgradeRoom(roomId, "Administrator manual action");
          stateStore.showToast(`Downgraded room ${roomId} to read-only`, "warning");
        }
        const updatedRooms = await api.getRooms();
        stateStore.updateData({ rooms: updatedRooms });
      } catch (e) {
        stateStore.showToast(`Action failed: ${e.message}`, "error");
      }
    });
  });

  tbody.querySelectorAll(".btn-action-suspend").forEach(btn => {
    btn.addEventListener("click", async () => {
      const roomId = btn.getAttribute("data-room-id");
      try {
        await api.updateRoomStatus(roomId, "SUSPENDED", "Administrator manual suspension");
        stateStore.showToast(`Suspended room ${roomId}`, "warning");
        const updatedRooms = await api.getRooms();
        stateStore.updateData({ rooms: updatedRooms });
      } catch (e) {
        stateStore.showToast(`Suspension failed: ${e.message}`, "error");
      }
    });
  });
}
