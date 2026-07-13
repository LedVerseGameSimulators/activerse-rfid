import { useState } from 'react'
import { api } from '../api'

export default function TopUp({ player, moneyPerMinute, onDone, onCancel }) {
  const [minutes, setMinutes] = useState(60)
  const [money, setMoney] = useState(60 * (moneyPerMinute || 25))
  const [loading, setLoading] = useState(false)

  const setMin = (v) => { setMinutes(v); setMoney(Math.round(v * (moneyPerMinute || 25))) }

  const submit = async () => {
    setLoading(true)
    try {
      await api(`/players/${player.id}/topup`, {
        method: 'POST',
        body: JSON.stringify({ minutes, amount_money: money }),
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
        <h3>Top Up — {player.name}</h3>
        <p style={{ color: '#9aa0a6', marginBottom: '1rem' }}>
          Current balance: {player.credit_balance ?? 0} min
        </p>
        <label style={label}>Minutes to add</label>
        <input style={input} type="number" value={minutes} onChange={e => setMin(+e.target.value)} min={1} />
        <label style={label}>Amount charged</label>
        <input style={input} type="number" value={money} onChange={e => setMoney(+e.target.value)} min={0} />
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
          <button style={btn} onClick={submit} disabled={loading}>{loading ? '...' : 'Add Credit'}</button>
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
