/**
 * GCP Health Data Platform - Application Orchestrator & View Switcher
 * Coordinates primary views: Overview, Fleet Rooms, Room Details, Researchers, Infrastructure, Audit Logs, Compliance, and FinOps
 */

import { stateStore } from './state.js';
import { api } from './api.js';
import { CONFIG } from './config.js';

import { renderHeader } from './components/header.js';
import { renderOverviewView } from './components/overviewView.js';
import { renderRoomsView } from './components/roomsView.js';
import { renderRoomDetailView } from './components/roomDetailView.js';
import { renderResearchersView } from './components/researchersView.js';
import { renderAuditView } from './components/auditView.js';
import { renderComplianceView } from './components/complianceView.js';
import { renderFinOpsView } from './components/finopsView.js';
import { renderReportsView } from './components/reportsView.js';
import { renderResourcesView } from './components/resourcesView.js';
import { renderAirlockView } from './components/airlockView.js';
import { initModals } from './components/modals.js';

let pollTimer = null;

export async function initApp() {
  console.log(`[App] Initializing ${CONFIG.APP_NAME} v${CONFIG.VERSION}`);

  // 1. Initialize Modals & Header
  initModals();
  renderHeader();

  // 2. Render Initial Skeleton View Immediately (No 0s flashing)
  const initialState = stateStore.getState();
  switchView(initialState.currentView, initialState.selectedRoomId);

  // 3. Register State Change Subscribers
  stateStore.addEventListener("viewChanged", (e) => {
    renderHeader();
    switchView(e.detail.view, e.detail.roomId);
  });

  stateStore.addEventListener("filtersChanged", () => {
    const state = stateStore.getState();
    if (state.currentView === "fleet") {
      renderRoomsView();
    }
  });

  stateStore.addEventListener("personaChanged", () => {
    renderHeader();
    const state = stateStore.getState();
    renderCurrentView(state.currentView, state.selectedRoomId);
  });

  stateStore.addEventListener("dataUpdated", () => {
    renderHeader();
    const state = stateStore.getState();
    // Only re-render if on overview or fleet to avoid resetting user interactions
    if (state.currentView === "overview" || state.currentView === "fleet") {
      renderCurrentView(state.currentView, state.selectedRoomId);
    }
  });

  stateStore.addEventListener("manualRefreshRequested", async () => {
    await refreshFleetData();
    const state = stateStore.getState();
    renderCurrentView(state.currentView, state.selectedRoomId);
    stateStore.showToast("Fleet state and telemetry updated!", "success");
  });

  // 4. Fetch Live Data in background and populate
  await refreshFleetData();

  // 5. Start Silent Background Polling
  startPolling();
}

function renderCurrentView(viewName, roomId = null) {
  if (viewName === "overview") renderOverviewView();
  else if (viewName === "fleet") renderRoomsView();
  else if (viewName === "room-detail" && roomId) renderRoomDetailView(roomId);
  else if (viewName === "resources") renderResourcesView();
  else if (viewName === "airlock") renderAirlockView();
  else if (viewName === "researchers") renderResearchersView();
  else if (viewName === "audit-logs") renderAuditView();
  else if (viewName === "compliance") renderComplianceView();
  else if (viewName === "finops") renderFinOpsView();
  else if (viewName === "reports") renderReportsView();
}

/**
 * Switch between the views: 'overview', 'fleet', 'room-detail', 'researchers', 'resources', 'airlock', 'audit-logs', 'compliance', 'finops', 'reports'
 */
function switchView(viewName, roomId = null) {
  const panelIds = [
    'view-overview',
    'view-fleet',
    'view-room-detail',
    'view-researchers',
    'view-resources',
    'view-airlock',
    'view-audit-logs',
    'view-compliance',
    'view-finops',
    'view-reports'
  ];

  // Hide all panels
  panelIds.forEach(id => {
    document.getElementById(id)?.classList.add("hidden");
  });

  if (viewName === "room-detail" && roomId) {
    document.getElementById("view-room-detail")?.classList.remove("hidden");
    renderRoomDetailView(roomId);
  } else if (viewName === "fleet") {
    document.getElementById("view-fleet")?.classList.remove("hidden");
    renderRoomsView();
  } else if (viewName === "resources") {
    document.getElementById("view-resources")?.classList.remove("hidden");
    renderResourcesView();
  } else if (viewName === "airlock") {
    document.getElementById("view-airlock")?.classList.remove("hidden");
    renderAirlockView();
  } else if (viewName === "researchers") {
    document.getElementById("view-researchers")?.classList.remove("hidden");
    renderResearchersView();
  } else if (viewName === "audit-logs") {
    document.getElementById("view-audit-logs")?.classList.remove("hidden");
    renderAuditView();
  } else if (viewName === "compliance") {
    document.getElementById("view-compliance")?.classList.remove("hidden");
    renderComplianceView();
  } else if (viewName === "finops") {
    document.getElementById("view-finops")?.classList.remove("hidden");
    renderFinOpsView();
  } else if (viewName === "reports") {
    document.getElementById("view-reports")?.classList.remove("hidden");
    renderReportsView();
  } else {
    document.getElementById("view-overview")?.classList.remove("hidden");
    renderOverviewView();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Fetch latest rooms, telemetry, finops, and compliance from REST API
 */
async function refreshFleetData() {
  stateStore.setLoading(true);
  try {
    const [rooms, telemetry, finops, compliance, horizons, matrix, forecast] = await Promise.all([
      api.getRooms(),
      api.getTelemetryOverview().catch(() => null),
      api.getFinOpsSummary().catch(() => null),
      api.getComplianceSummary().catch(() => []),
      api.getComplianceHorizons().catch(() => null),
      api.getFinOpsMatrix().catch(() => null),
      api.getFinOpsForecast().catch(() => null)
    ]);
    stateStore.updateData({
      rooms,
      telemetryOverview: telemetry,
      finopsSummary: finops,
      complianceSummary: compliance,
      complianceHorizons: horizons,
      finopsMatrix: matrix,
      finopsForecast: forecast
    });
  } catch (err) {
    console.error("[App] Failed to load data:", err);
    stateStore.showToast(`API Connection Notice: ${err.message}`, "warning", 5000);
  } finally {
    stateStore.setLoading(false);
  }
}

/**
 * Start silent background polling loop
 */
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  // Poll silently every 60 seconds without disrupting UI
  pollTimer = setInterval(async () => {
    try {
      const [rooms, telemetry, finops] = await Promise.all([
        api.getRooms(),
        api.getTelemetryOverview().catch(() => null),
        api.getFinOpsSummary().catch(() => null)
      ]);
      stateStore.updateData({ rooms, telemetryOverview: telemetry, finopsSummary: finops });
    } catch (e) {
      console.warn("[App] Background poll notice:", e);
    }
  }, 60000);
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", initApp);
