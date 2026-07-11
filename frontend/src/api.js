const BASE = import.meta.env.VITE_API_URL || 'http://localhost:9000'

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || err.error || res.statusText)
  }
  return res.json()
}
