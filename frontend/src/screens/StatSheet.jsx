import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { GAMES } from '../leaderboardQuery'
import { defaultStatsFilters, buildStatsQuery, buildTournamentStatsQuery } from '../statsQuery'
import StatFilterBar from '../components/stats/StatFilterBar'
import PlayerSheet from '../components/stats/PlayerSheet'
import SessionSheet from '../components/stats/SessionSheet'
import GroupSheet from '../components/stats/GroupSheet'
import CompanySheet from '../components/stats/CompanySheet'
import GameSheet from '../components/stats/GameSheet'
import TournamentSheet from '../components/stats/TournamentSheet'
import { muted, btnLink } from '../components/stats/statsTheme'

const VALID_KINDS = new Set(['player', 'session', 'group', 'company', 'game', 'tournament'])

function normalizeError(message) {
  const m = (message || '').toLowerCase()
  if (m.includes('not found') || m.includes('unknown game')) return 'not found'
  return message || 'Error loading stats'
}

function titleFor(kind, data, id) {
  if (!data) return 'Stats'
  switch (kind) {
    case 'player':
      return data.player?.name || `Player #${id}`
    case 'session':
      return `Session #${data.session?.id ?? id}`
    case 'group':
      return data.group?.name || `Group #${id}`
    case 'company':
      return data.company?.name || `Company #${id}`
    case 'game':
      return GAMES.find(g => g.key === data.game)?.label || data.game || id
    case 'tournament':
      return data.tournament?.name || `Tournament #${id}`
    default:
      return 'Stats'
  }
}

export default function StatSheet() {
  const { kind, id } = useParams()
  const [filters, setFilters] = useState(defaultStatsFilters)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const validKind = VALID_KINDS.has(kind)

  const load = useCallback(async () => {
    if (!validKind || !id) {
      setError('not found')
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      let path = `/stats/${kind}/${encodeURIComponent(id)}`
      if (kind === 'session') {
        // no query params
      } else if (kind === 'tournament') {
        path += `?${buildTournamentStatsQuery(filters)}`
      } else if (kind === 'game') {
        path += `?${buildStatsQuery(filters, { includeGame: false })}`
      } else {
        path += `?${buildStatsQuery(filters)}`
      }
      setData(await api(path))
    } catch (e) {
      setData(null)
      setError(normalizeError(e.message))
    } finally {
      setLoading(false)
    }
  }, [kind, id, filters, validKind])

  useEffect(() => {
    load()
  }, [load])

  const filterVariant = kind === 'tournament' ? 'tournament' : kind === 'game' ? 'game' : 'full'
  const showFilters = kind !== 'session'

  return (
    <div>
      <p style={{ marginBottom: 8 }}>
        <Link to="/dashboard" style={{ color: '#74c0fc' }}>← Back</Link>
      </p>
      <h1 style={{ marginBottom: '0.25rem' }}>{titleFor(kind, data, id)}</h1>
      <p style={{ ...muted, marginBottom: '1rem' }}>Stat sheet · {kind}</p>

      {showFilters && validKind && (
        <StatFilterBar
          filters={filters}
          onChange={setFilters}
          variant={filterVariant}
          showIncludeArchived={kind === 'player' || kind === 'group' || kind === 'company'}
        />
      )}

      {loading && <p style={muted}>Loading…</p>}
      {!loading && error && (
        <p style={{ color: error === 'not found' ? '#9aa0a6' : '#ff6b6b' }}>
          {error === 'not found' ? 'not found' : error}
        </p>
      )}
      {!loading && !error && data && (
        <>
          {kind === 'player' && <PlayerSheet data={data} />}
          {kind === 'session' && <SessionSheet data={data} />}
          {kind === 'group' && <GroupSheet data={data} />}
          {kind === 'company' && <CompanySheet data={data} />}
          {kind === 'game' && <GameSheet data={data} />}
          {kind === 'tournament' && <TournamentSheet data={data} />}
        </>
      )}

      {!loading && !error && (
        <button type="button" style={{ ...btnLink, marginTop: 8 }} onClick={load}>
          Refresh
        </button>
      )}
    </div>
  )
}
