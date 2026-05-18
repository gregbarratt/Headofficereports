const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const TOKEN_STORAGE_KEY = "head_office_reporting_token";

async function apiRequest(path, options = {}) {
  const { token, ...fetchOptions } = options;
  const isFormData = fetchOptions.body instanceof FormData;
  const headers = {
    ...(fetchOptions.body && !isFormData ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...fetchOptions.headers,
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json();
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

export async function getBankTransactions(token) {
  return apiRequest("/api/bank-transactions", { token });
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

export async function getBookings(token) {
  return apiRequest("/api/bookings", { token });
}

export async function getCustomerPayments(token) {
  return apiRequest("/api/customer-payments", { token });
}

export async function getSupplierPayments(token) {
  return apiRequest("/api/supplier-payments", { token });
}

export async function getTrustReconciliation(token) {
  return apiRequest("/api/trust-reconciliation", { token });
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
