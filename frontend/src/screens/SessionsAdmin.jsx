import { useState, useEffect } from 'react'
import { api } from '../api'
import AdjustSession from './AdjustSession'

export default function SessionsAdmin() {
  const [sessions, setSessions] = useState([])
  const [adjusting, setAdjusting] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setSessions(await api('/sessions/active'))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  const close = async (session) => {
    if (!confirm(`Close session #${session.id} for ${session.player_name}?`)) return
    try {
      await api(`/sessions/${session.id}/close`, { method: 'POST' })
      load()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Active Sessions</h1>
      {error && <p style={{ color: '#ff6b6b' }}>{error}</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
            {['Player', 'Phone', 'Card', 'Team', 'Issued', 'Expires', 'Min. Remaining', ''].map(h => (
              <th key={h} style={{ padding: '0.5rem', color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map(s => {
            const roster = Array.isArray(s.roster) ? s.roster : []
            const rosterNames = roster.map(m => m.name).filter(Boolean).join(', ')
            const count = s.roster_count ?? roster.length
            return (
              <tr key={s.id} style={{ borderBottom: '1px solid #1a1d27' }}>
                <td style={td}>{s.player_name}</td>
                <td style={td}>{s.phone}</td>
                <td style={td}>{s.card_id || '—'}</td>
                <td style={td}>
                  {count > 1
                    ? <span title={rosterNames}>{count}: {rosterNames || '—'}</span>
                    : <span style={{ color: '#6c757d' }}>{count || 1}</span>}
                </td>
                <td style={td}>{s.issued_at}</td>
                <td style={td}>{s.expiry_at}</td>
                <td style={{ ...td, fontWeight: 600 }}>{s.minutes_remaining}</td>
                <td style={td}>
                  <button style={btnSm} onClick={() => setAdjusting(s)}>Adjust</button>
                  <button style={{ ...btnSm, background: '#ff6b6b', marginLeft: 6 }} onClick={() => close(s)}>Close</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {sessions.length === 0 && !error && <p style={{ color: '#9aa0a6' }}>No active sessions.</p>}
      {adjusting && (
        <AdjustSession
          session={adjusting}
          onDone={() => { setAdjusting(null); load() }}
          onCancel={() => setAdjusting(null)}
        />
      )}
    </div>
  )
}

const td = { padding: '0.5rem' }
const btnSm = { padding: '0.35rem 0.75rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
