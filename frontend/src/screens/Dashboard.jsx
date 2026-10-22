import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import GameHealthTile from '../components/GameHealthTile'
import LeaderboardTable from '../components/LeaderboardTable'
import LeaderboardFilterBar from '../components/LeaderboardFilterBar'
import { api } from '../api'
import {
  defaultLeaderboardFilters,
  buildLeaderboardQuery,
  boardToTournamentType,
  formatTournamentWindow,
} from '../leaderboardQuery'

export default function Dashboard() {
  const [health, setHealth] = useState([])
  const [leaderboard, setLeaderboard] = useState([])
  const [stats, setStats] = useState(null)
  const [filters, setFilters] = useState(() => defaultLeaderboardFilters('admin'))
  const [activeGlobals, setActiveGlobals] = useState({ solo: null, team: null })
  const [tournaments, setTournaments] = useState([])

  const tType = boardToTournamentType(filters.board)

  const tournamentMeta = useCallback(() => {
    if (filters.tournamentId) {
      const t = tournaments.find(x => String(x.id) === String(filters.tournamentId))
      if (t) return t
    }
    return tType === 'team' ? activeGlobals.team : activeGlobals.solo
  }, [filters.tournamentId, filters.board, tournaments, activeGlobals, tType])()

  const load = async () => {
    try {
      const q = buildLeaderboardQuery(filters, { limit: 20 })
      const [h, lb, st, active, tlist] = await Promise.all([
        api('/dashboard/health'),
        api(`/dashboard/leaderboard?${q}`),
        api('/dashboard/stats'),
        api('/tournaments/active'),
        api(`/tournaments?status=active&type=${tType}`),
      ])
      setHealth(h)
      setLeaderboard(lb)
      setStats(st)
      setActiveGlobals(active)
      setTournaments(tlist)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { load() }, [filters])

  const onFiltersChange = next => setFilters(next)

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>
      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Game Health</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
          {health.map(g => (
            <Link
              key={g.game}
              to={`/stats/game/${g.game}`}
              style={{ textDecoration: 'none', color: 'inherit' }}
              title={`Open ${g.game} stat sheet`}
            >
              <GameHealthTile game={g.game} status={g.status} lastChecked={g.last_checked} />
            </Link>
          ))}
        </div>
      </section>
      {stats && (
        <section style={{ marginBottom: '2rem', display: 'flex', gap: '2rem' }}>
          <Stat label="Games Today" value={stats.games_today} />
          <Stat label="Games This Month" value={stats.games_month} />
          <Stat label="Unique Players Today" value={stats.unique_players_today} />
        </section>
      )}
      <section>
        <h2 style={{ marginBottom: '0.75rem', fontSize: '1.1rem' }}>Leaderboard</h2>
        {tournamentMeta && (
          <p style={{ color: '#9aa0a6', fontSize: 14, marginBottom: '0.75rem' }}>
            Tournament: <strong style={{ color: '#e8eaed' }}>{tournamentMeta.name}</strong>
            {' '}({formatTournamentWindow(tournamentMeta)})
          </p>
        )}
        <LeaderboardFilterBar
          variant="admin"
          filters={filters}
          onChange={onFiltersChange}
          style={{ marginBottom: '1rem' }}
        />
        <div style={{ marginBottom: '0.75rem' }}>
          <button style={btn} type="button" onClick={load}>Refresh</button>
        </div>
        <LeaderboardTable
          rows={leaderboard}
          board={filters.board}
          emptyMessage="No plays match this tournament window and filters."
        />
      </section>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ background: '#1a1d27', padding: '1rem 1.5rem', borderRadius: 12 }}>
      <div style={{ color: '#9aa0a6', fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{value}</div>
    </div>
  )
}

const btn = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
