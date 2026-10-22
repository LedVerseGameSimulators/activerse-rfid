export default function StatTiles({ tiles }) {
  if (!tiles?.length) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
      {tiles.map(t => (
        <div
          key={t.label}
          style={{ background: '#1a1d27', padding: '0.85rem 1.25rem', borderRadius: 12, minWidth: 120 }}
        >
          <div style={{ color: '#9aa0a6', fontSize: 12 }}>{t.label}</div>
          <div style={{ fontSize: '1.35rem', fontWeight: 700, marginTop: 4 }}>{t.value}</div>
          {t.hint && <div style={{ color: '#6c757d', fontSize: 11, marginTop: 4 }}>{t.hint}</div>}
        </div>
      ))}
    </div>
  )
}
