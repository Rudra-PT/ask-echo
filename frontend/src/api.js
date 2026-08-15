/**
 * frontend/src/api.js
 * ────────────────────
 * All HTTP calls to the Ask-Echo backend.
 *
 * Session isolation:
 *   Each browser tab gets a persistent UUID stored in sessionStorage
 *   under the key "echo_session_id".  That UUID is used as the Pinecone
 *   namespace, so every user's vectors are completely isolated from others.
 */

// Production Render URL — used in all environments (Vercel serves the built
// bundle, which always talks to the live backend).
const BASE = 'https://ask-echo-backend.onrender.com';

// ---------------------------------------------------------------------------
// Session helpers
// ---------------------------------------------------------------------------

/**
 * Returns a stable session UUID for this browser tab.
 * Creates and persists one in sessionStorage on first call.
 */
export function getSessionId() {
  const KEY = 'echo_session_id';
  let id = sessionStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(KEY, id);
  }
  return id;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Upload and ingest a document.
 * The session UUID is used as the Pinecone namespace so vectors are
 * isolated per browser tab.
 *
 * @param {File} file  - PDF, JPEG, or PNG to ingest.
 * @returns {Promise<{status: string, file_name: string, chunks_indexed: number}>}
 */
export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('namespace', getSessionId());

  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Upload failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data; // { status, file_name, chunks_indexed }
}

/**
 * Query the document store for a grounded answer.
 * Automatically scoped to the current session's namespace.
 *
 * @param {string} query  - Natural-language question.
 * @returns {Promise<{answer: string, sources: Array<object>}>}
 */
export async function queryDocuments(query) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, namespace: getSessionId() }),
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Query failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data; // { answer, sources }
}

/**
 * Delete all vectors in the current session's namespace.
 * Call this when the user wants to start fresh.
 *
 * @returns {Promise<{status: string, namespace: string}>}
 */
export async function clearSession() {
  const ns = getSessionId();
  const res = await fetch(`${BASE}/upload/clear?namespace=${encodeURIComponent(ns)}`, {
    method: 'DELETE',
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Clear failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data; // { status, namespace }
}
