import { useState, useEffect } from 'react'
import RegisterPlayer from './RegisterPlayer'
import BindCard from './BindCard'
import { api } from '../api'

export default function PlayerAdmin() {
  const [players, setPlayers] = useState([])
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(null)
  const [showRegister, setShowRegister] = useState(true)

  const load = async () => {
    try {
      const data = await api(q ? `/players?q=${encodeURIComponent(q)}` : '/players')
      setPlayers(data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Player Admin</h1>
      {showRegister ? (
        <RegisterPlayer onDone={() => { setShowRegister(false); load() }} />
      ) : (
        <button style={btn} onClick={() => setShowRegister(true)}>+ Register New Player</button>
      )}
      <div style={{ display: 'flex', gap: 8, margin: '1rem 0' }}>
        <input style={input} placeholder="Search..." value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
        <button style={btn} onClick={load}>Search</button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
            {['ID', 'Name', 'Phone', 'Card', 'Actions'].map(h => (
              <th key={h} style={{ padding: '0.5rem', color: '#9aa0a6' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map(p => (
            <tr key={p.id} style={{ borderBottom: '1px solid #1a1d27' }}>
              <td style={td}>{p.id}</td>
              <td style={td}>{p.name}</td>
              <td style={td}>{p.phone}</td>
              <td style={td}>{p.card_id || '—'}</td>
              <td style={td}>
                <button style={btnSm} onClick={() => setSelected(p)}>Bind Card</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && (
        <BindCard player={selected} onDone={() => { setSelected(null); load() }} />
      )}
    </div>
  )
}

const input = { flex: 1, padding: '0.5rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const btnSm = { padding: '0.25rem 0.75rem', background: '#495057', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }
const td = { padding: '0.5rem' }
