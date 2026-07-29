import { useEffect, useState } from 'react'
import { api } from '../api'

export default function SessionRoster({ sessionId, onChanged }) {
  const [roster, setRoster] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      const data = await api(`/sessions/${sessionId}/roster`)
      setRoster(data.roster || [])
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [sessionId])

  const search = async (q) => {
    setQuery(q)
    if (!q.trim()) { setResults([]); return }
    try {
      const players = await api(`/players?q=${encodeURIComponent(q.trim())}`)
      setResults(Array.isArray(players) ? players.slice(0, 8) : [])
    } catch {
      setResults([])
    }
  }

  const add = async (player) => {
    setBusy(true)
    setError('')
    try {
      const data = await api(`/sessions/${sessionId}/roster`, {
        method: 'POST',
        body: JSON.stringify({ player_id: player.id ?? player.custom_id }),
      })
      setRoster(data.roster || [])
      setQuery('')
      setResults([])
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (playerId) => {
    setBusy(true)
    setError('')
    try {
      const data = await api(`/sessions/${sessionId}/roster/${playerId}`, { method: 'DELETE' })
      setRoster(data.roster || [])
      onChanged?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const n = roster.length

  return (
    <div style={wrap}>
      <p style={{ fontWeight: 600, marginBottom: 6 }}>Team roster ({n})</p>
      <p style={hint}>
        Scores on this card split across all members (total ÷ N) until teammates are removed.
      </p>
      <ul style={{ listStyle: 'none', padding: 0, margin: '0.75rem 0' }}>
        {roster.map(m => (
          <li key={m.player_id} style={row}>
            <span>
              {m.name}
              {m.is_payer ? <span style={badge}>Leader</span> : null}
            </span>
            {!m.is_payer && (
              <button style={btnRemove} disabled={busy} onClick={() => remove(m.player_id)}>
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      <input
        style={input}
        placeholder="Search player to add…"
        value={query}
        onChange={(e) => search(e.target.value)}
        disabled={busy}
      />
      {results.length > 0 && (
        <div style={dropdown}>
          {results.map(p => {
            const id = p.id ?? p.custom_id
            const already = roster.some(m => m.player_id === id)
            return (
              <button
                key={id}
                style={dropItem}
                disabled={busy || already}
                onClick={() => add(p)}
              >
                {p.name} · {p.phone || p.phone_num}
                {already ? ' (already on roster)' : ''}
              </button>
            )
          })}
        </div>
      )}
      {error && <p style={{ color: '#ff6b6b', fontSize: 13, marginTop: 8 }}>{error}</p>}
    </div>
  )
}

const wrap = {
  marginTop: '1rem', padding: '0.75rem', background: '#12141c',
  borderRadius: 8, border: '1px solid #2a2d3a',
}
const hint = { color: '#9aa0a6', fontSize: 12, margin: 0 }
const row = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '6px 0', borderBottom: '1px solid #1a1d27', fontSize: 14,
}
const badge = {
  marginLeft: 8, fontSize: 11, color: '#51cf66', background: '#12261a',
  padding: '2px 6px', borderRadius: 4,
}
const btnRemove = {
  padding: '4px 10px', background: '#5c1a1a', color: '#ffc9c9',
  border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12,
}
const input = {
  width: '100%', padding: '0.5rem 0.75rem', borderRadius: 6,
  border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed',
  boxSizing: 'border-box',
}
const dropdown = {
  marginTop: 4, background: '#0f1117', border: '1px solid #2a2d3a',
  borderRadius: 6, maxHeight: 200, overflow: 'auto',
}
const dropItem = {
  display: 'block', width: '100%', textAlign: 'left', padding: '0.5rem 0.75rem',
  background: 'transparent', color: '#e8eaed', border: 'none', cursor: 'pointer',
  borderBottom: '1px solid #1a1d27', fontSize: 13,
}
