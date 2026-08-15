/**
 * frontend/src/api.js
 * ────────────────────
 * All HTTP calls to the Ask-Echo backend.
 *
 * Authentication:
 *   Call setAuthToken(googleIdToken) after a successful Google Sign-In.
 *   Every subsequent API request automatically includes:
 *     Authorization: Bearer <token>
 *
 * Namespace isolation:
 *   The server derives the Pinecone namespace from the verified user identity
 *   (sub claim of the JWT). No client-side namespace logic is needed.
 */

const BASE = 'https://ask-echo-backend.onrender.com';

// ---------------------------------------------------------------------------
// Auth token store — module-level (lives for the page session)
// ---------------------------------------------------------------------------

let _authToken = null;

/** Store the Google ID token after sign-in. */
export function setAuthToken(token) {
  _authToken = token;
}

/** Clear the stored token (call on sign-out). */
export function clearAuthToken() {
  _authToken = null;
}

/** Returns true when a token is available. */
export function isAuthenticated() {
  return Boolean(_authToken);
}

/**
 * Build standard auth headers.
 * Throws if the user is not signed in.
 */
function authHeaders() {
  if (!_authToken) {
    throw new Error('Not authenticated. Please sign in with Google.');
  }
  return { Authorization: `Bearer ${_authToken}` };
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Upload and ingest a document.
 * Namespace is derived server-side from the verified user identity.
 *
 * @param {File} file  - PDF, JPEG, or PNG to ingest.
 * @returns {Promise<{status: string, file_name: string, chunks_indexed: number}>}
 */
export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  // namespace field accepted by the server for compat but overridden server-side
  form.append('namespace', 'user_scoped');

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    headers: authHeaders(), // DO NOT set Content-Type — browser sets multipart boundary
    body: form,
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Upload failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data; // { status, file_name, chunks_indexed }
}

/**
 * Query the document store for a grounded answer.
 * Scoped to the authenticated user's namespace (server-enforced).
 *
 * @param {string} query  - Natural-language question.
 * @returns {Promise<{answer: string, sources: Array<object>}>}
 */
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
  return data; // { answer, sources }
}

/**
 * Delete all vectors for the currently signed-in user.
 * Namespace is determined server-side from the auth token.
 *
 * @returns {Promise<{status: string, namespace: string}>}
 */
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
  return data; // { status, namespace }
}
