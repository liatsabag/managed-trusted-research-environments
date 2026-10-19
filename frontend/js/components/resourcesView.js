/**
 * Resources & Infrastructure View Component
 * Clean, organized mapping of Storage Buckets, BigQuery Shared Datasets, Notebook Templates, and Spoke VPCs.
 */

import { api } from '../api.js';
import { stateStore } from '../state.js';

export async function renderResourcesView() {
  const container = document.getElementById("view-resources");
  if (!container) return;

  container.innerHTML = `
    <div class="flex items-center justify-center py-20 text-slate-400">
      <i class="fa-solid fa-circle-notch fa-spin text-2xl mr-3 text-blue-600"></i>
      <span class="text-sm font-medium">Discovering GCP physical assets, storage buckets, and shared datasets...</span>
    </div>
  `;

  try {
    const data = await api.getInfrastructureOverview();
    buildResourcesLayout(container, data);
  } catch (err) {
    container.innerHTML = `
      <div class="p-6 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm">
        <div class="font-bold mb-1"><i class="fa-solid fa-triangle-exclamation mr-1"></i> Failed to load cloud infrastructure topology</div>
        <div>${err.message || "An unexpected error occurred."}</div>
      </div>
    `;
  }
}

function buildResourcesLayout(container, data) {
  const counts = data.summary_counts || {};
  const buckets = data.storage_buckets || [];
  const datasets = data.shared_datasets || [];
  const templates = data.notebook_templates || [];
  const vpcs = data.vpcs || [];

  const totalFiles = buckets.reduce((acc, b) => acc + (b.object_count || 0), 0);
  const totalBytes = buckets.reduce((acc, b) => acc + (b.total_bytes || 0), 0);
  const totalVolStr = totalBytes > 1048576 
    ? `${(totalBytes / (1024 * 1024)).toFixed(2)} MB` 
    : `${(totalBytes / 1024).toFixed(1)} KB`;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Header Banner -->
      <div class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-6 shadow-xl border border-slate-800">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div class="flex items-center gap-2 text-indigo-400 text-xs font-mono uppercase tracking-wider mb-1">
              <i class="fa-solid fa-server"></i><span>GCP Health Data Platform Infrastructure</span>
            </div>
            <h1 class="text-2xl font-extrabold tracking-tight">Cloud Infrastructure, Buckets & Environments</h1>
            <p class="text-slate-300 text-xs mt-1">
              Maintain linkage between logical research rooms and physical GCP assets: Buckets, Shared Datasets, Subnets, and Runtime Templates.
            </p>
          </div>
          <button id="btn-open-link-bucket" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl shadow transition flex items-center gap-2 cursor-pointer shrink-0">
            <i class="fa-solid fa-link"></i><span>Link Storage Bucket</span>
          </button>
        </div>
      </div>

      <!-- KPI Summary Cards -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold shrink-0"><i class="fa-solid fa-hospital text-lg"></i></div>
          <div><div class="text-[11px] font-semibold text-slate-500 uppercase">Active Research Rooms</div><div class="text-lg font-extrabold text-slate-900">${counts.total_rooms || 4} Rooms</div></div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-3 md:col-span-2">
          <div class="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold shrink-0"><i class="fa-solid fa-bucket text-lg"></i></div>
          <div><div class="text-[11px] font-semibold text-slate-500 uppercase">Storage Buckets & Volume</div><div class="text-lg font-extrabold text-slate-900 flex items-center gap-2"><span>${counts.total_storage_buckets || buckets.length} Buckets</span><span class="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-mono">${totalFiles} files (${totalVolStr})</span></div></div>
        </div>
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold shrink-0"><i class="fa-solid fa-database text-lg"></i></div>
          <div><div class="text-[11px] font-semibold text-slate-500 uppercase">Shared Datasets</div><div class="text-lg font-extrabold text-slate-900">${counts.shared_datasets || datasets.length} (${counts.shared_tables || 4} Tables)</div></div>
        </div>
      </div>

      <!-- Section 1: Cloud Storage Buckets Table -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="px-6 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
          <div class="flex items-center gap-2"><i class="fa-solid fa-bucket text-amber-500"></i><h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Cloud Storage Buckets</h2></div>
          <span class="text-xs font-mono text-slate-500">${buckets.length} Total Buckets</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                <th class="py-2.5 px-4">Bucket Name</th>
                <th class="py-2.5 px-4">Related Project</th>
                <th class="py-2.5 px-4">Number of Files</th>
                <th class="py-2.5 px-4">Size</th>
                <th class="py-2.5 px-4">Linked Room</th>
                <th class="py-2.5 px-4">Role</th>
                <th class="py-2.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-700">
              ${buckets.map(b => {
                const isHub = b.project_id === 'gcp-rr-hub-core';
                const roleBadge = b.role_type === 'INBOUND' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                                  b.role_type === 'EXPORT' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                                  b.role_type.startsWith('HUB') ? 'bg-purple-50 text-purple-700 border-purple-200' :
                                  'bg-slate-100 text-slate-700 border-slate-200';
                const sz = b.total_bytes > 1048576 ? `${(b.total_bytes / 1048576).toFixed(2)} MB` : `${(b.total_bytes / 1024).toFixed(1)} KB`;
                return `
                  <tr class="hover:bg-slate-50 transition border-b border-slate-100">
                    <td class="py-2.5 px-4 font-mono font-bold text-slate-900 flex items-center gap-2">
                      <i class="fa-solid fa-bucket ${isHub ? 'text-purple-500' : 'text-amber-500'}"></i><span>gs://${b.bucket_name}</span>
                    </td>
                    <td class="py-2.5 px-4 font-mono text-[11px] text-slate-700">${b.project_id}</td>
                    <td class="py-2.5 px-4 font-mono text-[11px] font-semibold">${b.object_count} files</td>
                    <td class="py-2.5 px-4 font-mono text-[11px] font-semibold">${sz}</td>
                    <td class="py-2.5 px-4 font-mono">${b.room_id ? `<button class="btn-jump-room text-blue-600 hover:underline font-bold cursor-pointer" data-room="${b.room_id}">${b.room_id}</button>` : `<span class="text-slate-400 font-mono text-[11px] italic">Central Hub</span>`}</td>
                    <td class="py-2.5 px-4"><span class="inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${roleBadge}">${b.role_type}</span></td>
                    <td class="py-2.5 px-4 text-right">${b.room_id ? `<button class="btn-detach-bucket px-2.5 py-1 text-[11px] rounded bg-red-50 hover:bg-red-100 text-red-700 font-semibold border border-red-200 cursor-pointer" data-room="${b.room_id}" data-bucket="${b.bucket_name}"><i class="fa-solid fa-unlink mr-1"></i>Detach</button>` : `<span class="text-[10px] text-slate-400 italic">Hub Core</span>`}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section 2: BigQuery Central Sharing -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="px-6 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
          <div class="flex items-center gap-2"><i class="fa-solid fa-database text-emerald-600"></i><h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">BigQuery Central Data Sharing & Reference Catalog</h2></div>
          <span class="text-xs font-mono text-slate-500">Hub Shared Datasets</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                <th class="py-2.5 px-4">Dataset Listing</th>
                <th class="py-2.5 px-4">Table Name & Purpose</th>
                <th class="py-2.5 px-4">Schema Attributes</th>
                <th class="py-2.5 px-4">Row Count</th>
                <th class="py-2.5 px-4">Subscribed Rooms / Projects</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-700">
              ${datasets.flatMap(d => d.tables.map(t => `
                <tr class="hover:bg-slate-50 transition border-b border-slate-100">
                  <td class="py-3 px-4 font-mono font-bold text-slate-900"><div>${d.dataset_id}</div><div class="text-[10px] text-slate-400 font-normal">${d.project_id}</div></td>
                  <td class="py-3 px-4"><div class="font-mono font-bold text-indigo-700 text-xs">${t.table_id}</div><div class="text-[11px] text-slate-500 mt-0.5">${t.description}</div></td>
                  <td class="py-3 px-4"><div class="flex flex-wrap gap-1 max-w-xs">${t.schema_fields.map(f => `<span class="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-mono text-[9px]">${f}</span>`).join('')}</div></td>
                  <td class="py-3 px-4 font-mono text-xs font-bold text-slate-800">${t.row_count.toLocaleString()} rows</td>
                  <td class="py-3 px-4"><div class="flex flex-wrap gap-1">${d.subscribed_rooms.map(r => `<span class="px-1.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[9px] rounded font-bold">${r}</span>`).join('')}</div></td>
                </tr>
              `)).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section 3: Notebook Runtime Templates -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="px-6 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
          <div class="flex items-center gap-2"><i class="fa-solid fa-cube text-indigo-500"></i><h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Notebook Runtime Templates (Colab Enterprise & Vertex AI)</h2></div>
          <span class="text-xs font-mono text-slate-500">${templates.length} Profiles</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                <th class="py-2.5 px-4">Template Title</th>
                <th class="py-2.5 px-4">Machine Configuration</th>
                <th class="py-2.5 px-4">Target Workloads</th>
                <th class="py-2.5 px-4">Preinstalled Packages</th>
                <th class="py-2.5 px-4">Idle Shutdown</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-700">
              ${templates.map(tpl => `
                <tr class="hover:bg-slate-50 transition border-b border-slate-100">
                  <td class="py-3 px-4"><div class="font-bold text-slate-900 text-xs">${tpl.title}</div><div class="text-[10px] text-slate-400 font-mono mt-0.5">${tpl.container_image.split('/').pop()}</div></td>
                  <td class="py-3 px-4 font-mono"><div class="font-bold text-indigo-700">${tpl.machine_type}</div><div class="text-[10px] text-slate-500">${tpl.vcpus} vCPUs • ${tpl.ram_gb} GB RAM • ${tpl.gpu_type ? 'NVIDIA L4' : `${tpl.boot_disk_gb}GB SSD`}</div></td>
                  <td class="py-3 px-4 text-slate-600">${tpl.target_workloads}</td>
                  <td class="py-3 px-4"><div class="flex flex-wrap gap-1 max-w-sm">${tpl.preinstalled_libraries.map(pkg => `<span class="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-mono text-[9px]">${pkg}</span>`).join('')}</div></td>
                  <td class="py-3 px-4 font-mono font-semibold text-slate-700">${tpl.idle_shutdown_minutes} mins</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section 4: Virtual Private Cloud (VPC) & Security Perimeters Table -->
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="px-6 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
          <div class="flex items-center gap-2"><i class="fa-solid fa-network-wired text-blue-500"></i><h2 class="text-xs font-bold text-slate-900 uppercase tracking-wider">Virtual Private Cloud (VPC) & Security Perimeters</h2></div>
          <span class="text-xs font-mono text-slate-500">VPC-SC Room Isolation</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                <th class="py-2.5 px-4">Assigned Room</th>
                <th class="py-2.5 px-4">Network Name</th>
                <th class="py-2.5 px-4">Subnet & CIDR Range</th>
                <th class="py-2.5 px-4">Region</th>
                <th class="py-2.5 px-4">Private Google Access</th>
                <th class="py-2.5 px-4">Security Perimeter</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-700">
              ${vpcs.map(v => `
                <tr class="hover:bg-slate-50 transition border-b border-slate-100">
                  <td class="py-3 px-4 font-mono font-bold text-slate-900">${v.room_id}</td>
                  <td class="py-3 px-4 font-mono text-slate-700">${v.network_name}</td>
                  <td class="py-3 px-4 font-mono text-slate-600"><span class="font-bold">${v.subnet_name}</span> (${v.ip_cidr_range})</td>
                  <td class="py-3 px-4 font-mono text-slate-600">me-west1 (Tel Aviv)</td>
                  <td class="py-3 px-4"><span class="inline-flex items-center gap-1 text-emerald-700 font-semibold"><i class="fa-solid fa-circle-check text-[10px]"></i> Enabled</span></td>
                  <td class="py-3 px-4"><span class="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">VPC-SC Enforced</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Link Bucket Modal -->
      <div id="modal-link-bucket" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden items-center justify-center p-4">
        <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-md w-full overflow-hidden p-6 space-y-4">
          <div class="flex items-center justify-between pb-3 border-b border-slate-200">
            <div class="font-extrabold text-slate-900 text-sm flex items-center gap-2"><i class="fa-solid fa-link text-blue-600"></i><span>Link Storage Bucket</span></div>
            <button id="btn-close-link-modal" class="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"><i class="fa-solid fa-xmark"></i></button>
          </div>
          <form id="form-link-bucket" class="space-y-3">
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Target Research Room</label>
              <select id="link-target-room" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium" required>
                <option value="rr-oncology-01">rr-oncology-01 (Oncology)</option>
                <option value="rr-genomics-02">rr-genomics-02 (Genomics)</option>
                <option value="rr-cardio-03">rr-cardio-03 (Cardiology)</option>
                <option value="rr-neurology-04">rr-neurology-04 (Neurology)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">GCS Bucket URI / Name</label>
              <input type="text" id="link-bucket-name" placeholder="gs://custom-cohort-bucket" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium" required />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-700 mb-1">Role / Access Type</label>
              <select id="link-role-type" class="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium">
                <option value="INBOUND">INBOUND (Read-only researcher data)</option>
                <option value="EXPORT">EXPORT (Quarantine & approved export sink)</option>
                <option value="REFERENCE">REFERENCE (Shared reference catalog)</option>
              </select>
            </div>
            <div class="pt-3 flex items-center justify-end gap-2 border-t border-slate-200">
              <button type="button" id="btn-cancel-link-modal" class="px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-100 cursor-pointer">Cancel</button>
              <button type="submit" class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow flex items-center gap-1.5 cursor-pointer"><i class="fa-solid fa-check"></i><span>Link Bucket</span></button>
            </div>
          </form>
        </div>
      </div>

    </div>
  `;

  attachEventHandlers(container, buckets);
}

function attachEventHandlers(container, buckets) {
  const modal = document.getElementById("modal-link-bucket");
  const openModal = () => { modal?.classList.remove("hidden"); modal?.classList.add("flex"); };
  const closeModal = () => { modal?.classList.add("hidden"); modal?.classList.remove("flex"); };

  document.getElementById("btn-open-link-bucket")?.addEventListener("click", openModal);
  document.getElementById("btn-close-link-modal")?.addEventListener("click", closeModal);
  document.getElementById("btn-cancel-link-modal")?.addEventListener("click", closeModal);

  document.getElementById("form-link-bucket")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const roomId = document.getElementById("link-target-room").value;
    let bName = document.getElementById("link-bucket-name").value.trim().replace(/^gs:\/\//, '').replace(/\/$/, '');
    const roleType = document.getElementById("link-role-type").value;

    stateStore.showToast(`Linking bucket gs://${bName} to ${roomId}...`, "info");
    try {
      const res = await api.linkBucket(roomId, bName, roleType);
      stateStore.showToast(res.message || "Bucket linked successfully", "success");
      closeModal();
      renderResourcesView();
    } catch (err) {
      stateStore.showToast(`Failed to link bucket: ${err.message}`, "error");
    }
  });

  container.querySelectorAll(".btn-jump-room").forEach(btn => {
    btn.addEventListener("click", () => {
      const roomId = btn.getAttribute("data-room");
      if (roomId) stateStore.setView("room-detail", roomId);
    });
  });

  container.querySelectorAll(".btn-detach-bucket").forEach(btn => {
    btn.addEventListener("click", async () => {
      const roomId = btn.getAttribute("data-room");
      const bucketName = btn.getAttribute("data-bucket");
      if (!roomId || !bucketName) return;
      if (!confirm(`Are you sure you want to detach bucket 'gs://${bucketName}' from research room '${roomId}'?`)) return;

      stateStore.showToast(`Detaching bucket gs://${bucketName}...`, "info");
      try {
        const res = await api.detachBucket(roomId, bucketName);
        stateStore.showToast(res.message || "Bucket detached successfully", "success");
        renderResourcesView();
      } catch (err) {
        stateStore.showToast(`Failed to detach bucket: ${err.message}`, "error");
      }
    });
  });
}
