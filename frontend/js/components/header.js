/**
 * Top Application Header Component
 * Clean top navigation bar with project metadata, view tabs, persona switcher, and live clock
 */

import { stateStore } from '../state.js';
import { CONFIG } from '../config.js';

export function renderHeader() {
  const container = document.getElementById("header-container");
  if (!container) return;

  const state = stateStore.getState();
  const currentView = state.currentView;

  const navItems = [
    { id: 'overview', label: 'Overview', icon: 'fa-chart-pie' },
    { id: 'fleet', label: 'Rooms', icon: 'fa-hospital' },
    { id: 'researchers', label: 'Researchers', icon: 'fa-users' },
    { id: 'resources', label: 'Infrastructure', icon: 'fa-server' },
    { id: 'airlock', label: 'Airlock Egress', icon: 'fa-shield-virus' },
    { id: 'audit-logs', label: 'Audit Logs', icon: 'fa-shield-halved' },
    { id: 'compliance', label: 'Compliance & Gates', icon: 'fa-file-shield' },
    { id: 'finops', label: 'FinOps', icon: 'fa-coins' },
    { id: 'reports', label: 'Reports', icon: 'fa-file-lines' }
  ];

  container.innerHTML = `
    <div class="w-full px-4 sm:px-6 lg:px-8 py-2">
      <!-- Top Level: Brand & Controls -->
      <div class="flex items-center justify-between pb-2 border-b border-slate-800 gap-3">
        <!-- Brand / System Title -->
        <div class="cursor-pointer flex items-center gap-2.5 shrink-0" id="brand-home-btn">
          <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shrink-0">
            <i class="fa-solid fa-hospital text-sm"></i>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-extrabold text-sm md:text-base tracking-tight text-white whitespace-nowrap">${CONFIG.APP_NAME}</span>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                ${CONFIG.DEFAULT_PROJECT}
              </span>
            </div>
            <div class="text-[10px] text-slate-400 font-medium hidden sm:block">Central Research Fleet Administrator Portal</div>
          </div>
        </div>

        <!-- Right: Persona, Refresh & Clock -->
        <div class="flex items-center gap-3 shrink-0">
          <div class="relative">
            <select id="persona-select" class="appearance-none bg-slate-800 text-slate-200 border border-slate-700 rounded-lg pl-3 pr-8 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer">
              ${Object.values(CONFIG.PERSONAS).map(p => `
                <option value="${p.id}" ${state.activePersona === p.id ? 'selected' : ''}>
                  ${p.title}
                </option>
              `).join('')}
            </select>
            <i class="fa-solid fa-chevron-down absolute right-2.5 top-2.5 text-slate-400 pointer-events-none text-[10px]"></i>
          </div>

          <button id="btn-refresh-data" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition cursor-pointer" title="Refresh Live Data">
            <i class="fa-solid fa-rotate text-xs"></i>
          </button>

          <div class="hidden md:flex flex-col text-right font-mono text-[10px] text-slate-400 pl-2 border-l border-slate-800">
            <span id="live-clock-time">--:--:--</span>
            <span class="text-[9px] text-slate-500">Live Telemetry</span>
          </div>
        </div>
      </div>

      <!-- Bottom Level: Spacious Navigation Tabs -->
      <nav class="flex items-center gap-1.5 pt-2 overflow-x-auto">
        ${navItems.map(item => {
          const isActive = currentView === item.id || (item.id === 'fleet' && currentView === 'room-detail');
          return `
            <button 
              id="nav-btn-${item.id}" 
              class="px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 whitespace-nowrap shrink-0 cursor-pointer ${isActive ? 'bg-blue-600 text-white shadow-sm ring-1 ring-blue-400' : 'text-slate-300 hover:text-white hover:bg-slate-800'}"
            >
              <i class="fa-solid ${item.icon} text-xs"></i>
              <span>${item.label}</span>
            </button>
          `;
        }).join('')}
      </nav>
    </div>
  `;

  // Attach event handlers
  document.getElementById("brand-home-btn")?.addEventListener("click", () => {
    stateStore.setView("overview");
  });

  navItems.forEach(item => {
    document.getElementById(`nav-btn-${item.id}`)?.addEventListener("click", () => {
      stateStore.setView(item.id);
    });
  });

  const personaSelect = document.getElementById("persona-select");
  personaSelect?.addEventListener("change", (e) => {
    stateStore.setPersona(e.target.value);
  });

  const refreshBtn = document.getElementById("btn-refresh-data");
  refreshBtn?.addEventListener("click", () => {
    stateStore.triggerManualRefresh();
  });

  updateLiveClock();
}

function updateLiveClock() {
  const clockEl = document.getElementById("live-clock-time");
  if (!clockEl) return;
  const now = new Date();
  clockEl.textContent = now.toTimeString().split(' ')[0] + ' UTC';
}

if (!window.__headerClockInterval) {
  window.__headerClockInterval = setInterval(updateLiveClock, 1000);
}
