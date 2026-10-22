import { GAMES, PERIODS, PLAY_MODES } from '../../leaderboardQuery'
import DateRange from './DateRange'

const select = {
  padding: '0.5rem',
  borderRadius: 6,
  border: '1px solid #2a2d3a',
  background: '#0f1117',
  color: '#e8eaed',
  fontSize: 13,
}

/**
 * @param {'full'|'tournament'|'game'} variant
 */
export default function StatFilterBar({ filters, onChange, variant = 'full', showIncludeArchived = true }) {
  const patch = partial => onChange({ ...filters, ...partial })

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        alignItems: 'flex-end',
        marginBottom: '1.25rem',
        padding: '0.75rem',
        background: '#0f1117',
        borderRadius: 8,
        border: '1px solid #2a2d3a',
      }}
    >
      <label style={{ color: '#9aa0a6', fontSize: 13 }}>
        Period
        <select
          style={{ ...select, display: 'block', marginTop: 4 }}
          value={filters.period}
          onChange={e => patch({ period: e.target.value })}
        >
          {PERIODS.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
      </label>
      {variant !== 'game' && (
        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          Game
          <select
            style={{ ...select, display: 'block', marginTop: 4 }}
            value={filters.game}
            onChange={e => patch({ game: e.target.value })}
          >
            {GAMES.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
          </select>
        </label>
      )}
      {variant === 'full' && (
        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          Mode
          <select
            style={{ ...select, display: 'block', marginTop: 4 }}
            value={filters.playMode}
            onChange={e => patch({ playMode: e.target.value })}
          >
            {PLAY_MODES.map(m => <option key={m.key || 'all'} value={m.key}>{m.label}</option>)}
          </select>
        </label>
      )}
      {variant === 'game' && (
        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          Mode
          <select
            style={{ ...select, display: 'block', marginTop: 4 }}
            value={filters.playMode}
            onChange={e => patch({ playMode: e.target.value })}
          >
            {PLAY_MODES.map(m => <option key={m.key || 'all'} value={m.key}>{m.label}</option>)}
          </select>
        </label>
      )}
      {variant !== 'tournament' && (
        <DateRange
          dateFrom={filters.dateFrom}
          dateTo={filters.dateTo}
          onChange={partial => patch(partial)}
        />
      )}
      {showIncludeArchived && variant === 'full' && (
        <label style={{ color: '#9aa0a6', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 6 }}>
          <input
            type="checkbox"
            checked={filters.includeArchived}
            onChange={e => patch({ includeArchived: e.target.checked })}
          />
          Include archived groups
        </label>
      )}
    </div>
  )
}
