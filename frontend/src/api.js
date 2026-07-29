const BASE = import.meta.env.VITE_API_URL || 'http://localhost:9000'

function errorMessage(err, statusText) {
  const detail = err.detail ?? err.error ?? statusText
  if (Array.isArray(detail)) {
    return detail.map(d => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join('; ')
  }
  return String(detail)
}

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err, res.statusText))
  }
  return res.json()
}

/** Multipart upload — do not set Content-Type (browser sets boundary). */
export async function apiForm(path, formData) {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err, res.statusText))
  }
  return res.json()
}

export function templateUrl() {
  return `${BASE}/import/template.xlsx`
}
