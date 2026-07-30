import { useState } from 'react'
import { api } from '../api'

export default function PlayerSearch({ onSelect }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const data = await api(`/players?q=${encodeURIComponent(q)}`)
      setResults(data)
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          style={inputStyle}
          placeholder="Phone, name, or card ID..."
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && search()}
          autoFocus
        />
        <button style={btnStyle} onClick={search} disabled={loading}>
          {loading ? '...' : 'Search'}
        </button>
      </div>
      {results.length > 0 && (
        <ul style={{ listStyle: 'none', marginTop: '1rem' }}>
          {results.map(p => (
            <li key={p.id} style={itemStyle} onClick={() => onSelect(p)}>
              <strong>{p.name}</strong>
              <span style={{ color: '#9aa0a6', marginLeft: 8 }}>{p.phone}</span>
              {p.card_id && <span style={{ color: '#51cf66', marginLeft: 8 }}>{p.card_id}</span>}
              {p.company_name && <span style={badgeStyle}>{p.company_name}</span>}
              {p.group_name && <span style={{ ...badgeStyle, color: '#74c0fc' }}>{p.group_name}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const inputStyle = { flex: 1, padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btnStyle = { padding: '0.6rem 1.25rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const itemStyle = { padding: '0.75rem', background: '#1a1d27', borderRadius: 8, marginBottom: 6, cursor: 'pointer' }
const badgeStyle = { display: 'inline-block', fontSize: 11, padding: '2px 8px', borderRadius: 999, background: '#0f1117', color: '#9aa0a6', marginLeft: 8 }
