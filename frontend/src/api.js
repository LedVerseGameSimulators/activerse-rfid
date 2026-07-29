const BASE = import.meta.env.VITE_API_URL || 'http://localhost:9000'

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail ?? err.error ?? res.statusText
    // FastAPI validation errors return detail as an array of objects
    const message = Array.isArray(detail)
      ? detail.map(d => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join('; ')
      : String(detail)
    throw new Error(message)
  }
  return res.json()
}
