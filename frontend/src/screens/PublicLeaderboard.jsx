import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import LeaderboardFilterBar from '../components/LeaderboardFilterBar'
import {
  defaultLeaderboardFilters,
  buildLeaderboardQuery,
  boardToTournamentType,
  formatTournamentWindow,
  formatPlayMode,
} from '../leaderboardQuery'

export default function PublicLeaderboard() {
  const [filters, setFilters] = useState(() => defaultLeaderboardFilters('public'))
  const [rows, setRows] = useState([])
  const [activeGlobals, setActiveGlobals] = useState({ solo: null, team: null })
  const [tournaments, setTournaments] = useState([])
  const [hasMore, setHasMore] = useState(false)
  const [loadError, setLoadError] = useState('')

  const tType = boardToTournamentType(filters.board)

  const resolveTournamentMeta = useCallback(() => {
    if (filters.tournamentId) {
      const t = tournaments.find(x => String(x.id) === String(filters.tournamentId))
      if (t) return t
    }
    return tType === 'team' ? activeGlobals.team : activeGlobals.solo
  }, [filters.tournamentId, filters.board, tournaments, activeGlobals, tType])

  useEffect(() => {
    let cancelled = false
    const run = async (f) => {
      try {
        const type = boardToTournamentType(f.board)
        const q = buildLeaderboardQuery(f, { limit: 20 })
        const [data, active, tlist] = await Promise.all([
          api(`/dashboard/leaderboard?${q}`),
          api('/tournaments/active'),
          api(`/tournaments?status=active&type=${type}`),
        ])
        if (cancelled) return
        setRows(prev => (f.offset > 0 ? [...prev, ...data] : data))
        setActiveGlobals(active)
        setTournaments(tlist)
        setHasMore(Array.isArray(data) && data.length >= 20)
        setLoadError('')
      } catch (e) {
        if (!cancelled) setLoadError(e.message)
      }
    }
    run(filters)
    const t = setInterval(() => run({ ...filters, offset: 0 }), 30000)
    return () => { cancelled = true; clearInterval(t) }
  }, [filters])

  const onFiltersChange = next => setFilters(next)

  const tournamentMeta = resolveTournamentMeta()
  const emptyMsg = 'No plays match this tournament window and filters. Try widening the period or clearing filters.'

  return (
    <div style={page}>
      <h1 style={title}>Leaderboard</h1>
      {tournamentMeta && (
        <p style={tournamentHeader}>
          Tournament: <strong>{tournamentMeta.name}</strong> ({formatTournamentWindow(tournamentMeta)})
        </p>
      )}
      <LeaderboardFilterBar variant="public" filters={filters} onChange={onFiltersChange} style={{ marginBottom: '2rem' }} />
      {loadError && <p style={{ color: '#ff6b6b', textAlign: 'center' }}>{loadError}</p>}
      <div style={rankGrid}>
        {rows.map((r, i) => {
          const rank = r.rank ?? i + 1
          const memberNames = Array.isArray(r.members)
            ? r.members.map(m => m.name || `#${m.player_id}`).filter(Boolean).join(', ')
            : ''
          const titleText = filters.board === 'team'
            ? (r.group_name || r.player_name || memberNames || r.card_id || 'Team')
            : (r.player_name || r.card_id || `#${r.player_id || '?'}`)
          const size = r.roster_size_at_play ?? r.member_count
          const modeLabel = formatPlayMode(r.play_mode)
          const meta = [
            r.game,
            modeLabel,
            size != null ? `${size} players` : null,
            r.level,
          ].filter(Boolean).join(' · ')
          return (
            <div key={r.id ?? i} style={row}>
              <div style={rankNum}>{rank}</div>
              <div style={{ flex: 1 }}>
                <div style={playerName}>{titleText}</div>
                {filters.board === 'team' && memberNames && memberNames !== titleText && (
                  <div style={memberLine}>{memberNames}</div>
                )}
                <div style={gameLine}>{meta}</div>
                {r.played_at && <div style={dateLine}>{r.played_at}</div>}
              </div>
              <div style={scoreVal}>{r.score}</div>
            </div>
          )
        })}
        {rows.length === 0 && !loadError && <p style={{ color: '#9aa0a6', textAlign: 'center' }}>{emptyMsg}</p>}
        {hasMore && (
          <button
            type="button"
            style={moreBtn}
            onClick={() => setFilters(f => ({ ...f, offset: (f.offset || 0) + 20 }))}
          >
            Show more
          </button>
        )}
      </div>
    </div>
  )
}

const page = { minHeight: '100vh', background: '#06060c', color: '#e8eaed', padding: '2rem', fontFamily: 'system-ui, sans-serif' }
const title = { fontSize: '2.5rem', textAlign: 'center', marginBottom: '0.75rem' }
const tournamentHeader = { textAlign: 'center', color: '#9aa0a6', marginBottom: '1.25rem', fontSize: 15 }
const rankGrid = { maxWidth: 700, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 8 }
const row = { display: 'flex', alignItems: 'center', gap: 16, background: '#1a1d27', padding: '1rem 1.5rem', borderRadius: 12 }
const rankNum = { fontSize: '1.5rem', fontWeight: 700, color: '#3b5bdb', width: 40 }
const playerName = { fontSize: '1.1rem', fontWeight: 600 }
const memberLine = { fontSize: 13, color: '#c1c6ce', marginTop: 2 }
const gameLine = { fontSize: 13, color: '#9aa0a6' }
const dateLine = { fontSize: 12, color: '#6c757d', marginTop: 2 }
const scoreVal = { fontSize: '1.75rem', fontWeight: 700 }
const moreBtn = { marginTop: 8, padding: '0.75rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }
