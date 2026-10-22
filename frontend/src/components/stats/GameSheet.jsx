import { GAMES, formatPlayMode } from '../../leaderboardQuery'
import { formatScore, formatAvg, formatCount } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import SparkBar from './SparkBar'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { PlayerLink, GroupLink } from './EntityLinks'
import GameHealthTile from '../GameHealthTile'

function gameLabel(key) {
  return GAMES.find(g => g.key === key)?.label || key
}

function modeLabel(mode) {
  if (!mode) return '— (older / guests)'
  return formatPlayMode(mode) || mode
}

export default function GameSheet({ data }) {
  const vol = data.volume || {}
  const health = data.health || {}

  const tiles = [
    { label: 'Team plays', value: formatCount(vol.team_plays), hint: 'incl. guests' },
    { label: 'Shares', value: formatCount(vol.shares) },
    { label: 'Matches', value: formatCount(vol.matches) },
    { label: 'Unique players', value: formatCount(vol.unique_players) },
    { label: 'Unique groups', value: formatCount(vol.unique_groups) },
    { label: 'Avg time used', value: formatAvg(vol.avg_time_used) },
    { label: 'Avg roster size', value: formatAvg(vol.avg_roster_size) },
  ]

  return (
    <>
      <div style={{ maxWidth: 220, marginBottom: '1rem' }}>
        <GameHealthTile game={gameLabel(data.game)} status={health.status} lastChecked={health.last_checked} />
      </div>
      <StatTiles tiles={tiles} />

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Volume per day</h2>
        <SparkBar points={vol.per_day || []} />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>By mode</h2>
        <MiniTable
          rows={data.by_mode || []}
          columns={[
            { key: 'play_mode', label: 'Mode', render: r => modeLabel(r.play_mode) },
            { key: 'plays', label: 'Plays' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>By difficulty</h2>
        <MiniTable
          rows={data.by_difficulty || []}
          empty="No difficulty breakdown."
          columns={[
            { key: 'difficulty', label: 'Difficulty', render: r => r.difficulty || '—' },
            { key: 'plays', label: 'Plays' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Results (raw)</h2>
        <MiniTable
          rows={data.results || []}
          empty="No results."
          columns={[
            { key: 'result', label: 'Result code' },
            { key: 'plays', label: 'Plays' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Top players (shares)</h2>
        <MiniTable
          rows={data.top_players || []}
          empty="No top players."
          columns={[
            {
              key: 'player_name',
              label: 'Player',
              render: r => (
                <PlayerLink
                  id={r.player_id}
                  name={r.player_name}
                  fallback={r.card_id}
                />
              ),
            },
            { key: 'score', label: 'Score', render: r => formatScore(r.score) },
            { key: 'game', label: 'Game' },
            { key: 'played_at', label: 'When' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Top teams</h2>
        <MiniTable
          rows={data.top_teams || []}
          empty="No attributed team rows."
          columns={[
            {
              key: 'group_name',
              label: 'Group',
              render: r => <GroupLink id={r.group_id} name={r.group_name} />,
            },
            { key: 'score', label: 'Score', render: r => formatScore(r.score) },
            { key: 'played_at', label: 'When' },
          ]}
        />
      </div>
    </>
  )
}
