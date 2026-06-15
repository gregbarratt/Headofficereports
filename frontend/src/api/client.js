const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const TOKEN_STORAGE_KEY = "head_office_reporting_token";
const AUTH_EXPIRED_EVENT = "head-office-auth-expired";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function readableApiErrorDetail(detail, fallback) {
  if (!detail) {
    return fallback;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        const message = item?.msg || item?.message || JSON.stringify(item);
        return location ? `${location}: ${message}` : message;
      })
      .join(" ");
  }
  if (typeof detail === "object") {
    return detail.message || detail.msg || detail.error || JSON.stringify(detail);
  }
  return String(detail);
}

async function apiRequest(path, options = {}) {
  const { token, ...fetchOptions } = options;
  const isFormData = fetchOptions.body instanceof FormData;
  const headers = {
    ...(fetchOptions.body && !isFormData ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...fetchOptions.headers,
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      headers,
    });
  } catch {
    throw new ApiError(
      "The server did not respond. If you are syncing a large date range, use the background catch-up so the page does not time out.",
      0
    );
  }

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const error = await response.json();
      message = readableApiErrorDetail(error.detail || error.message || error, message);
    } catch {
      message = response.statusText || message;
    }
    handleAuthExpired(response.status, token, message);
    throw new ApiError(message, response.status);
  }

  return response.json();
}

function handleAuthExpired(status, token, message) {
  if (status !== 401 || !token) {
    return;
  }
  clearStoredToken();
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: { message } }));
}

