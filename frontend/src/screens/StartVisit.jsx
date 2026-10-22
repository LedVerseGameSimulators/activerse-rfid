import { useEffect, useState } from 'react'
import { api } from '../api'

export default function StartVisit({ player, onDone, onCancel }) {
  const [duration, setDuration] = useState(60)
  const [groupId, setGroupId] = useState(null)
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const detail = await api(`/players/${player.id}`)
        if (cancelled) return
        const list = detail.groups || []
        setGroups(list)
        const solo = list.find(g => g.kind === 'solo')
        const defaultId = solo?.id ?? detail.solo_group_id ?? list[0]?.id ?? null
        setGroupId(defaultId)
      } catch {
        if (!cancelled) {
          setGroups(player.groups || [])
          setGroupId(player.solo_group_id || player.primary_group_id || null)
        }
      }
    }
    load()
    return () => { cancelled = true }
  }, [player.id])

  const submit = async () => {
    if (!groupId) {
      alert('No group available — refresh the player or register again.')
      return
    }
    setLoading(true)
    try {
      const body = { duration_min: duration }
      if (player.card_id) body.card_id = player.card_id
      await api(`/groups/${groupId}/start-visit`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onDone()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const selected = groups.find(g => g.id === groupId)

  return (
    <div style={overlay}>
      <div style={modal}>
        <h3>Start Visit — {player.name}</h3>
        <p style={{ color: '#9aa0a6', fontSize: 13, marginTop: 8 }}>
          Pay once from the visit leader&apos;s credit. Only the leader&apos;s RFID card works at game kiosks;
          team members do not scan in separately during this visit.
        </p>
        {groups.length > 1 && (
          <>
            <label style={label}>Group</label>
            <select
              style={input}
              value={groupId ?? ''}
              onChange={e => setGroupId(Number(e.target.value))}
            >
              {groups.map(g => (
                <option key={g.id} value={g.id}>
                  {g.name}{g.kind === 'solo' ? ' (solo)' : ''}{g.company_name ? ` · ${g.company_name}` : ''}
                </option>
              ))}
            </select>
          </>
        )}
        {groups.length === 1 && selected && (
          <p style={{ color: '#9aa0a6', fontSize: 13, marginTop: 12 }}>
            Group: <strong style={{ color: '#e8eaed' }}>{selected.name}</strong>
            {selected.kind === 'solo' ? ' (solo)' : ''}
          </p>
        )}
        <label style={label}>Duration (minutes)</label>
        <input style={input} type="number" value={duration} onChange={e => setDuration(+e.target.value)} min={1} />
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
          <button style={btn} onClick={submit} disabled={loading || !groupId}>
            {loading ? '...' : 'Start visit'}
          </button>
          <button style={{ ...btn, background: '#495057' }} onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

const overlay = { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }
const modal = { background: '#1a1d27', padding: '1.5rem', borderRadius: 12, width: 440, maxWidth: '95vw' }
const label = { display: 'block', marginBottom: 4, color: '#9aa0a6', fontSize: 13, marginTop: 12 }
const input = { width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { padding: '0.6rem 1.25rem', background: '#2f9e44', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
