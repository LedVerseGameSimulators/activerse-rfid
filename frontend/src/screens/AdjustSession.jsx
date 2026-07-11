import { useState } from 'react'
import { api } from '../api'

export default function AdjustSession({ session, onDone, onCancel }) {
  const [delta, setDelta] = useState(30)
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setLoading(true)
    try {
      await api(`/sessions/${session.id}/adjust`, {
        method: 'POST',
        body: JSON.stringify({ delta_min: delta, reason }),
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
        <h3>Adjust Session #{session.id}</h3>
        <p style={{ color: '#9aa0a6', marginBottom: '1rem' }}>
          Current: {session.minutes_remaining} min remaining
        </p>
        <label style={label}>Add/subtract minutes (negative to reduce)</label>
        <input style={input} type="number" value={delta} onChange={e => setDelta(+e.target.value)} />
        <label style={label}>Reason</label>
        <input style={input} value={reason} onChange={e => setReason(e.target.value)} placeholder="comp, correction..." />
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
          <button style={btn} onClick={submit} disabled={loading}>{loading ? '...' : 'Apply'}</button>
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
