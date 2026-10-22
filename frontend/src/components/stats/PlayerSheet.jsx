import { formatPlayMode } from '../../leaderboardQuery'
import { formatMinutes, formatScore, formatAvg, formatCount } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { GroupLink, CompanyLink, SessionLink, TournamentLink } from './EntityLinks'

function modeLabel(mode) {
  if (!mode) return '— (older plays)'
  return formatPlayMode(mode) || mode
}

export default function PlayerSheet({ data }) {
  const p = data.player
  const plays = data.plays || {}
  const pt = data.play_time || {}
  const visits = data.visits || {}

  const tiles = [
    { label: 'Share plays', value: formatCount(plays.count) },
    { label: 'Best share', value: formatScore(plays.best) },
    { label: 'Avg share', value: formatAvg(plays.avg) },
    { label: 'Play time earned', value: formatMinutes(pt.earned_min) },
    { label: 'Visits led', value: formatCount(visits.led) },
    { label: 'On roster', value: formatCount(visits.on_roster) },
  ]

  return (
    <>
      <StatTiles tiles={tiles} />
      <div style={sectionCard}>
        <h2 style={sectionTitle}>Profile</h2>
        {p.company && (
          <p style={muted}>
            Company: <CompanyLink id={p.company.id} name={p.company.name} />
          </p>
        )}
        {p.groups?.length > 0 && (
          <p style={muted}>
            Groups:{' '}
            {p.groups.map(g => (
              <span key={g.id} style={{ marginRight: 8 }}>
                <GroupLink id={g.id} name={g.name} />
                {g.archived ? ' (archived)' : ''}
              </span>
            ))}
          </p>
        )}
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Play time</h2>
        <p style={muted}>
          Earned {formatMinutes(pt.earned_min)} · Adjust net {formatMinutes(pt.adjust_net_min)} · Refund {formatMinutes(pt.refund_min)}
        </p>
        <MiniTable
          empty="No ledger events."
          rows={pt.events || []}
          columns={[
            { key: 'earned_at', label: 'When' },
            { key: 'source', label: 'Source' },
            { key: 'minutes', label: 'Minutes', render: r => formatMinutes(r.minutes) },
            {
              key: 'session_id',
              label: 'Session',
              render: r => (r.session_id ? <SessionLink id={r.session_id} /> : '—'),
            },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Visits</h2>
        <p style={muted}>
          Last visit: {visits.last_visit_at || '—'}
        </p>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Plays by game / mode / roster size</h2>
        <MiniTable
          rows={plays.by_game || []}
          empty="No attributed plays in this window."
          columns={[
            { key: 'game', label: 'Game' },
            { key: 'plays', label: 'Plays' },
            { key: 'best', label: 'Best', render: r => formatScore(r.best) },
            { key: 'avg', label: 'Avg', render: r => formatAvg(r.avg) },
          ]}
        />
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={plays.by_mode || []}
            empty="—"
            columns={[
              { key: 'play_mode', label: 'Mode', render: r => modeLabel(r.play_mode) },
              { key: 'plays', label: 'Plays' },
            ]}
          />
        </div>
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={plays.by_size || []}
            empty="—"
            columns={[
              { key: 'n', label: 'Roster size' },
              { key: 'plays', label: 'Plays' },
            ]}
          />
        </div>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Tournaments</h2>
        <MiniTable
          rows={data.tournaments || []}
          empty="No tournament activity."
          columns={[
            { key: 'name', label: 'Tournament', render: r => <TournamentLink id={r.id} name={r.name} /> },
            { key: 'plays', label: 'Plays' },
            { key: 'best', label: 'Best', render: r => formatScore(r.best) },
            { key: 'best_rank', label: 'Best rank' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Recent plays</h2>
        <MiniTable
          rows={data.recent_plays || []}
          empty="No recent plays."
          columns={[
            { key: 'game', label: 'Game' },
            { key: 'level', label: 'Level' },
            { key: 'score', label: 'Score', render: r => formatScore(r.score) },
            { key: 'play_mode', label: 'Mode', render: r => modeLabel(r.play_mode) },
            { key: 'group_name', label: 'Group' },
            { key: 'played_at', label: 'When' },
          ]}
        />
      </div>
    </>
  )
}
