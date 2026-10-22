import { formatPlayMode } from '../../leaderboardQuery'
import { formatMinutes, formatScore, formatAvg, formatCount } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { PlayerLink, CompanyLink, SessionLink, TournamentLink } from './EntityLinks'

function modeLabel(mode) {
  if (!mode) return '— (older plays)'
  return formatPlayMode(mode) || mode
}

export default function GroupSheet({ data }) {
  const g = data.group || {}
  const tp = data.team_plays || {}
  const h2h = tp.head_to_head || {}
  const visits = data.visits || {}
  const pt = data.play_time || {}

  const h2hLabel = (() => {
    const wld = `${h2h.wins ?? 0}-${h2h.losses ?? 0}-${h2h.draws ?? 0}`
    const unresolved = h2h.unresolved_matches ?? tp.unresolved_matches
    if (unresolved != null && unresolved !== '') {
      return `${wld} (${unresolved} unresolved)`
    }
    return wld
  })()

  const tiles = [
    { label: 'Team plays', value: formatCount(tp.count) },
    { label: 'Best team', value: formatScore(tp.best) },
    { label: 'Avg team', value: formatAvg(tp.avg) },
    { label: 'Matches', value: formatCount(tp.matches) },
    { label: 'Head-to-head W-L-D', value: h2hLabel },
    { label: 'Visits', value: formatCount(visits.count) },
    { label: 'Play time', value: formatMinutes(pt.earned_min) },
  ]

  return (
    <>
      <StatTiles tiles={tiles} />
      <div style={sectionCard}>
        <h2 style={sectionTitle}>Group</h2>
        {g.company_id && (
          <p style={muted}>Company: <CompanyLink id={g.company_id} name={g.company_name} /></p>
        )}
        {g.archived_at && <p style={{ color: '#fcc419' }}>Archived {g.archived_at}</p>}
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Members</h2>
        <MiniTable
          rows={data.members || []}
          columns={[
            { key: 'name', label: 'Player', render: r => <PlayerLink id={r.player_id} name={r.name} /> },
            { key: 'is_leader', label: 'Leader', render: r => (r.is_leader ? 'Yes' : '') },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Visits</h2>
        <p style={muted}>
          {visits.count ?? 0} visits · {formatMinutes(visits.total_duration_min)} booked · Last {visits.last_visit_at || '—'}
        </p>
        <MiniTable
          rows={visits.sessions || []}
          empty="No visits."
          columns={[
            {
              key: 'id',
              label: 'Session',
              render: r => <SessionLink id={r.id} label={`#${r.id} (${r.payer || '—'})`} />,
            },
            { key: 'issued_at', label: 'Issued' },
            { key: 'closed_at', label: 'Closed' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Team plays</h2>
        <MiniTable
          rows={tp.by_game || []}
          empty="No team plays in window."
          columns={[
            { key: 'game', label: 'Game' },
            { key: 'plays', label: 'Plays' },
            { key: 'best', label: 'Best', render: r => formatScore(r.best) },
          ]}
        />
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={tp.by_mode || []}
            columns={[
              { key: 'play_mode', label: 'Mode', render: r => modeLabel(r.play_mode) },
              { key: 'plays', label: 'Plays' },
            ]}
          />
        </div>
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={tp.by_size || []}
            columns={[
              { key: 'n', label: 'Roster size' },
              { key: 'plays', label: 'Plays' },
            ]}
          />
        </div>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Member shares</h2>
        <MiniTable
          rows={data.member_shares || []}
          empty="No member shares."
          columns={[
            { key: 'name', label: 'Player', render: r => <PlayerLink id={r.player_id} name={r.name} /> },
            { key: 'plays', label: 'Plays' },
            { key: 'best_share', label: 'Best', render: r => formatScore(r.best_share) },
            { key: 'total_share', label: 'Total', render: r => formatScore(r.total_share) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Play time by player</h2>
        <p style={{ ...muted, marginBottom: 8 }}>
          Solo-issue visit_start rows without group_id are excluded from group rollups.
        </p>
        {pt.note && <p style={{ ...muted, fontStyle: 'italic', marginBottom: 8 }}>{pt.note}</p>}
        <MiniTable
          rows={pt.by_player || []}
          empty="No group play time."
          columns={[
            { key: 'player_id', label: 'Player', render: r => <PlayerLink id={r.player_id} /> },
            { key: 'earned_min', label: 'Earned', render: r => formatMinutes(r.earned_min) },
          ]}
        />
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
            {
              key: 'best_rank',
              label: 'Best rank in tournament',
              render: r => (r.best_rank != null ? r.best_rank : ''),
            },
          ]}
        />
      </div>
    </>
  )
}
