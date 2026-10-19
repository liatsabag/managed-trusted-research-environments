/**
 * Helper Card Templates for Room Details View
 * Clean enterprise lists, researcher roster table, audit event stream, and quarantine export queue
 */

import { formatUSD, formatBytes, formatDateTime } from '../config.js';

export function renderBigQueryCard(room, metadata) {
  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-database text-purple-600"></i>
          <span>BigQuery Datasets</span>
        </h2>
        <span class="text-xs font-mono font-semibold px-2 py-0.5 bg-purple-50 text-purple-700 rounded">${room.local_dataset_id}</span>
      </div>

      <!-- Local Dataset Table -->
      <div class="space-y-1.5">
        <div class="text-xs font-bold text-slate-700 font-mono">${room.local_dataset_id}</div>
        <div class="border border-slate-200 rounded-lg overflow-hidden text-xs">
          <table class="w-full text-left border-collapse">
            <thead class="bg-slate-50 text-slate-500 font-semibold text-[10px] uppercase">
              <tr>
                <th class="py-2 px-3">Table Name</th>
                <th class="py-2 px-3 text-right">Type</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
              ${metadata.tables.map(tbl => `
                <tr class="hover:bg-slate-50 transition">
                  <td class="py-2 px-3 font-bold text-slate-900 flex items-center gap-2">
                    <i class="fa-solid fa-table text-purple-500 text-xs"></i>
                    <span>${tbl}</span>
                  </td>
                  <td class="py-2 px-3 text-right text-slate-500">Native Table</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Shared Hub Datasets -->
      <div class="space-y-1.5 pt-2">
        <div class="text-xs font-bold text-slate-700 font-mono">Shared Reference Datasets</div>
        <div class="border border-slate-200 rounded-lg overflow-hidden text-xs">
          <table class="w-full text-left border-collapse">
            <thead class="bg-slate-50 text-slate-500 font-semibold text-[10px] uppercase">
              <tr>
                <th class="py-2 px-3">Shared Dataset</th>
                <th class="py-2 px-3 text-right">Referenced Tables</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
              <tr>
                <td class="py-2 px-3 font-bold text-slate-900">hub_clinical_omop</td>
                <td class="py-2 px-3 text-right text-slate-600">person, condition_occurrence, measurement</td>
              </tr>
              <tr>
                <td class="py-2 px-3 font-bold text-slate-900">hub_imaging_dicom</td>
                <td class="py-2 px-3 text-right text-slate-600">dicom_studies, series_metadata</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

export function renderResearchersRosterCard(room, activity) {
  const researchers = room.researchers || [];
  const audits = activity?.recent_audit_events || [];

  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4 w-full">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-user-doctor text-indigo-600"></i>
          <span>Authorized Researchers</span>
        </h2>
        <span class="text-xs font-mono font-semibold px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded">${researchers.length} Authorized</span>
      </div>

      <div class="border border-slate-200 rounded-lg overflow-x-auto text-xs">
        <table class="w-full text-left border-collapse min-w-[650px]">
          <thead class="bg-slate-50 text-slate-500 font-semibold text-[10px] uppercase">
            <tr>
              <th class="py-2.5 px-3">Name</th>
              <th class="py-2.5 px-3">Title / Role</th>
              <th class="py-2.5 px-3">Institutional Email</th>
              <th class="py-2.5 px-4 text-right min-w-[170px]">Last Active</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 font-mono text-[11px]">
            ${researchers.map(r => {
              const fullName = `Dr. ${r.first_name || ''} ${r.last_name || ''}`.trim();
              const userAudit = audits.find(a => a.principal_email === r.primary_email);
              const lastActive = r.last_activity_at ? formatDateTime(r.last_activity_at) : (userAudit ? formatDateTime(userAudit.timestamp) : 'Active Today');

              return `
                <tr class="hover:bg-slate-50 transition">
                  <td class="py-2.5 px-3 font-bold text-slate-900 whitespace-nowrap">${fullName}</td>
                  <td class="py-2.5 px-3 text-slate-600 font-sans whitespace-nowrap">${r.role || 'Investigator'}</td>
                  <td class="py-2.5 px-3 text-blue-600 whitespace-nowrap">${r.primary_email}</td>
                  <td class="py-2.5 px-4 text-right text-slate-600 whitespace-nowrap font-medium">${lastActive}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

export function renderStorageCard(metadata, inventory) {
  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-bucket text-blue-600"></i>
          <span>Cloud Storage Buckets & File Inventory</span>
        </h2>
      </div>
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <span class="font-semibold text-slate-700">Inbound GCS Bucket (Ingest):</span>
          <span class="font-mono text-[11px] text-slate-500">${formatBytes(inventory?.inbound_bytes || 0)}</span>
        </div>
        <div class="divide-y divide-slate-100 border border-slate-200 rounded-lg text-xs">
          ${metadata.inbound_files.map(f => `
            <div class="p-2.5 flex items-center justify-between gap-2 hover:bg-slate-50 transition">
              <div class="flex items-center gap-2 truncate">
                <i class="fa-solid fa-file-csv text-blue-500 text-xs"></i>
                <span class="font-mono font-medium text-slate-800 truncate">${f.name}</span>
              </div>
              <span class="font-mono text-slate-500 text-[11px]">${formatBytes(f.size)}</span>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="space-y-2 pt-2">
        <div class="flex items-center justify-between text-xs">
          <span class="font-semibold text-slate-700">Export Quarantine Bucket (Air-Lock):</span>
          <span class="font-mono text-[11px] text-slate-500">${formatBytes(inventory?.export_bytes || 0)}</span>
        </div>
        <div class="divide-y divide-slate-100 border border-slate-200 rounded-lg text-xs">
          ${metadata.export_files.map(f => `
            <div class="p-2.5 flex items-center justify-between gap-2 hover:bg-slate-50 transition">
              <div class="flex items-center gap-2 truncate">
                <i class="fa-solid fa-file-export text-emerald-500 text-xs"></i>
                <span class="font-mono font-medium text-slate-800 truncate">${f.name}</span>
              </div>
              <span class="font-mono text-slate-500 text-[11px]">${formatBytes(f.size)}</span>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

export function renderNotebooksCard(room, metadata) {
  const compute = metadata.compute_machine || {
    type: "e2-standard-4",
    specs: "4 vCPUs, 16 GB RAM",
    runtime: "Colab Enterprise Runtime"
  };

  const totalRuns = metadata.notebooks.reduce((acc, nb) => acc + (nb.runs || 5), 0);

  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-book-bookmark text-emerald-600"></i>
          <span>Notebooks & Execution Environment</span>
        </h2>
        <span class="text-xs font-mono text-emerald-700 font-semibold">${metadata.notebooks.length} Notebooks (${totalRuns} Runs)</span>
      </div>

      <!-- Execution Compute Machine -->
      <div class="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1">
        <div class="flex items-center justify-between">
          <span class="font-bold text-slate-800 flex items-center gap-1.5">
            <i class="fa-solid fa-server text-blue-600 text-xs"></i>
            <span>${compute.runtime}</span>
          </span>
          <span class="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-mono text-[10px] font-bold">${compute.type}</span>
        </div>
        <div class="text-[11px] text-slate-500 font-mono">${compute.specs} • Interactive GPU/CPU Gateway</div>
      </div>

      <!-- Assigned Notebooks List -->
      <div class="space-y-2 text-xs">
        ${metadata.notebooks.map(nb => `
          <div class="p-2.5 rounded-lg border border-slate-200 hover:border-emerald-400 bg-slate-50/50 transition flex items-center justify-between gap-3">
            <div class="overflow-hidden">
              <div class="font-bold text-slate-900 font-mono flex items-center gap-2">
                <i class="fa-solid fa-book-open text-emerald-600 text-xs"></i>
                <span class="truncate">${nb.name}</span>
              </div>
              <div class="text-[11px] text-slate-500 mt-0.5">${nb.desc}</div>
            </div>
            <div class="flex items-center gap-2">
              <span class="font-mono text-[10px] text-slate-500">${nb.runs || 5} runs</span>
              <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${nb.status === 'Executed' ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-slate-200 text-slate-700'}">
                ${nb.status}
              </span>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Merged Pre-installed Packages Section -->
      <div class="pt-2 border-t border-slate-100 space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
            <i class="fa-solid fa-cubes text-cyan-600 text-xs"></i>
            <span>Pre-installed Packages</span>
          </span>
          <span class="text-[11px] font-mono text-slate-400">${room.packages?.length || 0} libraries</span>
        </div>
        <div class="flex flex-wrap gap-1.5 text-xs font-mono">
          ${(room.packages || []).map(p => `
            <span class="px-2 py-0.5 rounded bg-cyan-50 border border-cyan-200 text-cyan-900 text-[11px] flex items-center gap-1">
              <span class="font-semibold">${p.package_name}</span>
              <span class="text-cyan-600 text-[9px]">v${p.package_version}</span>
            </span>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

export function renderAuditEventStreamCard(activity) {
  const allAudits = activity?.recent_audit_events || [];
  // Filter for researcher activity (exclude automated service accounts / system noise)
  const researcherAudits = allAudits.filter(a => {
    const email = (a.principal_email || '').toLowerCase();
    return !email.includes('gserviceaccount.com') && 
           !email.includes('cloudservices') && 
           !email.includes('gcp-sa-');
  });

  const audits = researcherAudits.length > 0 ? researcherAudits : allAudits;

  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4 w-full">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-shield-halved text-indigo-600"></i>
          <span>Live Audit Events Stream</span>
        </h2>
        <span class="text-xs font-mono font-semibold px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded">${audits.length} Loaded Events</span>
      </div>
      <div class="divide-y divide-slate-100 text-xs max-h-72 overflow-y-auto">
        ${audits.length === 0 ? '<div class="p-4 text-center text-slate-400">No recent researcher events.</div>' : audits.map(a => `
          <div class="py-2.5 space-y-1">
            <div class="flex items-center justify-between text-[11px]">
              <span class="font-mono text-slate-800 font-semibold truncate">${a.principal_email}</span>
              <span class="text-slate-400 text-[10px] font-mono">${formatDateTime(a.timestamp)}</span>
            </div>
            <div class="text-[11px] text-slate-600">${a.description || a.method_name}</div>
            <div class="flex items-center gap-2 text-[10px] font-mono text-slate-500">
              <span class="text-indigo-600 font-semibold">${a.service_name}</span>
              <span>•</span>
              <span class="px-1.5 py-0.2 rounded bg-slate-100 text-slate-700">${a.category || 'DATA_ACCESS'}</span>
              <span>•</span>
              <span class="text-emerald-600 font-semibold">${a.status}</span>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

export function renderExportQuarantineCard(room, metadata) {
  const exportFiles = metadata.export_files || [];
  return `
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-200">
        <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-shield-virus text-indigo-600"></i>
          <span>Airlock & Data Egress Quarantine</span>
        </h2>
        <span class="text-xs font-mono font-bold px-2 py-0.5 bg-indigo-50 text-indigo-800 border border-indigo-200 rounded">
          ${exportFiles.length} Staged Files
        </span>
      </div>
      <div class="space-y-2">
        <div class="divide-y divide-slate-100 border border-slate-200 rounded-lg text-xs">
          ${exportFiles.map(f => `
            <div class="p-3 flex items-center justify-between gap-3 hover:bg-slate-50 transition">
              <div class="overflow-hidden">
                <div class="font-mono font-bold text-slate-900 flex items-center gap-2">
                  <i class="fa-solid fa-file-csv text-indigo-500 text-xs"></i>
                  <span class="truncate">${f.name}</span>
                </div>
                <div class="text-[11px] text-slate-500 mt-0.5">${f.desc} • ${formatBytes(f.size)}</div>
              </div>
              <div class="flex items-center gap-2 whitespace-nowrap">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                  Pending Scan
                </span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}
