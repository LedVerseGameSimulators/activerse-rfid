import { useState } from 'react'
import { api } from '../api'

export default function IssueSession({ player, onDone, onCancel }) {
  const [duration, setDuration] = useState(60)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    try {
      await api('/sessions', {
        method: 'POST',
        body: JSON.stringify({ player_id: player.id, duration_min: duration, notes }),
      })
      onDone()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={overlay}>
      <div style={modal}>
        <h3>Issue Session — {player.name}</h3>
        <label style={label}>Duration (minutes)</label>
        <input style={input} type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={1} />
        <label style={label}>Notes</label>
        <input style={input} value={notes} onChange={e => setNotes(e.target.value)} />
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
          <button style={btn} onClick={submit} disabled={loading}>{loading ? '...' : 'Confirm'}</button>
          <button style={{ ...btn, background: '#495057' }} onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

const overlay = { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }
const modal = { background: '#1a1d27', padding: '1.5rem', borderRadius: 12, width: 400 }
const label = { display: 'block', marginBottom: 4, color: '#9aa0a6', fontSize: 13, marginTop: 12 }
const input = { width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { padding: '0.6rem 1.25rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
