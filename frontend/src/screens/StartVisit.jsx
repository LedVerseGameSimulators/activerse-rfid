import { useEffect, useState, useMemo } from 'react'
import { api } from '../api'

const MIN_DURATION = 1
const MAX_DURATION = 720

export default function StartVisit({ player, onDone, onCancel }) {
  const [duration, setDuration] = useState(60)
  const [groupId, setGroupId] = useState(null)
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')

  const reloadGroups = async () => {
    const detail = await api(`/players/${player.id}`)
    const list = detail.groups || []
    setGroups(list)
    const solo = list.find(g => g.kind === 'solo')
    const defaultId = solo?.id ?? detail.solo_group_id ?? list[0]?.id ?? null
    setGroupId(defaultId)
    return detail
  }

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoadError('')
      try {
        if (!cancelled) await reloadGroups()
      } catch (e) {
        if (!cancelled) setLoadError(e.message || 'Could not load player groups.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [player.id])

  const selected = groups.find(g => g.id === groupId)
  const isVisitLeader = selected?.leader_player_id === player.id
  const leaderCanScan = Boolean(
    selected?.leader_has_card || (isVisitLeader && player.card_id && player.card_id.length > 5)
  )

  const durationValid = useMemo(() => {
    const d = Number(duration)
    return Number.isFinite(d) && d >= MIN_DURATION && d <= MAX_DURATION
  }, [duration])

  const ensureSoloGroup = async () => {
    await api(`/players/${player.id}/ensure-solo-group`, { method: 'POST' })
    return reloadGroups()
  }

  const submit = async () => {
    setError('')
    if (!durationValid) {
      setError(`Duration must be between ${MIN_DURATION} and ${MAX_DURATION} minutes.`)
      return
    }
    let gid = groupId
    try {
      if (!gid) {
        const detail = await ensureSoloGroup()
        gid = detail.solo_group_id ?? detail.groups?.find(g => g.kind === 'solo')?.id
        if (!gid) {
          setError('No group available yet. Try again or open Groups.')
          return
        }
        setGroupId(gid)
      }
      if (!leaderCanScan) {
        setError('Visit leader has no RFID card bound. Bind the leader’s card or pass card_id when you are the leader.')
        return
      }
      setLoading(true)
      const body = { duration_min: Math.round(Number(duration)) }
      if (isVisitLeader && player.card_id && player.card_id.length > 5) {
        body.card_id = player.card_id
      }
      await api(`/groups/${gid}/start-visit`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onDone()
    } catch (e) {
      setError(e.message || 'Start visit failed.')
    } finally {
      setLoading(false)
    }
  }

  const onDurationChange = (raw) => {
    const n = parseInt(raw, 10)
    if (Number.isNaN(n)) {
      setDuration('')
      return
    }
    setDuration(Math.min(MAX_DURATION, Math.max(MIN_DURATION, n)))
  }

  return (
    <div style={overlay}>
      <div style={modal}>
        <h3>Start Visit — {player.name}</h3>
        <p style={{ color: '#9aa0a6', fontSize: 13, marginTop: 8 }}>
          Pay once from the visit leader&apos;s credit. Only the leader&apos;s RFID card works at game kiosks;
          team members do not scan in separately during this visit.
        </p>
        {loadError && <p style={errStyle}>{loadError}</p>}
        {groups.length === 0 && !loadError && (
          <p style={{ color: '#fcc419', fontSize: 13, marginTop: 8 }}>
            No group yet for this player. Start visit will create their solo group first.
          </p>
        )}
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
        {selected && (
          <p style={{ color: '#9aa0a6', fontSize: 13, marginTop: 12 }}>
            Visit leader: <strong style={{ color: '#e8eaed' }}>{selected.leader_name || '—'}</strong>
            {groups.length === 1 && (
              <> · Group: <strong style={{ color: '#e8eaed' }}>{selected.name}</strong>
                {selected.kind === 'solo' ? ' (solo)' : ''}</>
            )}
          </p>
        )}
        {selected && !leaderCanScan && (
          <p style={errStyle}>
            Leader has no RFID card bound. Bind a card for {selected.leader_name || 'the leader'} before starting.
          </p>
        )}
        <label style={label}>Duration (minutes)</label>
        <input
          style={input}
          type="number"
          value={duration}
          onChange={e => onDurationChange(e.target.value)}
          min={MIN_DURATION}
          max={MAX_DURATION}
        />
        {error && <p style={{ ...errStyle, marginTop: 12 }}>{error}</p>}
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
          <button
            style={btn}
            onClick={submit}
            disabled={loading || !durationValid || (selected && !leaderCanScan)}
          >
            {loading ? '...' : 'Start visit'}
          </button>
          <button style={{ ...btnCancel }} onClick={onCancel}>Cancel</button>
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
const btnCancel = { ...btn, background: '#495057' }
const errStyle = { color: '#ff6b6b', fontSize: 13, marginTop: 8 }
