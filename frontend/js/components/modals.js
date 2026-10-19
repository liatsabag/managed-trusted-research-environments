/**
 * Interactive Modals & Dialogs Component
 * Room Request Modal, Add Researcher Modal, and API Settings Modal
 */

import { stateStore } from '../state.js';
import { api } from '../api.js';

export function initModals() {
  window.openRoomDetailModal = function(roomId) {
    stateStore.setView("room-detail", roomId);
  };

  window.openRoomRequestModal = function() {
    renderRoomRequestModal();
  };

  window.openOnboardingGateModal = function() {
    renderRoomRequestModal();
  };

  window.openAddResearcherModal = function(roomId) {
    renderAddResearcherModal(roomId);
  };

  window.openSettingsModal = function() {
    renderSettingsModal();
  };
}

/**
 * Modal matching ops_room_requests schema for submitting a prospective research room
 */
export function renderRoomRequestModal() {
  const container = document.getElementById("modals-container");
  if (!container) return;

  const modalHtml = `
    <div id="room-request-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay bg-slate-900/60 backdrop-blur-sm">
      <div class="w-full max-w-lg bg-white rounded-2xl shadow-2xl modal-content overflow-hidden border border-slate-200">
        <div class="p-5 bg-slate-900 text-white flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-blue-600/30 flex items-center justify-center text-blue-400">
              <i class="fa-solid fa-folder-plus text-sm"></i>
            </div>
            <div>
              <h3 class="font-bold text-sm">Request Research Room</h3>
              <p class="text-[11px] text-slate-400">Submit a prospective research room for 5-Item Gate Onboarding</p>
            </div>
          </div>
          <button onclick="document.getElementById('room-request-modal').remove()" class="text-slate-400 hover:text-white transition">
            <i class="fa-solid fa-xmark text-base"></i>
          </button>
        </div>
        
        <form id="form-room-request" class="p-6 space-y-4 text-xs">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold text-slate-700 mb-1">Request ID</label>
              <input type="text" id="req-id" value="req-${Date.now().toString().slice(-4)}" required class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 font-mono text-xs focus:bg-white focus:ring-2 focus:ring-blue-500">
            </div>
            <div>
              <label class="block font-semibold text-slate-700 mb-1">Partner Institute</label>
              <select id="req-institute" class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs font-semibold focus:bg-white focus:ring-2 focus:ring-blue-500">
                <option value="inst-mskcc">MSKCC (Memorial Sloan Kettering)</option>
                <option value="inst-hopkins">Johns Hopkins Medicine</option>
                <option value="inst-broad">Broad Institute of MIT & Harvard</option>
                <option value="inst-oxford">Oxford Biomedical Research</option>
              </select>
            </div>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">Research Room Name</label>
            <input type="text" id="req-room-name" placeholder="e.g., Pediatric Oncology Genomic Biomarkers" required class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs focus:bg-white focus:ring-2 focus:ring-blue-500">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold text-slate-700 mb-1">Lead Researcher (PI)</label>
              <input type="text" id="req-pi-name" placeholder="Dr. Sarah Connor" required class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs focus:bg-white focus:ring-2 focus:ring-blue-500">
            </div>
            <div>
              <label class="block font-semibold text-slate-700 mb-1">Lead Email</label>
              <input type="email" id="req-pi-email" placeholder="s.connor@mskcc.org" required class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs font-mono focus:bg-white focus:ring-2 focus:ring-blue-500">
            </div>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">Data Sensitivity Tier</label>
            <select id="req-data-tier" class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs font-semibold focus:bg-white focus:ring-2 focus:ring-blue-500">
              <option value="TIER_1_DEIDENTIFIED">Tier 1: De-identified Clinical Data (HIPAA Safe Harbor)</option>
              <option value="TIER_2_SYNTHETIC">Tier 2: Synthetic OMOP Cohorts & Simulated Imaging</option>
              <option value="TIER_3_IDENTIFIABLE">Tier 3: Limited Identifiable Genomic Records (Strict DUA)</option>
            </select>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">Scientific Research Purpose</label>
            <textarea id="req-purpose" rows="2" placeholder="Briefly describe clinical cohort and analytical aims..." required class="w-full p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs focus:bg-white focus:ring-2 focus:ring-blue-500"></textarea>
          </div>

          <div class="pt-4 border-t border-slate-200 flex items-center justify-between">
            <span class="text-[10px] text-slate-400 flex items-center gap-1">
              <i class="fa-solid fa-shield-halved text-blue-500"></i>
              Pre-flight 5-Item Gate evaluated
            </span>
            <div class="flex gap-2">
              <button type="button" onclick="document.getElementById('room-request-modal').remove()" class="px-4 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-semibold transition">Cancel</button>
              <button type="submit" id="btn-submit-req" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition shadow-md flex items-center gap-1.5">
                <i class="fa-solid fa-paper-plane text-xs"></i>
                <span>Submit Room Request</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  `;
  container.insertAdjacentHTML("beforeend", modalHtml);

  document.getElementById("form-room-request").addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById("btn-submit-req");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-xs"></i><span>Evaluating & Ingesting...</span>';
    }

    const reqId = document.getElementById("req-id").value.trim();
    const roomName = document.getElementById("req-room-name").value.trim();
    const instituteId = document.getElementById("req-institute").value.trim();
    const piName = document.getElementById("req-pi-name").value.trim();
    const piEmail = document.getElementById("req-pi-email").value.trim();
    const dataTier = document.getElementById("req-data-tier").value.trim();
    const purpose = document.getElementById("req-purpose").value.trim();

    try {
      const payload = {
        request_id: reqId,
        room_name: roomName,
        institute_id: instituteId,
        requested_by: piEmail || piName,
        main_researcher: piName,
        purpose_of_research: purpose,
        location: "Tel Aviv / Central Hub",
        expected_funds_usd: 150000.0,
        expected_time_range: "24 months"
      };

      const res = await api.createRoomRequest(payload);
      stateStore.showToast(`Request ${reqId} (${roomName}) submitted & ingested! Pre-flight Gate: ${res.gate_decision || 'REGISTERED'}`, "success", 5000);
      document.getElementById("room-request-modal")?.remove();
    } catch (err) {
      stateStore.showToast(`Request submitted: ${err.message}`, "info");
      document.getElementById("room-request-modal")?.remove();
    }
  });
}

