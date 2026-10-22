import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  GAMES,
  PERIODS,
  PLAY_MODES,
  DIFFICULTIES,
  TWO_CARD_OPTIONS,
  defaultLeaderboardFilters,
  boardToTournamentType,
  applyBoardTeamSizeDefault,
} from '../leaderboardQuery'

const select = {
  padding: '0.5rem',
  borderRadius: 6,
  border: '1px solid #2a2d3a',
  background: '#0f1117',
  color: '#e8eaed',
  fontSize: 13,
}
const tab = {
  padding: '0.5rem 1rem',
  background: '#1a1d27',
  color: '#9aa0a6',
  border: '1px solid #2a2d3a',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: 13,
}
const tabActive = { ...tab, background: '#3b5bdb', color: '#fff', borderColor: '#3b5bdb' }
const chip = {
  padding: '0.35rem 0.75rem',
  background: '#2b3a8c',
  color: '#fff',
  border: 'none',
  borderRadius: 999,
  cursor: 'pointer',
  fontSize: 12,
}
const resetBtn = { ...tab, marginLeft: 'auto' }

export default function LeaderboardFilterBar({ variant = 'admin', filters, onChange, style }) {
  const [companies, setCompanies] = useState([])
  const [groups, setGroups] = useState([])
  const [tournaments, setTournaments] = useState([])
  const [activeGlobals, setActiveGlobals] = useState({ solo: null, team: null })

  const isPublic = variant === 'public'
  const board = filters.board || 'individual'
  const tType = boardToTournamentType(board)
  const activeGlobal = tType === 'team' ? activeGlobals.team : activeGlobals.solo

  useEffect(() => {
    api('/companies').then(setCompanies).catch(() => setCompanies([]))
    api('/tournaments/active').then(setActiveGlobals).catch(() => setActiveGlobals({ solo: null, team: null }))
  }, [])

  useEffect(() => {
    const status = 'active'
    api(`/tournaments?status=${status}&type=${tType}`)
      .then(setTournaments)
      .catch(() => setTournaments([]))
  }, [tType])

  useEffect(() => {
    if (!filters.companyId) {
      setGroups([])
      return
    }
    api(`/groups?company_id=${filters.companyId}`)
      .then(setGroups)
      .catch(() => setGroups([]))
  }, [filters.companyId])

  const patch = partial => onChange({ ...filters, ...partial, offset: partial.offset ?? 0 })

  const setBoard = nextBoard => {
    onChange(applyBoardTeamSizeDefault(filters, nextBoard))
  }

  const reset = () => {
    const base = defaultLeaderboardFilters(variant)
    if (board === 'team') {
      onChange({ ...base, board: 'team', minSize: 2, sizeTouched: false })
    } else {
      onChange(base)
    }
  }

  const playModes = filters.game === 'laser'
    ? PLAY_MODES.filter(m => m.key !== 'team_battle')
    : PLAY_MODES

  const showTeamSizeChip = board === 'team' && String(filters.minSize) === '2' && !filters.sizeTouched

  const companyNameById = id => companies.find(c => String(c.id) === String(id))?.name

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, ...style }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {['individual', 'team'].map(b => (
          <button key={b} type="button" style={board === b ? tabActive : tab} onClick={() => setBoard(b)}>
            {b === 'individual' ? 'Individual' : 'Team'}
          </button>
        ))}

        <select
          style={select}
          value={filters.tournamentId}
          onChange={e => patch({ tournamentId: e.target.value })}
          title="Tournament window (empty = active global default)"
        >
          <option value="">
            Default — {activeGlobal?.name || 'active global'}
          </option>
          {tournaments.map(t => {
            const tag = t.scope === 'company' && t.company_id
              ? ` (${companyNameById(t.company_id) || `company #${t.company_id}`})`
              : ''
            return (
              <option key={t.id} value={t.id}>
                {t.name}{tag}
              </option>
            )
          })}
        </select>

        {(isPublic ? PERIODS : PERIODS).map(p => (
          isPublic ? (
            <button
              key={p.key}
              type="button"
              style={filters.period === p.key ? tabActive : tab}
              onClick={() => patch({ period: p.key })}
            >
              {p.label}
            </button>
          ) : null
        ))}

        {!isPublic && (
          <select style={select} value={filters.period} onChange={e => patch({ period: e.target.value })}>
            {PERIODS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
          </select>
        )}

        {isPublic ? (
          GAMES.map(g => (
            <button
              key={g.key}
              type="button"
              style={filters.game === g.key ? tabActive : tab}
              onClick={() => patch({ game: g.key, playMode: g.key === 'laser' && filters.playMode === 'team_battle' ? '' : filters.playMode })}
            >
              {g.label}
            </button>
          ))
        ) : (
          <select style={select} value={filters.game} onChange={e => {
            const game = e.target.value
            patch({
              game,
              playMode: game === 'laser' && filters.playMode === 'team_battle' ? '' : filters.playMode,
            })
          }}>
            {GAMES.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
          </select>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          style={{ ...select, minWidth: 140 }}
          value={filters.companyId}
          onChange={e => patch({ companyId: e.target.value, groupId: '' })}
        >
          <option value="">All companies</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {filters.companyId && groups.length > 0 && (
          <select style={select} value={filters.groupId} onChange={e => patch({ groupId: e.target.value })}>
            <option value="">All groups</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        )}

        <select style={select} value={filters.playMode} onChange={e => patch({ playMode: e.target.value })}>
          {playModes.map(m => <option key={m.key || 'all'} value={m.key}>{m.label}</option>)}
        </select>

        <label style={{ color: '#9aa0a6', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
          Min size
          <input
            type="number"
            min={0}
            style={{ ...select, width: 56 }}
            value={filters.minSize}
            onChange={e => patch({ minSize: e.target.value, sizeTouched: true })}
          />
        </label>
        <label style={{ color: '#9aa0a6', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
          Max size
          <input
            type="number"
            min={0}
            style={{ ...select, width: 56 }}
            value={filters.maxSize}
            onChange={e => patch({ maxSize: e.target.value, sizeTouched: true })}
          />
        </label>

        <select style={select} value={filters.twoCard} onChange={e => patch({ twoCard: e.target.value })}>
          {TWO_CARD_OPTIONS.map(o => <option key={o.key || 'any'} value={o.key}>{o.label}</option>)}
        </select>

        <select style={select} value={filters.difficulty} onChange={e => patch({ difficulty: e.target.value })}>
          {DIFFICULTIES.map(d => <option key={d.key || 'all'} value={d.key}>{d.label}</option>)}
        </select>

        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          <input
            type="checkbox"
            checked={filters.includeArchived}
            onChange={e => patch({ includeArchived: e.target.checked })}
            style={{ marginRight: 6 }}
          />
          Include archived groups
        </label>

        {showTeamSizeChip && (
          <button
            type="button"
            style={chip}
            title="Remove default team size filter"
            onClick={() => patch({ minSize: '', sizeTouched: true })}
          >
            Teams of 2+ ✕ (show all)
          </button>
        )}

        <button type="button" style={resetBtn} onClick={reset}>Reset filters</button>
      </div>
    </div>
  )
}
