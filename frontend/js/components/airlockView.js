/**
 * Airlock Data Egress Governance & Gemini Risk Scanner View
 * Displays candidate export files across research rooms with Gemini AI privacy risk score, PII tokens, and approval actions.
 */

import { api } from '../api.js';
import { formatBytes, formatDateTime } from '../config.js';

export async function renderAirlockView() {
  const container = document.getElementById("view-airlock");
  if (!container) return;

  container.innerHTML = `
    <div class="space-y-6 animate-pulse">
      <div class="h-8 bg-slate-200 rounded w-1/4"></div>
      <div class="h-32 bg-slate-200 rounded-xl"></div>
      <div class="h-64 bg-slate-200 rounded-xl"></div>
    </div>
  `;

  try {
    const candidates = await api.getAirlockCandidates();
    renderAirlockContent(container, candidates);
  } catch (err) {
    container.innerHTML = `
      <div class="p-8 bg-white rounded-xl border border-rose-200 text-center">
        <h3 class="text-base font-bold text-slate-800">Failed to Load Airlock Candidates</h3>
        <p class="text-xs text-slate-500 mt-1">${err.message}</p>
      </div>
    `;
  }
}

export function renderAirlockContent(container, candidates = []) {
  const scannedCount = candidates.filter(c => c.status !== 'PENDING_SCAN').length;
  const approvedCount = candidates.filter(c => c.status === 'APPROVED').length;
  const flaggedCount = candidates.filter(c => c.status === 'FLAGGED' || (c.risk_score && c.risk_score > 30 && c.status !== 'APPROVED')).length;
  const pendingCount = candidates.filter(c => c.status === 'PENDING_SCAN').length;

  container.innerHTML = `
    <div class="space-y-6">
      
      <!-- Top Title & Stats Banner -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2.5">
            <span class="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center text-sm shadow-sm">
              <i class="fa-solid fa-shield-virus"></i>
            </span>
            Airlock Data Egress Governance
          </h1>
          <p class="text-xs text-slate-500 mt-1">
            Automated Gemini AI privacy auditing, HIPAA Safe Harbor verification, and PII token detection for candidate data exports.
          </p>
        </div>

        <button id="btn-refresh-airlock" class="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-xl shadow-sm transition flex items-center gap-2">
          <i class="fa-solid fa-arrows-rotate text-xs"></i>
          <span>Refresh Egress Queue</span>
        </button>
      </div>

      <!-- Metric Cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-file-export"></i>
          </div>
          <div>
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Candidate Files</div>
            <div class="text-xl font-black text-slate-900 font-mono">${candidates.length}</div>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-circle-check"></i>
          </div>
          <div>
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Approved / Safe</div>
            <div class="text-xl font-black text-emerald-600 font-mono">${approvedCount}</div>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-triangle-exclamation"></i>
          </div>
          <div>
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Flagged for Review</div>
            <div class="text-xl font-black text-amber-600 font-mono">${flaggedCount}</div>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center text-lg shrink-0">
            <i class="fa-solid fa-wand-magic-sparkles"></i>
          </div>
          <div>
            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Pending Gemini Scan</div>
            <div class="text-xl font-black text-purple-600 font-mono">${pendingCount}</div>
          </div>
        </div>
      </div>

      <!-- Candidate Files Data Table -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 class="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <i class="fa-solid fa-list-check text-indigo-600"></i>
            <span>Candidate Data Exports</span>
          </h2>
          <span class="text-xs text-slate-500 font-medium">Staged in spoke export buckets (<code class="font-mono text-indigo-600">gs://rr-*-export/</code>)</span>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse min-w-[900px]">
            <thead class="bg-slate-50 border-b border-slate-200 text-slate-600 font-bold text-[11px] uppercase tracking-wider">
              <tr>
                <th class="py-3 px-4">Research Room</th>
                <th class="py-3 px-4">Export File / Bucket</th>
                <th class="py-3 px-4">Researcher</th>
                <th class="py-3 px-3 text-center">Gemini Risk Rating</th>
                <th class="py-3 px-3 text-center">Status</th>
                <th class="py-3 px-4 text-center">Actions</th>
                <th class="py-3 px-3 text-center">Details</th>
              </tr>
            </thead>
            <tbody id="airlock-table-body" class="divide-y divide-slate-200 text-xs text-slate-700">
              ${candidates.length === 0 ? `
                <tr>
                  <td colspan="7" class="py-12 text-center text-slate-400">
                    <i class="fa-solid fa-folder-open text-3xl mb-3 text-slate-300"></i>
                    <p class="font-semibold text-slate-600">No candidate export files found</p>
                  </td>
                </tr>
              ` : candidates.map((c, idx) => {
                const score = c.risk_score !== null && c.risk_score !== undefined ? c.risk_score : null;
                const scoreBadgeClass = score === null ? 'bg-slate-100 text-slate-500' :
                  score > 70 ? 'bg-rose-100 text-rose-800 border border-rose-300' :
                  score > 30 ? 'bg-amber-100 text-amber-800 border border-amber-300' :
                  'bg-emerald-100 text-emerald-800 border border-emerald-300';
                
                const piiList = c.pii_tokens_detected || [];
                const findingsList = c.findings || [];
                const isApproved = c.status === 'APPROVED';
                const isRejected = c.status === 'REJECTED';
                const rowId = `airlock-row-${idx}`;
                const detailId = `airlock-detail-${idx}`;
                const chevronId = `airlock-chevron-${idx}`;

                return `
                  <tr class="hover:bg-blue-50/40 transition cursor-pointer airlock-master-row" data-detail-id="${detailId}" data-chevron-id="${chevronId}">
                    <!-- Room ID -->
                    <td class="py-3.5 px-4 font-mono font-bold text-slate-900 whitespace-nowrap">
                      <span class="text-blue-600">${c.room_id}</span>
                    </td>

                    <!-- File & Bucket -->
                    <td class="py-3.5 px-4">
                      <div class="font-bold text-slate-900 font-mono text-[11px] truncate max-w-[280px]" title="${c.file_name}">${c.file_name}</div>
                      <div class="text-[10px] text-slate-400 font-mono">gs://${c.bucket_name} • ${formatBytes(c.file_size_bytes)}</div>
                    </td>

                    <!-- Researcher -->
                    <td class="py-3.5 px-4 font-mono text-[11px] text-slate-600 whitespace-nowrap">
                      ${c.researcher_email || '—'}
                    </td>

                    <!-- Risk Rating -->
                    <td class="py-3.5 px-3 text-center whitespace-nowrap">
                      ${score !== null ? `
                        <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold font-mono ${scoreBadgeClass}">
                          <span>${score} / 100</span>
                          <span class="text-[9px] uppercase tracking-wider">(${c.risk_level || 'EVAL'})</span>
                        </div>
                      ` : `
                        <span class="text-slate-400 text-[11px] italic">Pending Scan</span>
                      `}
                    </td>

                    <!-- Status -->
                    <td class="py-3.5 px-3 text-center whitespace-nowrap">
                      <span class="px-2 py-0.5 rounded text-[11px] font-bold ${
                        isApproved ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' :
                        isRejected ? 'bg-rose-100 text-rose-800 border border-rose-200' :
                        'bg-amber-100 text-amber-800 border border-amber-200'
                      }">
                        ${c.status}
                      </span>
                    </td>

                    <!-- Actions -->
                    <td class="py-3.5 px-4 text-center whitespace-nowrap" onclick="event.stopPropagation();">
                      <div class="flex items-center justify-center gap-1.5">
                        <button class="btn-airlock-scan px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition cursor-pointer flex items-center gap-1" data-room-id="${c.room_id}" data-file-name="${c.file_name}" title="Scan with Gemini AI">
                          <i class="fa-solid fa-wand-magic-sparkles text-[10px]"></i>
                          <span>Scan</span>
                        </button>
                        ${!isApproved ? `
                          <button class="btn-airlock-approve px-2 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition cursor-pointer" data-room-id="${c.room_id}" data-file-name="${c.file_name}" title="Approve Export">
                            <i class="fa-solid fa-check text-[10px]"></i>
                          </button>
                        ` : ''}
                        ${!isRejected ? `
                          <button class="btn-airlock-reject px-2 py-1.5 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition cursor-pointer" data-room-id="${c.room_id}" data-file-name="${c.file_name}" title="Reject Export">
                            <i class="fa-solid fa-xmark text-[10px]"></i>
                          </button>
                        ` : ''}
                      </div>
                    </td>

                    <!-- Details Expand Chevron -->
                    <td class="py-3.5 px-3 text-center text-slate-400">
                      <i id="${chevronId}" class="fa-solid fa-chevron-down text-xs transition-transform transform"></i>
                    </td>
                  </tr>

                  <!-- Expandable Scan Details Drawer -->
                  <tr id="${detailId}" class="hidden bg-slate-50 border-b border-slate-200">
                    <td colspan="7" class="p-5">
                      <div class="space-y-4 max-w-4xl">
                        
                        <!-- Header with Status & Score -->
                        <div class="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200">
                          <div>
                            <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Airlock Privacy Evaluation</div>
                            <div class="font-bold text-slate-900 text-sm mt-0.5 font-mono">${c.file_name}</div>
                            <div class="text-[11px] text-slate-500 font-mono mt-0.5">Bucket: gs://${c.bucket_name} • Scanned: ${c.scanned_at ? formatDateTime(c.scanned_at) : 'Pending Scan'}</div>
                          </div>
                          <div class="flex items-center gap-3">
                            ${score !== null ? `
                              <div class="text-right">
                                <div class="text-[10px] font-bold text-slate-400 uppercase">Risk Level</div>
                                <div class="text-xs font-extrabold ${score > 70 ? 'text-rose-600' : score > 30 ? 'text-amber-600' : 'text-emerald-600'} font-mono">${score}/100 (${c.risk_level || 'EVAL'})</div>
                              </div>
                            ` : ''}
                            <span class="px-2.5 py-1 rounded-lg text-xs font-bold ${
                              isApproved ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' :
                              isRejected ? 'bg-rose-100 text-rose-800 border border-rose-300' :
                              'bg-amber-100 text-amber-800 border border-amber-300'
                            }">${c.status}</span>
                          </div>
                        </div>

                        <!-- Scan Rationale & Recommendation -->
                        <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                          <div class="flex items-center justify-between">
                            <span class="text-[11px] font-bold text-slate-700 uppercase flex items-center gap-1.5">
                              <i class="fa-solid fa-wand-magic-sparkles text-indigo-500"></i>
                              <span>Gemini Decision Rationale & Recommendation</span>
                            </span>
                            ${c.recommendation ? `
                              <span class="px-2 py-0.5 rounded text-[10px] font-bold ${c.recommendation === 'APPROVE' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'} font-mono">
                                Policy: ${c.recommendation}
                              </span>
                            ` : ''}
                          </div>
                          <p class="text-xs text-slate-600 leading-relaxed font-mono">
                            ${c.reason || (score !== null ? 'Automated privacy assessment completed with no blocking policy violations.' : 'File has not been evaluated yet. Click "Scan" to trigger an automated Gemini AI inspection.')}
                          </p>
                        </div>

                        <!-- PII Tokens & K-Anonymity Grid -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                          
                          <!-- Detected PII Tokens -->
                          <div class="bg-white p-3.5 rounded-xl border border-slate-200 space-y-2">
                            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Detected PII / Direct Identifiers</span>
                            ${piiList.length > 0 ? `
                              <div class="flex flex-wrap gap-1.5">
                                ${piiList.map(t => `<span class="px-2 py-1 rounded bg-rose-50 text-rose-700 border border-rose-200 text-xs font-mono font-bold flex items-center gap-1"><i class="fa-solid fa-triangle-exclamation text-[10px]"></i> ${t}</span>`).join('')}
                              </div>
                            ` : `
                              <div class="text-xs text-emerald-700 font-semibold flex items-center gap-1.5 bg-emerald-50/60 border border-emerald-200/80 p-2 rounded-lg">
                                <i class="fa-solid fa-circle-check text-emerald-600"></i>
                                <span>Zero PII / direct identifiers detected in dataset sample.</span>
                              </div>
                            `}
                          </div>

                          <!-- K-Anonymity Violations -->
                          <div class="bg-white p-3.5 rounded-xl border border-slate-200 space-y-2">
                            <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">K-Anonymity & Cell Suppression (k ≥ 5)</span>
                            ${c.k_anonymity_violation ? `
                              <div class="text-xs text-rose-700 font-semibold flex items-center gap-1.5 bg-rose-50/60 border border-rose-200/80 p-2 rounded-lg font-mono">
                                <i class="fa-solid fa-ban text-rose-600"></i>
                                <span>Small cell count detected (k &lt; 5 violation, re-identification risk).</span>
                              </div>
                            ` : `
                              <div class="text-xs text-emerald-700 font-semibold flex items-center gap-1.5 bg-emerald-50/60 border border-emerald-200/80 p-2 rounded-lg">
                                <i class="fa-solid fa-circle-check text-emerald-600"></i>
                                <span>Aggregated group sizes satisfy k-anonymity (k ≥ 5).</span>
                              </div>
                            `}
                          </div>
                        </div>

                        <!-- Findings List -->
                        <div class="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                          <span class="text-[11px] font-bold text-slate-700 uppercase flex items-center gap-1.5">
                            <i class="fa-solid fa-clipboard-list text-slate-400"></i>
                            <span>Detailed Privacy Findings (${findingsList.length})</span>
                          </span>
                          ${findingsList.length > 0 ? `
                            <ul class="space-y-1 text-xs text-slate-600 font-mono">
                              ${findingsList.map(f => `
                                <li class="flex items-start gap-2 p-1.5 rounded hover:bg-slate-50">
                                  <i class="fa-solid fa-circle-dot text-[8px] text-indigo-500 mt-1 shrink-0"></i>
                                  <span>${f}</span>
                                </li>
                              `).join('')}
                            </ul>
                          ` : `
                            <div class="text-xs text-slate-500 font-mono p-2 bg-slate-50 rounded-lg">No findings or issues reported.</div>
                          `}
                        </div>

                      </div>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  `;

  // Attach event listeners
  document.getElementById("btn-refresh-airlock")?.addEventListener("click", () => renderAirlockView());

  container.querySelectorAll(".airlock-master-row").forEach(row => {
    row.addEventListener("click", () => {
      const detailId = row.getAttribute("data-detail-id");
      const chevronId = row.getAttribute("data-chevron-id");
      const detail = document.getElementById(detailId);
      const chevron = document.getElementById(chevronId);
      if (!detail) return;
      const isHidden = detail.classList.contains("hidden");
      detail.classList.toggle("hidden");
      chevron?.classList.toggle("rotate-180", isHidden);
    });
  });

  container.querySelectorAll(".btn-airlock-scan").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const rId = b.getAttribute("data-room-id");
      const fName = b.getAttribute("data-file-name");
      b.disabled = true;
      b.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-[10px]"></i> Scanning...`;
      try {
        const scanRes = await api.scanAirlockFile(rId, fName);
        renderAirlockView();
      } catch (err) {
        alert(`Scan failed: ${err.message}`);
        b.disabled = false;
        b.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles text-[10px]"></i> <span>Scan</span>`;
      }
    });
  });

  container.querySelectorAll(".btn-airlock-approve").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const rId = b.getAttribute("data-room-id");
      const fName = b.getAttribute("data-file-name");
      try {
        await api.takeAirlockAction(rId, fName, "APPROVE");
        renderAirlockView();
      } catch (err) {
        alert(`Failed to approve: ${err.message}`);
      }
    });
  });

  container.querySelectorAll(".btn-airlock-reject").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const b = e.currentTarget;
      const rId = b.getAttribute("data-room-id");
      const fName = b.getAttribute("data-file-name");
      try {
        await api.takeAirlockAction(rId, fName, "REJECT");
        renderAirlockView();
      } catch (err) {
        alert(`Failed to reject: ${err.message}`);
      }
    });
  });
}
