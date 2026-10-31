/**
 * GCP Health Data Platform - Central Administrator Portal
 * Global Configuration and Formatter Utilities
 */

export const CONFIG = {
  APP_NAME: "GCP Health Data Platform",
  APP_SUBTITLE: "Central Administrator & Governance Portal",
  VERSION: "1.0.0",
  // Default API base URL (relative '/api/v1' routes through Nginx reverse proxy to Cloud Run backend)
  DEFAULT_API_BASE: "/api/v1",
  
  // Polling intervals in milliseconds
  POLL_INTERVAL: 30000,
  
  PERSONAS: {
    admin: {
      id: "admin",
      title: "Central Operations Admin",
      role: "Platform Operations & Fleet Governance",
      description: "Full visibility over room states, DUA lifecycles, and tenant onboarding.",
      badgeColor: "bg-blue-100 text-blue-800 border-blue-200",
      icon: "fa-shield-halved"
    },
    cloud: {
      id: "cloud",
      title: "Technical Cloud Administrator",
      role: "Infrastructure, BigQuery & Telemetry",
      description: "Observability over BigQuery queries, slot consumption, and FinOps reconciliation.",
      badgeColor: "bg-indigo-100 text-indigo-800 border-indigo-200",
      icon: "fa-server"
    },
    dpo: {
      id: "dpo",
      title: "Data Privacy Officer (DPO)",
      role: "Helsinki IRB & 5-Item Statutory Compliance",
      description: "Regulatory horizon tracking, Air-Lock audit feeds, and soft-downgrade enforcement.",
      badgeColor: "bg-emerald-100 text-emerald-800 border-emerald-200",
      icon: "fa-scale-balanced"
    }
  }
};

/**
 * Format currency in USD (Standardized 5-decimal precision for micro-cost billing telemetry)
 */
export function formatUSD(amount, minDecimals = 5, maxDecimals = 5) {
  if (amount === undefined || amount === null || isNaN(amount)) return "$0.00000";
  const num = Number(amount);
  if (num === 0) return "$0.00000";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: minDecimals,
    maximumFractionDigits: maxDecimals
  }).format(num);
}

/**
 * Format bytes to readable human unit (KB, MB, GB, TB, PB)
 */
export function formatBytes(bytes, decimals = 2) {
  if (bytes === 0 || !bytes || isNaN(bytes)) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

/**
 * Format slot milliseconds to slot hours or seconds
 */
export function formatSlotTime(slotMs) {
  if (!slotMs || isNaN(slotMs)) return "0 ms";
  if (slotMs < 1000) return `${slotMs} ms`;
  const seconds = slotMs / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = seconds / 60;
  if (minutes < 60) return `${minutes.toFixed(1)} m`;
  const hours = minutes / 60;
  return `${hours.toFixed(2)} slot-hrs`;
}

/**
 * Format ISO datetime string to clean localized string
 */
export function formatDateTime(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    });
  } catch (e) {
    return isoString;
  }
}

/**
 * Format date (YYYY-MM-DD)
 */
export function formatDate(dateString) {
  if (!dateString) return "—";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  } catch (e) {
    return dateString;
  }
}
