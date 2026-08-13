const BASE = 'https://ask-echo-backend.onrender.com';

export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);


  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Upload failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;
}

export async function queryDocuments(query, namespace = 'public', topK = 5) {

  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, namespace, top_k: topK }),
  });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Query failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;
}