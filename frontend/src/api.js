export async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

export const get = (p) => api(p);
export const post = (p, body) =>
  api(p, { method: 'POST', body: body !== undefined ? JSON.stringify(body ?? {}) : undefined });
export const put = (p, body) => api(p, { method: 'PUT', body: JSON.stringify(body) });

export async function upload(path, formData) {
  const r = await fetch(path, { method: 'POST', body: formData });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
