import { useState, useEffect } from 'react'
import RegisterPlayer from './RegisterPlayer'
import BindCard from './BindCard'
import { api } from '../api'

export default function PlayerAdmin() {
  const [players, setPlayers] = useState([])
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null)
  const [viewingHistory, setViewingHistory] = useState(null)
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

  const deletePlayer = async (p) => {
    if (!confirm(`Delete ${p.name}? This cannot be undone.`)) return
    try {
      await api(`/players/${p.id}`, { method: 'DELETE' })
      load()
    } catch (e) {
      alert(e.message)
    }
  }

  const viewHistory = async (p) => {
    try {
      const data = await api(`/players/${p.id}`)
      setViewingHistory(data)
    } catch (e) {
      alert(e.message)
    }
  }

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
              <td style={{ ...td, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button style={btnSm} onClick={() => setSelected(p)}>Bind Card</button>
                <button style={btnSm} onClick={() => setEditing(p)}>Edit</button>
                <button style={btnSm} onClick={() => viewHistory(p)}>History</button>
                <button style={{ ...btnSm, background: '#ff6b6b' }} onClick={() => deletePlayer(p)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && (
        <BindCard player={selected} onDone={() => { setSelected(null); load() }} />
      )}
      {editing && (
        <EditPlayer player={editing} onDone={() => { setEditing(null); load() }} onCancel={() => setEditing(null)} />
      )}
      {viewingHistory && (
        <RechargeHistory player={viewingHistory} onClose={() => setViewingHistory(null)} />
      )}
    </div>
  )
}

function EditPlayer({ player, onDone, onCancel }) {
  const [name, setName] = useState(player.name || '')
  const [email, setEmail] = useState(player.email || '')
  const [age, setAge] = useState(player.age ?? '')
  const [notes, setNotes] = useState(player.notes || '')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api(`/players/${player.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name,
          email: email || null,
          age: age === '' ? null : Number(age),
          notes: notes || null,
        }),
      })
      onDone()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ background: '#1a1d27', padding: '1rem', borderRadius: 8, marginTop: '1rem' }}>
      <h4>Edit Player — {player.name}</h4>
      <input style={input} value={name} onChange={e => setName(e.target.value)} placeholder="Name" />
      <input style={input} value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
      <input style={input} value={age} onChange={e => setAge(e.target.value)} placeholder="Age" type="number" />
      <input style={input} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes" />
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="submit" style={btn} disabled={loading}>{loading ? '...' : 'Save'}</button>
        <button type="button" style={{ ...btn, background: '#495057' }} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

function RechargeHistory({ player, onClose }) {
  const history = player.recharge_history || []
  return (
    <div style={{ background: '#1a1d27', padding: '1rem', borderRadius: 8, marginTop: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4>Recharge History — {player.name}</h4>
        <button style={{ ...btnSm, background: '#495057' }} onClick={onClose}>Close</button>
      </div>
      {history.length === 0 ? (
        <p style={{ color: '#9aa0a6', fontSize: 13 }}>No recharge records.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
              {['Date', 'Money', 'Game Time'].map(h => (
                <th key={h} style={{ padding: '0.5rem', color: '#9aa0a6' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.map(r => (
              <tr key={r.id} style={{ borderBottom: '1px solid #1a1d27' }}>
                <td style={td}>{r.date}</td>
                <td style={td}>{r.money}</td>
                <td style={td}>{r.game_time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const input = { flex: 1, padding: '0.5rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed', marginBottom: 8, width: '100%', boxSizing: 'border-box' }
const btn = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const btnSm = { padding: '0.25rem 0.75rem', background: '#495057', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }
const td = { padding: '0.5rem' }
