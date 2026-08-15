
const BASE = import.meta.env.VITE_API_BASE ?? '';

export async function uploadDocument(file, namespace = 'public') {
  const form = new FormData();
  form.append('file', file);
  form.append('namespace', namespace);   // required by backend Form(...)

  const res = await fetch(`${BASE}/upload/`, { method: 'POST', body: form });
  const data = await res.json();

  if (!res.ok) {
    const msg = data?.detail ?? `Upload failed (HTTP ${res.status})`;
    throw new Error(msg);
  }
  return data;  // { status, file_name, chunks_indexed }
}

export async function queryDocuments(query, namespace = 'public', topK = 5) {
  const res = await fetch(`${BASE}/query/`, {
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
