import { muted } from './statsTheme'

/** Inline bar chart for per-day volume — no external chart library. */
export default function SparkBar({ points, valueKey = 'plays', labelKey = 'date' }) {
  if (!points?.length) {
    return <p style={{ ...muted, margin: 0 }}>No daily volume in this window.</p>
  }
  const sorted = [...points].sort((a, b) => String(a[labelKey]).localeCompare(String(b[labelKey])))
  const max = Math.max(...sorted.map(p => Number(p[valueKey]) || 0), 1)

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 72, marginTop: 8 }}>
      {sorted.map(p => {
        const v = Number(p[valueKey]) || 0
        const h = Math.max(4, Math.round((v / max) * 64))
        return (
          <div
            key={p[labelKey]}
            title={`${p[labelKey]}: ${v}`}
            style={{
              flex: '1 1 0',
              minWidth: 6,
              maxWidth: 24,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'flex-end',
            }}
          >
            <div style={{ width: '100%', height: h, background: '#3b5bdb', borderRadius: 2 }} />
            <span style={{ fontSize: 9, color: '#6c757d', marginTop: 4, transform: 'rotate(-45deg)', whiteSpace: 'nowrap' }}>
              {String(p[labelKey]).slice(5)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