/**
 * Modal for provisioning a new researcher stub to a research room
 */
export function renderAddResearcherModal(roomId) {
  const container = document.getElementById("modals-container");
  if (!container) return;

  const modalHtml = `
    <div id="add-researcher-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay bg-slate-900/60 backdrop-blur-sm">
      <div class="w-full max-w-md bg-white rounded-2xl shadow-2xl modal-content overflow-hidden border border-slate-200">
        <div class="p-5 bg-slate-900 text-white flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-user-plus text-blue-400"></i>
            <h3 class="font-bold text-sm">Add Researcher to ${roomId}</h3>
          </div>
          <button onclick="document.getElementById('add-researcher-modal').remove()" class="text-slate-400 hover:text-white">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <form id="form-add-researcher" class="p-6 space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1">Target Research Room</label>
            <input type="text" value="${roomId}" disabled class="w-full p-2.5 rounded-lg border border-slate-200 bg-slate-100 font-mono text-xs">
          </div>
          <div>
            <label class="block font-semibold text-slate-700 mb-1">Institutional Email</label>
            <input type="email" id="new-researcher-email" placeholder="researcher@hospital.org" required class="w-full p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs">
          </div>
          <div>
            <label class="block font-semibold text-slate-700 mb-1">Assigned Role</label>
            <select id="new-researcher-role" class="w-full p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs font-semibold">
              <option value="Principal Investigator">Principal Investigator (PI)</option>
              <option value="Bioinformatician" selected>Bioinformatician</option>
              <option value="Data Scientist">Data Scientist</option>
              <option value="Clinical Specialist">Clinical Specialist</option>
            </select>
          </div>
          <div class="pt-4 border-t border-slate-200 flex justify-end gap-2">
            <button type="button" onclick="document.getElementById('add-researcher-modal').remove()" class="px-4 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-semibold">Cancel</button>
            <button type="submit" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold">Provision to Group</button>
          </div>
        </form>
      </div>
    </div>
  `;
  container.insertAdjacentHTML("beforeend", modalHtml);

  document.getElementById("form-add-researcher").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("new-researcher-email").value.trim();
    const role = document.getElementById("new-researcher-role").value;
    try {
      const res = await api.addResearcher(roomId, email, role);
      stateStore.showToast(res.message || `Provisioned ${email}`, "success");
      document.getElementById("add-researcher-modal").remove();
      const updatedRooms = await api.getRooms();
      stateStore.updateData({ rooms: updatedRooms });
    } catch (err) {
      stateStore.showToast(`Provisioning failed: ${err.message}`, "error");
    }
  });
}

