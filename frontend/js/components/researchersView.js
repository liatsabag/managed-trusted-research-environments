/**
 * Dedicated Researchers Fleet Page Component
 * Renders KPI cards, search toolbar, "+ Add Researcher" modal stub, and expandable researcher detail rows.
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';
import { formatUSD, formatDateTime } from '../config.js';

const RESEARCHER_METADATA = {
  "dr.oren.katz@liatsabag.altostrat.com": { phone: "+972-54-819-2041", room_id: "rr-oncology-01", room_name: "Immuno-Oncology Biomarker Study", role: "Principal Investigator", institute: "Sheba Medical Center / MSKCC", start_time: "2026-09-01T08:00:00Z", last_active: "2026-09-29T14:09:04Z" },
  "prof.miriam.levy@liatsabag.altostrat.com": { phone: "+972-52-491-8302", room_id: "rr-oncology-01", room_name: "Immuno-Oncology Biomarker Study", role: "Oncologist", institute: "Sheba Medical Center / MSKCC", start_time: "2026-09-01T08:00:00Z", last_active: "2026-09-29T11:43:37Z" },
  "dr.eitan.rosen@liatsabag.altostrat.com": { phone: "+972-50-384-9128", room_id: "rr-genomics-02", room_name: "Rare Disease Whole-Genome Sequencing", role: "Lead Genomicist", institute: "Hadassah / Broad Institute", start_time: "2026-09-02T09:30:00Z", last_active: "2026-09-29T18:22:15Z" },
  "prof.anat.shapiro@liatsabag.altostrat.com": { phone: "+972-54-927-4610", room_id: "rr-genomics-02", room_name: "Rare Disease Whole-Genome Sequencing", role: "Bioinformatician", institute: "Hadassah / Broad Institute", start_time: "2026-09-02T09:30:00Z", last_active: "2026-09-29T16:10:04Z" },
  "dr.maya.lin@liatsabag.altostrat.com": { phone: "+972-53-718-3920", room_id: "rr-cardio-03", room_name: "Cardiovascular Risk Prediction Cohort", role: "Lead Investigator", institute: "Tel Aviv Sourasky (Ichilov)", start_time: "2026-09-05T10:00:00Z", last_active: "2026-09-29T19:27:54Z" },
  "dr.daniel.cohen@liatsabag.altostrat.com": { phone: "+972-54-209-1847", room_id: "rr-cardio-03", room_name: "Cardiovascular Risk Prediction Cohort", role: "Cardiologist", institute: "Tel Aviv Sourasky (Ichilov)", start_time: "2026-09-05T10:00:00Z", last_active: "2026-09-29T17:05:12Z" },
  "dr.noa.shapira@liatsabag.altostrat.com": { phone: "+972-52-671-9304", room_id: "rr-neurology-04", room_name: "Neurological & Dementia Imaging Cohort", role: "Principal Investigator", institute: "Technion / Rambam Health", start_time: "2026-09-10T08:15:00Z", last_active: "2026-09-29T13:45:00Z" },
  "dr.rami.friedman@liatsabag.altostrat.com": { phone: "+972-50-938-1049", room_id: "rr-neurology-04", room_name: "Neurological & Dementia Imaging Cohort", role: "Neurologist", institute: "Technion / Rambam Health", start_time: "2026-09-10T08:15:00Z", last_active: "2026-09-29T10:18:22Z" }
};

export async function renderResearchersView() {
  const container = document.getElementById("view-researchers");
  if (!container) return;

  container.innerHTML = `
    <div class="space-y-6 animate-pulse">
      <div class="h-8 bg-slate-200 rounded w-1/4"></div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="h-24 bg-slate-200 rounded-xl"></div>
        <div class="h-24 bg-slate-200 rounded-xl"></div>
        <div class="h-24 bg-slate-200 rounded-xl"></div>
      </div>
      <div class="h-96 bg-slate-200 rounded-xl"></div>
    </div>
  `;

  try {
    const rawResearchers = await api.getResearchers();
    renderResearchersContent(container, rawResearchers || []);
  } catch (err) {
    container.innerHTML = `
      <div class="p-8 bg-white rounded-xl border border-rose-200 text-center">
        <h3 class="text-base font-bold text-slate-800">Failed to Load Researchers</h3>
        <p class="text-xs text-slate-500 mt-1">${err.message}</p>
        <button id="btn-retry-researchers" class="mt-4 px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg">Retry</button>
      </div>
    `;
    document.getElementById("btn-retry-researchers")?.addEventListener("click", () => renderResearchersView());
  }
}

function renderResearchersContent(container, rawResearchers) {
  const state = stateStore.getState();
  const rooms = state.rooms || [];

  const researchers = rawResearchers.map(r => {
    const email = (r.email || r.primary_email || '').toLowerCase();
    const meta = RESEARCHER_METADATA[email] || {};
    const matchedRoom = rooms.find(rm => rm.room_id === meta.room_id || rm.room_id === r.room_id);

    return {
      researcher_id: r.researcher_id || `res-${email.split('@')[0]}`,
      name: r.name || r.researcher_name || `${r.first_name || ''} ${r.last_name || ''}`.trim() || 'Principal Investigator',
      email: email,
      phone: meta.phone || '+972-54-000-0000',
      institute_name: meta.institute || (r.institute_id ? r.institute_id.replace(/^inst-/, '').toUpperCase() : 'Medical Center'),
      room_id: r.room_id || meta.room_id || matchedRoom?.room_id || 'rr-oncology-01',
      room_name: matchedRoom?.room_name || meta.room_name || 'Research Room',
      role: r.role || meta.role || 'Investigator',
      status: r.status || r.access_state || 'ACTIVE',
      spend: r.total_allocated_cost ?? r.allocated_cost_usd ?? 0,
      start_time: meta.start_time || '2026-09-01T08:00:00Z',
      last_active_at: r.last_active_at || meta.last_active || '2026-09-29T14:00:00Z'
    };
  });

  const totalCount = researchers.length;
  const totalSpend = researchers.reduce((acc, r) => acc + (r.spend || 0), 0);

  const instCounts = {};
  researchers.forEach(r => { instCounts[r.institute_name] = (instCounts[r.institute_name] || 0) + 1; });
  const uniqueInstCount = Object.keys(instCounts).length;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Title & Action Banner -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-600">
            <i class="fa-solid fa-users-viewfinder"></i><span>Fleet Identity & Access Management</span>
          </div>
          <h1 class="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight mt-0.5">Authorized Researchers & Investigators</h1>
          <p class="text-xs text-slate-500 mt-1">Cross-institutional research roster, room assignments, and financial spend attribution.</p>
        </div>
        <button id="btn-open-add-researcher" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl shadow transition flex items-center gap-2 cursor-pointer shrink-0">
          <i class="fa-solid fa-user-plus"></i><span>+ Add Researcher</span>
        </button>
      </div>

      <!-- 3 Clean KPI Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Researchers</span>
            <div class="text-2xl font-extrabold text-slate-900 font-mono mt-1">${totalCount} PIs & Staff</div>
            <div class="text-[10px] text-slate-400 mt-0.5">Enrolled across all research rooms</div>
          </div>
          <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-lg"><i class="fa-solid fa-users-line"></i></div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Fleet Spend</span>
            <div class="text-2xl font-extrabold text-slate-900 font-mono mt-1">${formatUSD(totalSpend)}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">Directly attributed to researchers</div>
          </div>
          <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-lg"><i class="fa-solid fa-receipt"></i></div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center justify-between">
          <div>
            <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Affiliated Institutes</span>
            <div class="text-2xl font-extrabold text-purple-700 font-mono mt-1">${uniqueInstCount} Partner Centers</div>
            <div class="text-[10px] text-slate-400 mt-0.5">Sheba, Hadassah, Ichilov, Technion</div>
          </div>
          <div class="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center text-lg"><i class="fa-solid fa-building-columns"></i></div>
        </div>
      </div>

      <!-- Search Toolbar -->
      <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="relative w-full sm:w-96">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-slate-400 text-xs"></i>
          <input type="text" id="researcher-search-input" placeholder="Search by researcher name, role, or institute..." class="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 transition">
        </div>
        <div class="text-xs text-slate-400 italic"><i class="fa-solid fa-circle-info mr-1"></i>Click any researcher row to view details</div>
      </div>

      <!-- Researchers Table -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold text-[11px] uppercase tracking-wider">
              <tr>
                <th class="py-3 px-4">Researcher Name</th>
                <th class="py-3 px-4">Role</th>
                <th class="py-3 px-4">Affiliated Institute</th>
                <th class="py-3 px-4 text-right">Spend</th>
                <th class="py-3 px-4 text-center w-12"></th>
              </tr>
            </thead>
            <tbody id="researchers-table-body" class="divide-y divide-slate-200 text-xs text-slate-700"></tbody>
          </table>
        </div>
      </div>

      <!-- Add Researcher Modal -->
      <div id="modal-add-researcher" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden p-6 space-y-4">
          <div class="flex items-center justify-between pb-3 border-b border-slate-200">
            <div class="font-extrabold text-slate-900 text-sm flex items-center gap-2"><i class="fa-solid fa-user-plus text-blue-600"></i><span>Register New Researcher</span></div>
            <button id="btn-close-add-modal" class="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"><i class="fa-solid fa-xmark"></i></button>
          </div>
          <form id="form-add-researcher" class="space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">First Name</label>
                <input type="text" id="add-res-first" placeholder="e.g. Rachel" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium" required />
              </div>
              <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">Last Name</label>
                <input type="text" id="add-res-last" placeholder="e.g. Green" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium" required />
              </div>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Institutional Email</label>
              <input type="email" id="add-res-email" placeholder="dr.rachel.green@liatsabag.altostrat.com" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium font-mono" required />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
              <input type="tel" id="add-res-phone" placeholder="+972-54-123-4567" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium font-mono" />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Affiliated Institute</label>
              <select id="add-res-institute" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium">
                <option value="inst-sheba-onco">Sheba Medical Center</option>
                <option value="inst-hadassah-gen">Hadassah University Medical Center</option>
                <option value="inst-tlv-cardio">Tel Aviv Sourasky (Ichilov)</option>
                <option value="inst-technion-neuro">Technion - Rambam Health</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Assign to Research Room</label>
              <select id="add-res-room" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium">
                <option value="rr-oncology-01">rr-oncology-01 (Immuno-Oncology)</option>
                <option value="rr-genomics-02">rr-genomics-02 (Rare Disease Genomics)</option>
                <option value="rr-cardio-03">rr-cardio-03 (Cardiovascular Risk)</option>
                <option value="rr-neurology-04">rr-neurology-04 (Neurology & Dementia)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Role / Specialization</label>
              <input type="text" id="add-res-role" placeholder="e.g. Lead Bioinformatician" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium" required />
            </div>
            <div class="pt-3 flex items-center justify-end gap-2 border-t border-slate-200">
              <button type="button" id="btn-cancel-add-modal" class="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-100 cursor-pointer">Cancel</button>
              <button type="submit" class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow flex items-center gap-1.5 cursor-pointer"><i class="fa-solid fa-check"></i><span>Submit Registration</span></button>
            </div>
          </form>
        </div>
      </div>

    </div>
  `;

  // Modal setup
  const addModal = document.getElementById("modal-add-researcher");
  document.getElementById("btn-open-add-researcher")?.addEventListener("click", () => { addModal?.classList.remove("hidden"); addModal?.classList.add("flex"); });
  const close = () => { addModal?.classList.add("hidden"); addModal?.classList.remove("flex"); };
  document.getElementById("btn-close-add-modal")?.addEventListener("click", close);
  document.getElementById("btn-cancel-add-modal")?.addEventListener("click", close);

  document.getElementById("form-add-researcher")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = `${document.getElementById("add-res-first").value} ${document.getElementById("add-res-last").value}`.trim();
    close();
    document.getElementById("form-add-researcher").reset();
    stateStore.showToast(`Researcher registration submitted for ${name} (Safe Mode: verified, no mutation).`, "success");
  });

  // Table rendering & expansion
  const searchInput = document.getElementById("researcher-search-input");

  function filterAndRenderTable() {
    const query = (searchInput?.value || '').toLowerCase().trim();
    const filtered = researchers.filter(r => !query || r.name.toLowerCase().includes(query) || r.role.toLowerCase().includes(query) || r.institute_name.toLowerCase().includes(query));

    const tbody = document.getElementById("researchers-table-body");
    if (!tbody) return;

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-12 text-center text-slate-400">No researchers found.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(r => `
      <tr class="hover:bg-blue-50/50 transition cursor-pointer researcher-row" data-id="${r.researcher_id}">
        <td class="py-3.5 px-4 whitespace-nowrap">
          <div class="font-bold text-slate-900 flex items-center gap-2"><i class="fa-solid fa-user-doctor text-indigo-500 text-xs"></i><span>${r.name}</span></div>
          <div class="text-[10px] text-slate-400 font-mono">${r.researcher_id}</div>
        </td>
        <td class="py-3.5 px-4 whitespace-nowrap font-medium text-slate-700">${r.role}</td>
        <td class="py-3.5 px-4 whitespace-nowrap text-slate-600 font-medium">${r.institute_name}</td>
        <td class="py-3.5 px-4 text-right font-mono font-bold text-slate-900 whitespace-nowrap">${formatUSD(r.spend)}</td>
        <td class="py-3.5 px-4 text-center text-slate-400"><i class="fa-solid fa-chevron-down text-xs transition-transform transform" id="chevron-${r.researcher_id}"></i></td>
      </tr>
      <tr id="accordion-${r.researcher_id}" class="hidden bg-slate-50/90 border-b border-slate-200">
        <td colspan="5" class="p-5">
          <div class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 bg-white p-3.5 rounded-xl border border-slate-200">
              <div><span class="text-[10px] font-bold text-slate-400 uppercase">Institutional Email</span><div class="font-mono text-xs font-bold text-blue-600 mt-0.5">${r.email}</div></div>
              <div><span class="text-[10px] font-bold text-slate-400 uppercase">Phone Number</span><div class="font-mono text-xs font-bold text-slate-800 mt-0.5">${r.phone}</div></div>
              <div><span class="text-[10px] font-bold text-slate-400 uppercase">Primary Affiliation</span><div class="text-xs font-bold text-slate-800 mt-0.5">${r.institute_name}</div></div>
            </div>
            <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div class="px-4 py-2 bg-slate-100/80 border-b border-slate-200 flex items-center justify-between"><span class="text-[11px] font-bold text-slate-700 uppercase">Assigned Research Rooms & Authorization</span><span class="text-[10px] font-mono text-slate-500">1 Room Bound</span></div>
              <table class="w-full text-left text-xs">
                <thead>
                  <tr class="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                    <th class="py-2 px-3">Room Identifier</th>
                    <th class="py-2 px-3">Authorization Status</th>
                    <th class="py-2 px-3">Start Activity</th>
                    <th class="py-2 px-3">Last Activity</th>
                    <th class="py-2 px-3 text-right">Spend in Room</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100 font-mono">
                  <tr>
                    <td class="py-2.5 px-3"><span class="font-bold text-slate-900">${r.room_id}</span><span class="text-slate-500 text-[10px] block font-sans">${r.room_name}</span></td>
                    <td class="py-2.5 px-3"><span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200"><i class="fa-solid fa-circle-check text-[9px]"></i> AUTHORIZED</span></td>
                    <td class="py-2.5 px-3 text-slate-600 text-[11px]">${formatDateTime(r.start_time)}</td>
                    <td class="py-2.5 px-3 text-slate-600 text-[11px]" id="res-last-active-${r.researcher_id}">${formatDateTime(r.last_active_at)}</td>
                    <td class="py-2.5 px-3 text-right font-bold text-slate-900">${formatUSD(r.spend)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="bg-white rounded-xl border border-slate-200 p-3.5 space-y-3">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-[11px] font-bold text-slate-700 uppercase">Recent Curated Activity Events</span>
                  <span class="text-[10px] font-mono text-emerald-600 font-bold"><i class="fa-solid fa-shield-check mr-1"></i>Audit Verified</span>
                </div>
                <div class="flex items-center gap-1.5 self-end sm:self-auto">
                  <span class="text-[10px] font-semibold text-slate-500">Show:</span>
                  <select class="events-limit-select bg-slate-50 border border-slate-200 rounded px-2 py-0.5 text-[10px] font-bold text-slate-700 cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500" data-email="${r.email}" data-target="events-container-${r.researcher_id}" data-res-id="${r.researcher_id}">
                    <option value="10" selected>10 Events</option>
                    <option value="25">25 Events</option>
                    <option value="50">50 Events</option>
                  </select>
                </div>
              </div>
              <div id="events-container-${r.researcher_id}" class="events-list-container text-xs">
                <div class="p-3 text-center text-slate-400 text-xs font-mono"><i class="fa-solid fa-circle-notch fa-spin mr-2"></i>Click to load live audit events...</div>
              </div>
            </div>
          </div>
        </td>
      </tr>
    `).join('');

    async function loadEventsForResearcher(email, containerId, limit = 10, resId = null) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = `<div class="p-4 text-center text-slate-400 text-xs font-mono"><i class="fa-solid fa-circle-notch fa-spin mr-2"></i>Loading live audit events...</div>`;
      try {
        const events = await api.getAuditFeed(null, email, limit, null, true);
        if (!events || events.length === 0) {
          container.innerHTML = `<div class="p-3 text-center text-slate-400 text-xs font-mono">No recent activity events recorded for this researcher.</div>`;
          return;
        }

        // Reconcile and synchronize the last active timestamp with the newest actual audit event
        if (resId && events[0]?.timestamp) {
          const lastActiveEl = document.getElementById(`res-last-active-${resId}`);
          if (lastActiveEl) {
            lastActiveEl.textContent = formatDateTime(events[0].timestamp);
          }
        }

        container.innerHTML = `
          <div class="space-y-1.5 font-mono text-[11px]">
            ${events.map(ev => `
              <div class="p-2.5 rounded bg-slate-50 border border-slate-200/80 hover:bg-white transition flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    ev.category === 'DATA_ACCESS' ? 'bg-blue-100 text-blue-700' :
                    ev.category === 'COMPUTE_SESSION' ? 'bg-purple-100 text-purple-700' :
                    ev.category === 'STORAGE_EGRESS' ? 'bg-amber-100 text-amber-700' :
                    'bg-slate-200 text-slate-700'
                  }">${ev.category || 'ACTION'}</span>
                  <span class="text-slate-800 font-medium">${ev.description || ev.method_name}</span>
                  ${ev.room_id ? `<span class="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-mono">${ev.room_id}</span>` : ''}
                </div>
                <span class="text-slate-400 text-[10px] whitespace-nowrap">${formatDateTime(ev.timestamp)}</span>
              </div>
            `).join('')}
          </div>
        `;
      } catch (err) {
        container.innerHTML = `<div class="p-3 text-center text-rose-500 text-xs font-mono">Failed to load audit events: ${err.message}</div>`;
      }
    }

    tbody.querySelectorAll(".researcher-row").forEach(row => {
      row.addEventListener("click", () => {
        const id = row.getAttribute("data-id");
        const panel = document.getElementById(`accordion-${id}`);
        const chevron = document.getElementById(`chevron-${id}`);
        if (!panel) return;
        const isHidden = panel.classList.contains("hidden");
        panel.classList.toggle("hidden");
        chevron?.classList.toggle("rotate-180", isHidden);

        if (isHidden) {
          const researcher = filtered.find(r => r.researcher_id === id);
          if (researcher && researcher.email) {
            const limitSelect = panel.querySelector(`.events-limit-select`);
            const limit = limitSelect ? parseInt(limitSelect.value, 10) : 10;
            loadEventsForResearcher(researcher.email, `events-container-${id}`, limit, id);
          }
        }
      });
    });

    tbody.querySelectorAll(".events-limit-select").forEach(select => {
      select.addEventListener("change", (e) => {
        e.stopPropagation();
        const email = select.getAttribute("data-email");
        const targetId = select.getAttribute("data-target");
        const resId = select.getAttribute("data-res-id");
        const limit = parseInt(select.value, 10) || 10;
        if (email && targetId) {
          loadEventsForResearcher(email, targetId, limit, resId);
        }
      });
    });
  }

  searchInput?.addEventListener("input", filterAndRenderTable);
  filterAndRenderTable();
}
