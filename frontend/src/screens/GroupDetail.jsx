import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'

const td = { padding: '0.5rem' }
const btn = { padding: '0.45rem 0.9rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const input = { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed', width: '100%', boxSizing: 'border-box' }
const card = { background: '#1a1d27', borderRadius: 12, padding: '1rem', border: '1px solid #2a2d3a', marginBottom: '1rem' }

export default function GroupDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [group, setGroup] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [regName, setRegName] = useState('')
  const [regPhone, setRegPhone] = useState('')
  const [duration, setDuration] = useState(60)
  const [cardId, setCardId] = useState('')
  const [visitResult, setVisitResult] = useState(null)

  const load = async () => {
    try {
      setGroup(await api(`/groups/${id}`))
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [id])

  const search = async (value) => {
    setQ(value)
    if (!value.trim()) { setResults([]); return }
    try {
      setResults(await api(`/players?q=${encodeURIComponent(value.trim())}`))
    } catch {
      setResults([])
    }
  }

  const addExisting = async (player) => {
    try {
      setGroup(await api(`/groups/${id}/members`, {
        method: 'POST',
        body: JSON.stringify({ player_id: player.id }),
      }))
      setQ('')
      setResults([])
    } catch (e) {
      setError(e.message)
    }
  }

  const registerAdd = async (e) => {
    e.preventDefault()
    try {
      setGroup(await api(`/groups/${id}/members`, {
        method: 'POST',
        body: JSON.stringify({ name: regName, phone: regPhone }),
      }))
      setRegName('')
      setRegPhone('')
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (playerId) => {
    try {
      setGroup(await api(`/groups/${id}/members/${playerId}`, { method: 'DELETE' }))
    } catch (e) {
      setError(e.message)
    }
  }

  const setLeader = async (playerId) => {
    try {
      setGroup(await api(`/groups/${id}/leader`, {
        method: 'PUT',
        body: JSON.stringify({ player_id: playerId }),
      }))
    } catch (e) {
      setError(e.message)
    }
  }

  const startVisit = async (e) => {
    e.preventDefault()
    try {
      const body = { duration_min: Number(duration) }
      if (cardId.trim()) body.card_id = cardId.trim()
      setVisitResult(await api(`/groups/${id}/start-visit`, {
        method: 'POST',
        body: JSON.stringify(body),
      }))
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  const deleteGroup = async () => {
    if (!confirm(`Delete group "${group?.name}"?`)) return
    try {
      await api(`/groups/${id}`, { method: 'DELETE' })
      nav('/groups')
    } catch (e) {
      alert(e.message)
    }
  }

  if (!group && !error) return <p style={{ color: '#9aa0a6' }}>Loading…</p>

  return (
    <div>
      <p>
        <Link to="/groups" style={{ color: '#74c0fc' }}>← Groups</Link>
        {group?.company_id && (
          <> · <Link to={`/companies/${group.company_id}`} style={{ color: '#74c0fc' }}>{group.company_name}</Link></>
        )}
      </p>
      <h1 style={{ marginBottom: '0.25rem' }}>{group?.name}</h1>
      <p style={{ color: '#9aa0a6', marginBottom: '1rem' }}>{group?.company_name}</p>
      {error && <p style={{ color: '#ff6b6b' }}>{error}</p>}

      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: '1rem', margin: 0 }}>Members</h2>
          <button style={{ ...btn, background: '#ff6b6b' }} onClick={deleteGroup}>Delete group</button>
        </div>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {(group?.members || []).map(m => (
            <li key={m.player_id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #12141c' }}>
              <span style={{ flex: 1 }}>{m.name} · {m.phone}{m.is_leader ? ' (leader)' : ''}</span>
              {!m.is_leader && (
                <button style={{ ...btn, background: '#2f9e44', fontSize: 12 }} onClick={() => setLeader(m.player_id)}>Make leader</button>
              )}
              {!m.is_leader && (
                <button style={{ ...btn, background: '#5c1a1a', fontSize: 12 }} onClick={() => remove(m.player_id)}>Remove</button>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Add existing player</h2>
        <input style={input} placeholder="Search players…" value={q} onChange={e => search(e.target.value)} />
        {results.slice(0, 8).map(p => (
          <button key={p.id} style={{ ...btn, display: 'block', width: '100%', marginTop: 6, textAlign: 'left', background: '#12141c' }}
            onClick={() => addExisting(p)}>
            {p.name} · {p.phone}
          </button>
        ))}
      </div>

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Register + add</h2>
        <form onSubmit={registerAdd} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input style={{ ...input, width: 180 }} placeholder="Name" value={regName} onChange={e => setRegName(e.target.value)} required />
          <input style={{ ...input, width: 180 }} placeholder="Phone" value={regPhone} onChange={e => setRegPhone(e.target.value)} required />
          <button style={btn} type="submit">Add</button>
        </form>
        <p style={{ color: '#9aa0a6', fontSize: 12 }}>Uses phone dedup — existing players are linked, not duplicated.</p>
      </div>

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Start visit</h2>
        <p style={{ color: '#9aa0a6', fontSize: 13 }}>
          Issues a session on the leader’s card and loads all members onto the session roster (score split).
          Leader must have credits; optional card_id binds/rebinds the leader first.
        </p>
        <form onSubmit={startVisit} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input style={{ ...input, width: 100 }} type="number" min={1} value={duration} onChange={e => setDuration(e.target.value)} />
          <span style={{ color: '#9aa0a6' }}>min</span>
          <input style={{ ...input, width: 200 }} placeholder="Card ID (optional)" value={cardId} onChange={e => setCardId(e.target.value)} />
          <button style={{ ...btn, background: '#2f9e44' }} type="submit">Start visit</button>
        </form>
        {visitResult && (
          <pre style={{ marginTop: 12, fontSize: 12, color: '#c1c2c5', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(visitResult, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}
