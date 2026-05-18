const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const TOKEN_STORAGE_KEY = "head_office_reporting_token";

async function apiRequest(path, options = {}) {
  const { token, ...fetchOptions } = options;
  const headers = {
    ...(fetchOptions.body ? { "Content-Type": "application/json" } : {}),
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