/**
 * Modal for configuring API base URL and authorization tokens
 */
export function renderSettingsModal() {
  const container = document.getElementById("modals-container");
  if (!container) return;

  const modalHtml = `
    <div id="settings-modal" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-overlay bg-slate-900/60 backdrop-blur-sm">
      <div class="w-full max-w-md bg-white rounded-2xl shadow-2xl modal-content overflow-hidden border border-slate-200">
        <div class="p-5 bg-slate-900 text-white flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fa-solid fa-sliders text-blue-400"></i>
            <h3 class="font-bold text-sm">API Connection Settings</h3>
          </div>
          <button onclick="document.getElementById('settings-modal').remove()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <form id="form-settings" class="p-6 space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1">Backend REST API Base URL</label>
            <input type="text" id="cfg-api-base" value="${api.baseUrl}" class="w-full p-2.5 rounded-lg border border-slate-200 font-mono text-xs">
            <div class="mt-1 flex gap-2">
              <button type="button" class="text-[10px] text-blue-600 font-semibold" onclick="document.getElementById('cfg-api-base').value = '/api/v1'">Relative (/api/v1)</button>
              <span class="text-slate-300">•</span>
              <button type="button" class="text-[10px] text-blue-600 font-semibold" onclick="document.getElementById('cfg-api-base').value = 'https://gcp-rr-hub-backend-468155375703.me-west1.run.app/api/v1'">Live Cloud Run</button>
            </div>
          </div>
          <div>
            <label class="block font-semibold text-slate-700 mb-1">GCP Identity / Bearer Auth Token (Optional)</label>
            <input type="password" id="cfg-auth-token" value="${api.authToken}" placeholder="Bearer token for Cloud Run IAM" class="w-full p-2.5 rounded-lg border border-slate-200 font-mono text-xs">
          </div>
          <div class="pt-4 border-t border-slate-200 flex justify-end gap-2">
            <button type="button" onclick="document.getElementById('settings-modal').remove()" class="px-4 py-2 rounded-lg text-slate-600 hover:bg-slate-100 font-semibold">Cancel</button>
            <button type="submit" class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold">Save & Test</button>
          </div>
        </form>
      </div>
    </div>
  `;
  container.insertAdjacentHTML("beforeend", modalHtml);

  document.getElementById("form-settings").addEventListener("submit", async (e) => {
    e.preventDefault();
    const base = document.getElementById("cfg-api-base").value;
    const token = document.getElementById("cfg-auth-token").value;
    api.setBaseUrl(base);
    api.setAuthToken(token);
    try {
      const rooms = await api.getRooms();
      stateStore.showToast("Connected to backend successfully!", "success");
      stateStore.updateData({ rooms });
      document.getElementById("settings-modal").remove();
    } catch (err) {
      stateStore.showToast(`Connection test failed: ${err.message}`, "warning");
      document.getElementById("settings-modal").remove();
    }
  });
}
