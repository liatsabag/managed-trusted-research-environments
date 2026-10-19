/**
 * Dedicated Fleet Audit Logs Page Component
 * Real-time unified audit feed, security telemetry, live backend filtering by room, researcher, category, and limit.
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatDateTime } from '../config.js';

let currentAuditLimit = 500;
let currentRoomFilter = 'ALL';
let currentResearcherFilter = 'ALL';
let currentCategoryFilter = 'ALL';
let researchersRoster = [];

export async function renderAuditView() {
  const container = document.getElementById("view-audit-logs");
  if (!container) return;

  container.innerHTML = `
    <div class="space-y-6 animate-pulse">
      <div class="h-8 bg-slate-200 rounded w-1/4"></div>
      <div class="h-16 bg-slate-200 rounded-xl"></div>
      <div class="h-96 bg-slate-200 rounded-xl"></div>
    </div>
  `;

  try {
    if (researchersRoster.length === 0) {
      researchersRoster = await api.getResearchers();
    }
  } catch (e) {
    console.warn("Could not preload researchers roster:", e);
  }

  await fetchAndRenderAudit(container);
}

async function fetchAndRenderAudit(container) {
  try {
    const roomId = currentRoomFilter !== 'ALL' ? currentRoomFilter : null;
    let principalEmail = currentResearcherFilter !== 'ALL' ? currentResearcherFilter : null;
    let researchersOnly = false;
    if (currentResearcherFilter === 'ALL_RESEARCHERS') {
      principalEmail = null;
      researchersOnly = true;
    }
    const category = currentCategoryFilter !== 'ALL' ? currentCategoryFilter : null;

    const events = await api.getAuditFeed(roomId, principalEmail, currentAuditLimit, category, researchersOnly);
    renderAuditContent(container, events);
  } catch (err) {
    container.innerHTML = `
      <div class="p-8 bg-white rounded-xl border border-rose-200 text-center">
        <h3 class="text-base font-bold text-slate-800">Failed to Load Audit Logs</h3>
        <p class="text-xs text-slate-500 mt-1">${err.message}</p>
        <button id="btn-retry-audit" class="mt-4 px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg cursor-pointer">Retry</button>
      </div>
    `;
    document.getElementById("btn-retry-audit")?.addEventListener("click", () => renderAuditView());
  }
}

function renderAuditContent(container, events) {
  const state = stateStore.getState();
  const rooms = state.rooms || [];
  
  // Build clean researcher options from roster and rooms
  const researcherOptions = [];
  const addedEmails = new Set();
  const pool = researchersRoster.length > 0 ? researchersRoster : rooms.flatMap(r => (r.researchers || []).map(res => ({ ...res, room_id: r.room_id })));

  pool.forEach(r => {
    const email = (r.email || r.primary_email || '').toLowerCase().trim();
    if (email && !addedEmails.has(email) && (currentRoomFilter === 'ALL' || r.room_id === currentRoomFilter)) {
      const name = r.name || r.researcher_name || `${r.first_name || ''} ${r.last_name || ''}`.trim() || email;
      researcherOptions.push({ email, label: `${name} (${email})` });
      addedEmails.add(email);
    }
  });

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Title & Description + Refresh & Limit Controls -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 class="text-xl font-extrabold text-slate-900 tracking-tight">Security & Activity Audit Trail</h1>
          <p class="text-xs text-slate-500 mt-0.5">Live curated Cloud Audit Logs from <span class="font-mono text-slate-700 font-bold">ops_audit_events_curated</span> capturing queries, storage egress, IAM mutations, and compute runtimes.</p>
        </div>

        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1.5 text-xs text-slate-600 font-semibold bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm">
            <span>Row Limit:</span>
            <select id="audit-limit-select" class="font-mono font-bold text-slate-800 bg-transparent focus:outline-none cursor-pointer">
              <option value="50" ${currentAuditLimit === 50 ? 'selected' : ''}>50</option>
              <option value="100" ${currentAuditLimit === 100 ? 'selected' : ''}>100</option>
              <option value="200" ${currentAuditLimit === 200 ? 'selected' : ''}>200</option>
              <option value="500" ${currentAuditLimit === 500 ? 'selected' : ''}>500</option>
              <option value="1000" ${currentAuditLimit === 1000 ? 'selected' : ''}>1,000</option>
              <option value="2000" ${currentAuditLimit === 2000 ? 'selected' : ''}>2,000 (Max)</option>
            </select>
          </div>

          <span class="px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono font-bold shadow-sm">
            ${events.length} Events Loaded
          </span>

          <button id="btn-refresh-audit" class="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow flex items-center gap-1.5 transition cursor-pointer">
            <i class="fa-solid fa-arrows-rotate text-xs"></i>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <!-- Filters & Search Toolbar -->
      <div class="bg-white rounded-xl border border-slate-200 p-3 shadow-sm flex flex-col lg:flex-row items-center justify-between gap-2.5">
        <div class="relative w-full lg:w-72">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-2.5 text-slate-400 text-xs"></i>
          <input 
            type="text" 
            id="audit-search-input" 
            placeholder="Search principal, action, resource, or desc..." 
            class="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition"
          >
        </div>

        <div class="flex flex-wrap items-center gap-2 w-full lg:w-auto justify-end">
          <div class="flex items-center gap-1.5">
            <span class="text-xs font-semibold text-slate-500">Room:</span>
            <select id="audit-room-filter" class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
              <option value="ALL" ${currentRoomFilter === 'ALL' ? 'selected' : ''}>All Rooms</option>
              <option value="hub-core" ${currentRoomFilter === 'hub-core' ? 'selected' : ''}>hub-core</option>
              ${rooms.map(r => `<option value="${r.room_id}" ${currentRoomFilter === r.room_id ? 'selected' : ''}>${r.room_id}</option>`).join('')}
            </select>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-xs font-semibold text-slate-500">Researcher:</span>
            <select id="audit-researcher-filter" class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer max-w-[280px] truncate">
              <option value="ALL" ${currentResearcherFilter === 'ALL' ? 'selected' : ''}>All Users & Systems</option>
              <option value="ALL_RESEARCHERS" ${currentResearcherFilter === 'ALL_RESEARCHERS' ? 'selected' : ''} class="font-bold text-indigo-700">★ All Researchers (Excl. Admin/System)</option>
              <optgroup label="Authorized Researchers">
                ${researcherOptions.map(opt => `<option value="${opt.email}" ${currentResearcherFilter === opt.email ? 'selected' : ''}>${opt.label}</option>`).join('')}
              </optgroup>
            </select>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-xs font-semibold text-slate-500">Category:</span>
            <select id="audit-category-filter" class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
              <option value="ALL" ${currentCategoryFilter === 'ALL' ? 'selected' : ''}>All Categories</option>
              <option value="DATA_ACCESS" ${currentCategoryFilter === 'DATA_ACCESS' ? 'selected' : ''}>Data Access (BQ)</option>
              <option value="COMPUTE_SESSION" ${currentCategoryFilter === 'COMPUTE_SESSION' ? 'selected' : ''}>Compute Sessions</option>
              <option value="STORAGE_EGRESS" ${currentCategoryFilter === 'STORAGE_EGRESS' ? 'selected' : ''}>Storage & Egress</option>
              <option value="IAM_SECURITY" ${currentCategoryFilter === 'IAM_SECURITY' ? 'selected' : ''}>IAM & Security</option>
              <option value="AI_INFERENCE" ${currentCategoryFilter === 'AI_INFERENCE' ? 'selected' : ''}>AI & Inference</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Audit Logs Table -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full table-fixed text-left border-collapse">
            <colgroup>
              <col class="w-7">
              <col class="w-[130px]">
              <col class="w-[110px]">
              <col class="w-[160px]">
              <col class="w-[105px]">
              <col class="w-[135px]">
              <col class="w-[135px]">
              <col class="w-[75px]">
              <col class="w-auto">
            </colgroup>
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold text-[10px] uppercase tracking-wider">
              <tr>
                <th class="py-2 px-1.5 text-center"></th>
                <th class="py-2 px-2">Timestamp (UTC)</th>
                <th class="py-2 px-2">Research Room</th>
                <th class="py-2 px-2">Principal Identity</th>
                <th class="py-2 px-1 text-center">Category</th>
                <th class="py-2 px-2">Service / Method</th>
                <th class="py-2 px-2">Target Resource</th>
                <th class="py-2 px-1 text-center">Status</th>
                <th class="py-2 px-2">Description</th>
              </tr>
            </thead>
            <tbody id="audit-table-body" class="divide-y divide-slate-200 text-xs text-slate-700">
            </tbody>
          </table>
        </div>
      </div>

    </div>
  `;

  const searchInput = document.getElementById("audit-search-input");
  const roomFilter = document.getElementById("audit-room-filter");
  const researcherFilter = document.getElementById("audit-researcher-filter");
  const categoryFilter = document.getElementById("audit-category-filter");
  const limitSelect = document.getElementById("audit-limit-select");

  function filterAndRenderTable() {
    const query = (searchInput?.value || '').toLowerCase().trim();

    const filtered = events.filter(e => {
      const email = (e.principal_email || '').toLowerCase();
      const action = (e.method_name || e.service_name || '').toLowerCase();
      const resource = (e.resource_name || '').toLowerCase();
      const desc = (e.description || '').toLowerCase();

      return !query || email.includes(query) || action.includes(query) || resource.includes(query) || desc.includes(query);
    });

    const tbody = document.getElementById("audit-table-body");
    if (!tbody) return;

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" class="py-10 text-center text-slate-400">
            <i class="fa-solid fa-list-check text-lg mb-1.5 text-slate-300 block"></i>
            No audit events found matching the filter criteria.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtered.map((e, idx) => {
      const cat = (e.category || 'DATA_ACCESS').toUpperCase();
      let catBadge = 'bg-slate-100 text-slate-700';
      if (cat.includes('DATA')) catBadge = 'bg-purple-50 text-purple-700 border border-purple-200';
      else if (cat.includes('COMPUTE')) catBadge = 'bg-blue-50 text-blue-700 border border-blue-200';
      else if (cat.includes('STORAGE') || cat.includes('EGRESS')) catBadge = 'bg-cyan-50 text-cyan-700 border border-cyan-200';
      else if (cat.includes('IAM') || cat.includes('SECURITY')) catBadge = 'bg-rose-50 text-rose-700 border border-rose-200';
      else if (cat.includes('AI')) catBadge = 'bg-emerald-50 text-emerald-700 border border-emerald-200';

      const isSuccess = (e.status || 'SUCCESS').toUpperCase() === 'SUCCESS';
      const statusClass = isSuccess ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200';
      const rowId = `audit-row-${idx}`;
      const drawerId = `audit-drawer-${idx}`;
      const chevronId = `audit-chevron-${idx}`;
      const fullDesc = e.description || e.method_name || 'Routine cloud audit operation';

      return `
        <tr class="hover:bg-blue-50/40 transition cursor-pointer audit-master-row" data-drawer="${drawerId}" data-chevron="${chevronId}">
          <td class="py-1.5 px-1.5 text-center text-slate-400">
            <i class="fa-solid fa-chevron-right text-[9px] transition-transform duration-200" id="${chevronId}"></i>
          </td>
          <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px] text-slate-500 truncate" title="${e.timestamp}">${formatDateTime(e.timestamp)}</td>
          <td class="py-1.5 px-2 whitespace-nowrap truncate">
            <button class="btn-audit-room-jump px-1.5 py-0.5 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 font-mono text-[10px] font-bold border border-blue-200 transition cursor-pointer" data-room-id="${e.room_id}">
              ${e.room_id}
            </button>
          </td>
          <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px] text-slate-900 font-semibold truncate" title="${e.principal_email}">
            ${e.principal_email}
          </td>
          <td class="py-1.5 px-1 text-center whitespace-nowrap">
            <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${catBadge}">${cat}</span>
          </td>
          <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px] text-slate-700 truncate" title="${e.service_name} / ${e.method_name || ''}">
            <span class="text-indigo-600 font-semibold">${e.service_name}</span>
            <div class="text-[10px] text-slate-400 truncate">${e.method_name || 'execute'}</div>
          </td>
          <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[11px] text-slate-600 truncate" title="${e.resource_name || '—'}">
            ${e.resource_name || '—'}
          </td>
          <td class="py-1.5 px-1 text-center whitespace-nowrap">
            <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${statusClass}">${e.status || 'SUCCESS'}</span>
          </td>
          <td class="py-1.5 px-2 text-slate-700 font-medium text-[11px] truncate" title="${fullDesc}">
            ${fullDesc}
          </td>
        </tr>
        <tr id="${drawerId}" class="hidden bg-slate-50/90 border-b border-slate-200">
          <td colspan="9" class="p-2.5">
            <div class="bg-white rounded-lg border border-slate-200 p-3 shadow-sm space-y-2">
              <div class="flex items-center justify-between pb-1.5 border-b border-slate-100">
                <div class="flex items-center gap-2">
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${catBadge}">${cat}</span>
                  <span class="font-bold text-slate-800 text-xs">Event Detail #${e.event_id || idx + 1}</span>
                </div>
                <span class="font-mono text-[10px] text-slate-500">${formatDateTime(e.timestamp)}</span>
              </div>
              
              <div>
                <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Full Description</span>
                <p class="text-xs text-slate-800 font-medium mt-0.5 leading-relaxed bg-slate-50 p-2 rounded border border-slate-200">
                  ${fullDesc}
                </p>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 text-xs pt-0.5">
                <div>
                  <span class="text-[10px] font-bold uppercase text-slate-400 block">Principal</span>
                  <span class="font-mono text-slate-900 font-semibold break-all text-[11px]">${e.principal_email}</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-slate-400 block">Room</span>
                  <span class="font-mono text-blue-700 font-bold text-[11px]">${e.room_id}</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-slate-400 block">Service & Method</span>
                  <span class="font-mono text-slate-700 font-medium text-[11px]">${e.service_name} • ${e.method_name || 'execute'}</span>
                </div>
                <div>
                  <span class="text-[10px] font-bold uppercase text-slate-400 block">Target Resource</span>
                  <span class="font-mono text-slate-600 break-all text-[11px]">${e.resource_name || '—'}</span>
                </div>
              </div>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll(".audit-master-row").forEach(row => {
      row.addEventListener("click", (e) => {
        if (e.target.closest(".btn-audit-room-jump")) return;
        const drawerId = row.getAttribute("data-drawer");
        const chevronId = row.getAttribute("data-chevron");
        const drawer = document.getElementById(drawerId);
        const chevron = document.getElementById(chevronId);
        if (!drawer) return;
        const isHidden = drawer.classList.contains("hidden");
        drawer.classList.toggle("hidden");
        chevron?.classList.toggle("rotate-90", isHidden);
      });
    });

    tbody.querySelectorAll(".btn-audit-room-jump").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const roomId = btn.getAttribute("data-room-id");
        stateStore.setView("room-detail", roomId);
      });
    });
  }

  roomFilter?.addEventListener("change", (e) => {
    currentRoomFilter = e.target.value;
    renderAuditView();
  });

  researcherFilter?.addEventListener("change", (e) => {
    currentResearcherFilter = e.target.value;
    renderAuditView();
  });

  categoryFilter?.addEventListener("change", (e) => {
    currentCategoryFilter = e.target.value;
    renderAuditView();
  });

  limitSelect?.addEventListener("change", (e) => {
    currentAuditLimit = parseInt(e.target.value, 10) || 500;
    renderAuditView();
  });

  searchInput?.addEventListener("input", filterAndRenderTable);
  document.getElementById("btn-refresh-audit")?.addEventListener("click", () => renderAuditView());

  filterAndRenderTable();
}

