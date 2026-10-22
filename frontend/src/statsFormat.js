/** Pure formatters for stat sheets (no React). */

export function formatScore(value) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return String(n)
}

export function formatMinutes(value) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  const rounded = Math.round(n * 100) / 100
  return `${rounded} min`
}

export function formatCount(value) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return String(Math.trunc(n))
}

export function formatAvg(value, digits = 2) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return String(Math.round(n * 10 ** digits) / 10 ** digits)
}
