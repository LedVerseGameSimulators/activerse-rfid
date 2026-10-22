import { formatTournamentWindow } from '../../leaderboardQuery'
import { formatScore, formatAvg, formatCount } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import SparkBar from './SparkBar'
import LeaderboardTable from '../LeaderboardTable'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { CompanyLink } from './EntityLinks'

export default function TournamentSheet({ data }) {
  const t = data.tournament || {}
  const totals = data.totals || {}
  const board = t.type === 'team' ? 'team' : 'individual'

  const tiles = [
    { label: 'Plays', value: formatCount(totals.plays) },
    { label: 'Entrants', value: formatCount(totals.entrants) },
    {
      label: t.type === 'team' ? 'Unique groups' : 'Unique players',
      value: formatCount(t.type === 'team' ? totals.unique_groups : totals.unique_players),
    },
    { label: 'Best score', value: formatScore(totals.best_score) },
    { label: 'Avg score', value: formatAvg(totals.avg_score) },
  ]

  return (
    <>
      <StatTiles tiles={tiles} />
      <div style={sectionCard}>
        <h2 style={sectionTitle}>Tournament</h2>
        <p style={muted}>
          {t.type} · {t.scope}
          {t.scope === 'company' && t.company_id && (
            <> · <CompanyLink id={t.company_id} name={t.company_name} /></>
          )}
        </p>
        <p style={muted}>{formatTournamentWindow(t)} · Status {t.status}</p>
        {data.window && (
          <p style={{ fontSize: 12, color: '#6c757d' }}>
            Effective window: {data.window.from || 'open'} → {data.window.to_exclusive || 'open'}
          </p>
        )}
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>By game</h2>
        <MiniTable
          rows={data.by_game || []}
          columns={[
            { key: 'game', label: 'Game' },
            { key: 'plays', label: 'Plays' },
            { key: 'best', label: 'Best', render: r => formatScore(r.best) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>By mode</h2>
        <MiniTable
          rows={data.by_mode || []}
          columns={[
            { key: 'play_mode', label: 'Mode', render: r => (r.play_mode || '— (older)') },
            { key: 'plays', label: 'Plays' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>By day</h2>
        <SparkBar points={data.by_day || []} />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Top plays</h2>
        <LeaderboardTable rows={data.top || []} board={board} emptyMessage="No plays in this window." />
      </div>
    </>
  )
}
