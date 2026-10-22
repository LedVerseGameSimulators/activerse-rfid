const input = {
  padding: '0.5rem 0.75rem',
  borderRadius: 6,
  border: '1px solid #2a2d3a',
  background: '#0f1117',
  color: '#e8eaed',
  fontSize: 13,
}

export default function DateRange({ dateFrom, dateTo, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label style={{ color: '#9aa0a6', fontSize: 13 }}>
        From
        <input
          type="date"
          style={{ ...input, display: 'block', marginTop: 4 }}
          value={dateFrom}
          onChange={e => onChange({ dateFrom: e.target.value })}
        />
      </label>
      <label style={{ color: '#9aa0a6', fontSize: 13 }}>
        To
        <input
          type="date"
          style={{ ...input, display: 'block', marginTop: 4 }}
          value={dateTo}
          onChange={e => onChange({ dateTo: e.target.value })}
        />
      </label>
    </div>
  )
}
