/**
 * GCP Health Data Platform - Reactive State Store
 * Supports 3 primary views: Overview (Main Dashboard), Fleet (Rooms Table), and Room Details
 */

import { CONFIG } from './config.js';

class StateStore extends EventTarget {
  constructor() {
    super();
    this.state = {
      // Navigation: 'overview' | 'fleet' | 'room-detail'
      currentView: 'overview',
      selectedRoomId: null,
      
      // Selected persona
      activePersona: localStorage.getItem("gcp_active_persona") || "admin",
      
      // Filters
      searchQuery: '',
      statusFilter: 'ALL',
      
      // Collections
      rooms: [],
      telemetryOverview: null,
      selectedRoomDetail: null,
      selectedRoomInventory: null,
      selectedRoomActivity: null,
      selectedRoomFinOps: null,
      
      // Metadata
      lastUpdated: null,
      isLoading: true,
      loading: true,
      error: null
    };
  }

  getState() {
    return this.state;
  }

  setView(view, roomId = null) {
    this.state.currentView = view;
    this.state.selectedRoomId = roomId;
    this.dispatchEvent(new CustomEvent("viewChanged", { detail: { view, roomId } }));
  }

  setPersona(personaId) {
    if (CONFIG.PERSONAS[personaId]) {
      this.state.activePersona = personaId;
      localStorage.setItem("gcp_active_persona", personaId);
      this.dispatchEvent(new CustomEvent("personaChanged", { detail: personaId }));
    }
  }

  setFilters(searchQuery, statusFilter) {
    this.state.searchQuery = searchQuery;
    this.state.statusFilter = statusFilter;
    this.dispatchEvent(new CustomEvent("filtersChanged", { detail: { searchQuery, statusFilter } }));
  }

  updateData(newData) {
    this.state = {
      ...this.state,
      ...newData,
      isLoading: false,
      loading: false,
      lastUpdated: new Date()
    };
    this.dispatchEvent(new CustomEvent("dataUpdated", { detail: this.state }));
  }

  setLoading(isLoading) {
    this.state.isLoading = isLoading;
    this.state.loading = isLoading;
    this.dispatchEvent(new CustomEvent("loadingChanged", { detail: isLoading }));
  }

  showToast(message, type = "info", duration = 4000) {
    const toastContainer = document.getElementById("toast-container");
    if (!toastContainer) return;

    const toastId = "toast-" + Date.now();
    const colors = {
      info: "bg-blue-600 text-white",
      success: "bg-emerald-600 text-white",
      warning: "bg-amber-600 text-white",
      error: "bg-rose-600 text-white"
    };
    const icons = {
      info: "fa-circle-info",
      success: "fa-circle-check",
      warning: "fa-triangle-exclamation",
      error: "fa-circle-xmark"
    };

    const html = `
      <div id="${toastId}" class="flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl text-xs font-medium ${colors[type] || colors.info} transform transition-all duration-300 translate-y-2 opacity-0">
        <i class="fa-solid ${icons[type] || icons.info} text-sm"></i>
        <span>${message}</span>
      </div>
    `;

    toastContainer.insertAdjacentHTML("beforeend", html);
    const toastEl = document.getElementById(toastId);
    setTimeout(() => toastEl?.classList.remove("translate-y-2", "opacity-0"), 10);
    setTimeout(() => {
      if (toastEl) {
        toastEl.classList.add("opacity-0", "translate-y-2");
        setTimeout(() => toastEl.remove(), 300);
      }
    }, duration);
  }
}

export const stateStore = new StateStore();