export function onAuthExpired(callback) {
  window.addEventListener(AUTH_EXPIRED_EVENT, callback);
  return () => window.removeEventListener(AUTH_EXPIRED_EVENT, callback);
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export async function getApiHealth() {
  return apiRequest("/api/health");
}

export async function getAgentCommissions(token) {
  return apiRequest("/api/agent-commissions", { token });
}

export async function getBankTransactions(token) {
  return apiRequest("/api/bank-transactions", { token });
}

export async function getHeadOfficeCosts(token) {
  return apiRequest("/api/bank-transactions/head-office-costs", { token });
}

export async function allocateBankTransaction({ token, transactionId, bookingRef, allocationType }) {
  return apiRequest(`/api/bank-transactions/${transactionId}/allocate`, {
    method: "PUT",
    token,
    body: JSON.stringify({ booking_ref: bookingRef, allocation_type: allocationType }),
  });
}

export async function createManualTrustBalance({ token, trustValue, balanceDate, checkedAt, note }) {
  return apiRequest("/api/bank-transactions/manual-trust-balance", {
    method: "POST",
    token,
    body: JSON.stringify({
      trust_value: trustValue,
      balance_date: balanceDate,
      checked_at: checkedAt,
      note,
    }),
  });
}

export async function loginSuperAdmin({ email, password }) {
  return apiRequest("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getCurrentUser(token) {
  return apiRequest("/api/auth/me", { token });
}

export async function logoutSuperAdmin(token) {
  return apiRequest("/api/auth/logout", {
    method: "POST",
    token,
  });
}

export async function getDashboardStatus(token) {
  return apiRequest("/api/dashboard/status", { token });
}

export async function getRefunds(token) {
  return apiRequest("/api/refunds", { token });
}

export async function getEmailRecipients(token) {
  return apiRequest("/api/email-recipients", { token });
}

export async function getInsuranceCosts(token) {
  return apiRequest("/api/insurance-costs", { token });
}

export async function getOtcCrmComparisons(token, filters = {}) {
  const query = new URLSearchParams({ limit: String(filters.limit || 2500) });
  if (filters.status && filters.status !== "all") {
    query.set("status", filters.status);
  }
  if (filters.search?.trim()) {
    query.set("search", filters.search.trim());
  }
  return apiRequest(`/api/otc-crm?${query.toString()}`, { token });
}

export async function createEmailRecipient({ token, email, name }) {
  return apiRequest("/api/email-recipients", {
    method: "POST",
    token,
    body: JSON.stringify({ email, name }),
  });
}

export async function updateEmailRecipient({ token, recipientId, name, isActive }) {
  return apiRequest(`/api/email-recipients/${recipientId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ name, is_active: isActive }),
  });
}

export async function sendWeeklyEmail(token) {
  return apiRequest("/api/weekly-email/send", {
    method: "POST",
    token,
  });
}

export async function getReportTypes(token) {
  return apiRequest("/api/reports/types", { token });
}

export async function getReportRuns(token) {
  return apiRequest("/api/reports/runs", { token });
}

export async function getBookings(token, limit = 10000) {
  const query = new URLSearchParams({ limit: String(limit) });
  return apiRequest(`/api/bookings?${query.toString()}`, { token });
}

export async function getBookingChecks(token, filters = {}) {
  const query = new URLSearchParams();
  if (filters.limit) {
    query.set("limit", String(filters.limit));
  }
  if (filters.search?.trim()) {
    query.set("search", filters.search.trim());
  }
  if (filters.review && filters.review !== "all") {
    query.set("review", filters.review);
  }
  if (filters.company && filters.company !== "all") {
    query.set("company", filters.company);
  }
  if (filters.supplier && filters.supplier !== "all") {
    query.set("supplier", filters.supplier);
  }
  if (filters.customer && filters.customer !== "all") {
    query.set("customer", filters.customer);
  }
  if (filters.archive && filters.archive !== "active") {
    query.set("archive", filters.archive);
  }
  if (filters.commissionReview && filters.commissionReview !== "all") {
    query.set("commission_review", filters.commissionReview);
  }
  if (filters.departureFrom) {
    query.set("departure_from", filters.departureFrom);
  }
  if (filters.departureTo) {
    query.set("departure_to", filters.departureTo);
  }
  return apiRequest(`/api/bookings/checks${query.toString() ? `?${query.toString()}` : ""}`, { token });
}

export async function updateBookingCheckAdjustments({ token, bookingRef, adjustments }) {
  return apiRequest(`/api/bookings/checks/${encodeURIComponent(bookingRef)}/adjustments`, {
    method: "PUT",
    token,
    body: JSON.stringify(adjustments),
  });
}

export async function updateBookingArchiveStatus({ token, bookingRef, values }) {
  return apiRequest(`/api/bookings/checks/${encodeURIComponent(bookingRef)}/archive`, {
    method: "PATCH",
    token,
    body: JSON.stringify(values),
  });
}

export async function refreshTraveltekBooking({ token, bookingRef }) {
  return apiRequest(`/api/traveltek/bookings/${encodeURIComponent(bookingRef)}/refresh`, {
    method: "POST",
    token,
  });
}

export async function getCustomerPayments(token, filters = {}) {
  const query = new URLSearchParams({ limit: String(filters.limit || 1000) });
  if (filters.source && filters.source !== "all") {
    query.set("source", filters.source);
  }
  if (filters.search?.trim()) {
    query.set("search", filters.search.trim());
  }
  return apiRequest(`/api/customer-payments?${query.toString()}`, { token });
}

export async function syncFellohCustomerPayments({ token, startDate, endDate }) {
  return apiRequest("/api/customer-payments/sync-felloh", {
    method: "POST",
    token,
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  });
}

export async function startFellohCustomerPaymentBackfill({ token, startDate, endDate, chunkDays = 14 }) {
  return apiRequest("/api/customer-payments/sync-felloh-backfill", {
    method: "POST",
    token,
    body: JSON.stringify({ start_date: startDate, end_date: endDate, chunk_days: chunkDays }),
  });
}

export async function getExceptions(token, filters = {}) {
  const search = new URLSearchParams();
  if (filters.status && filters.status !== "all") {
    search.set("status", filters.status);
  }
  if (filters.severity && filters.severity !== "all") {
    search.set("severity", filters.severity);
  }
  const query = search.toString();
  return apiRequest(`/api/exceptions${query ? `?${query}` : ""}`, { token });
}

export async function generateExceptions(token) {
  return apiRequest("/api/exceptions/generate", {
    method: "POST",
    token,
  });
}

export async function getSupplierPayments(token, search = "", source = "all", match = "all") {
  const query = new URLSearchParams();
  if (search.trim()) {
    query.set("search", search.trim());
  }
  if (source && source !== "all") {
    query.set("source", source);
  }
  if (match && match !== "all") {
    query.set("match", match);
  }
  return apiRequest(`/api/supplier-payments${query.toString() ? `?${query.toString()}` : ""}`, { token });
}

export async function allocateSupplierPayment(token, paymentId, bookingRef) {
  return apiRequest(`/api/supplier-payments/${paymentId}/allocate`, {
    body: JSON.stringify({ booking_ref: bookingRef }),
    method: "PUT",
    token,
  });
}

export async function getSettingsStatus(token) {
  return apiRequest("/api/settings/status", { token });
}

export async function getTrustReconciliation(token) {
  return apiRequest("/api/trust-reconciliation", { token });
}

export async function getTraveltekUpdates(token, status = "open") {
  const query = new URLSearchParams();
  if (status && status !== "open") {
    query.set("status", status);
  }
  return apiRequest(`/api/traveltek/updates${query.toString() ? `?${query.toString()}` : ""}`, { token });
}

export async function getTraveltekChangeLog(token, changeType = "all", limit = 100) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (changeType && changeType !== "all") {
    query.set("change_type", changeType);
  }
  return apiRequest(`/api/traveltek/change-log?${query.toString()}`, { token });
}

export async function syncTraveltekActiveBookings({ token, limit }) {
  return apiRequest("/api/traveltek/sync-active-bookings", {
    method: "POST",
    token,
    body: JSON.stringify({ limit }),
  });
}

export async function importTraveltekBookings({ token, startDate, endDate, limit }) {
  return apiRequest("/api/traveltek/import-bookings", {
    method: "POST",
    token,
    body: JSON.stringify({ start_date: startDate, end_date: endDate, date_type: "booking_date", limit }),
  });
}

export async function runTraveltekFullCatchUpBatch({
  token,
  startDate,
  endDate,
  batchDays,
  limit,
  resetProgress,
}) {
  return apiRequest("/api/traveltek/full-catch-up/next-batch", {
    method: "POST",
    token,
    body: JSON.stringify({
      start_date: startDate,
      end_date: endDate,
      batch_days: batchDays,
      limit,
      reset_progress: resetProgress,
    }),
  });
}

export async function runTraveltekUpdateEverythingBatch({ token, limit, resetProgress }) {
  return apiRequest("/api/traveltek/update-everything/next-batch", {
    method: "POST",
    token,
    body: JSON.stringify({
      limit,
      reset_progress: resetProgress,
    }),
  });
}

export async function scanNewTraveltekOtcReferences({ token, maxReferences, stopAfterMissing }) {
  return apiRequest("/api/traveltek/scan-new-otc-references", {
    method: "POST",
    token,
    body: JSON.stringify({
      max_references: maxReferences,
      stop_after_missing: stopAfterMissing,
    }),
  });
}

export async function runTraveltekActiveMaintenance({
  token,
  newBookingStartDate,
  newBookingEndDate,
  newBookingLimit,
  refreshLimit,
  activeWindowDays,
}) {
  return apiRequest("/api/traveltek/active-maintenance", {
    method: "POST",
    token,
    body: JSON.stringify({
      new_booking_start_date: newBookingStartDate,
      new_booking_end_date: newBookingEndDate,
      new_booking_limit: newBookingLimit,
      refresh_limit: refreshLimit,
      active_window_days: activeWindowDays,
    }),
  });
}

export async function updateTraveltekUpdateStatus({ token, updateId, status }) {
  return apiRequest(`/api/traveltek/updates/${updateId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
  });
}

export async function getWeeklySnapshots(token) {
  return apiRequest("/api/weekly-snapshots", { token });
}

export async function generateWeeklySnapshot(token) {
  return apiRequest("/api/weekly-snapshots/generate", {
    method: "POST",
    token,
  });
}

export async function getUploadTypes(token) {
  return apiRequest("/api/uploads/types", { token });
}

export async function getUploadBatches(token) {
  return apiRequest("/api/uploads", { token });
}

export async function uploadBatch({ token, uploadType, file }) {
  const body = new FormData();
  body.append("upload_type", uploadType);
  body.append("file", file);

  return apiRequest("/api/uploads", {
    method: "POST",
    token,
    body,
  });
}

export async function updateExceptionStatus({ token, exceptionId, status }) {
  return apiRequest(`/api/exceptions/${exceptionId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
  });
}

export async function downloadReportExcel({ token, reportType }) {
  const response = await fetch(`${API_BASE_URL}/api/reports/${reportType}/excel`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    let message = "Report export failed.";
    try {
      const error = await response.json();
      message = readableApiErrorDetail(error.detail || error.message || error, message);
    } catch {
      message = response.statusText || message;
    }
    handleAuthExpired(response.status, token, message);
    throw new ApiError(message, response.status);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/);
  return {
    blob,
    filename: filenameMatch?.[1] || `${reportType}.xlsx`,
  };
}
