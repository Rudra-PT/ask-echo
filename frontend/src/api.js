/**
 * frontend/src/api.js
 * ────────────────────
 * HTTP API client for Ask-Echo backend services.
 */

const BASE = import.meta.env.VITE_API_BASE ?? 'https://ask-echo-backend.onrender.com';

let _authToken = null;

export function setAuthToken(token) {
  _authToken = token;
}

export function clearAuthToken() {
  _authToken = null;
}

export function isAuthenticated() {
  return Boolean(_authToken);
}

function authHeaders() {
  if (!_authToken) {
    throw new Error('Not authenticated. Please sign in with Google.');
  }
  return { Authorization: `Bearer ${_authToken}` };
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('namespace', 'user_scoped');

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Upload failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;
}

export async function queryDocuments(query) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ query }),
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Query failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;
}

export async function clearSession() {
  const res = await fetch(`${BASE}/upload/clear`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Clear failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;
}
