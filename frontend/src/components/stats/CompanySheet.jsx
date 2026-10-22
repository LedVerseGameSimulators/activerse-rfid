import { formatPlayMode } from '../../leaderboardQuery'
import { formatMinutes, formatScore, formatCount } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { PlayerLink, GroupLink, TournamentLink } from './EntityLinks'

function modeLabel(mode) {
  if (!mode) return '— (older plays)'
  return formatPlayMode(mode) || mode
}

export default function CompanySheet({ data }) {
  const plays = data.plays || {}
  const pt = data.play_time || {}
  const groups = data.groups || {}
  const members = data.members || {}

  const tiles = [
    { label: 'Members', value: formatCount(members.count) },
    { label: 'Active groups', value: formatCount(groups.active) },
    { label: 'Team plays', value: formatCount(plays.team_plays) },
    { label: 'Shares', value: formatCount(plays.shares) },
    { label: 'Unique players', value: formatCount(plays.unique_players) },
    { label: 'Visits', value: formatCount(data.visits?.count) },
    { label: 'Play time', value: formatMinutes(pt.earned_min) },
  ]

  return (
    <>
      <StatTiles tiles={tiles} />
      <div style={sectionCard}>
        <h2 style={sectionTitle}>Plays</h2>
        <p style={muted}>
          Best team {formatScore(plays.best_team_score)} · Best share {formatScore(plays.best_share)}
        </p>
        <MiniTable
          rows={plays.by_game || []}
          empty="No plays (stamped company_id only)."
          columns={[
            { key: 'game', label: 'Game' },
            { key: 'team_plays', label: 'Team plays' },
            { key: 'shares', label: 'Shares' },
          ]}
        />
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={plays.by_mode || []}
            columns={[
              { key: 'play_mode', label: 'Mode', render: r => modeLabel(r.play_mode) },
              { key: 'plays', label: 'Team plays' },
            ]}
          />
        </div>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Play time</h2>
        <p style={muted}>
          Earned {formatMinutes(pt.earned_min)} · Adjust {formatMinutes(pt.adjust_net_min)} · Refund {formatMinutes(pt.refund_min)}
        </p>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Groups</h2>
        <p style={muted}>{groups.archived ?? 0} archived</p>
        <MiniTable
          rows={groups.list || []}
          empty="No groups."
          columns={[
            { key: 'name', label: 'Group', render: r => <GroupLink id={r.id} name={r.name} /> },
            { key: 'kind', label: 'Kind' },
            { key: 'member_count', label: 'Members' },
            { key: 'archived', label: 'Archived', render: r => (r.archived ? 'Yes' : '') },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Top players</h2>
        <MiniTable
          rows={data.top_players || []}
          empty="No players in window."
          columns={[
            { key: 'name', label: 'Player', render: r => <PlayerLink id={r.player_id} name={r.name} /> },
            { key: 'plays', label: 'Plays' },
            { key: 'best_share', label: 'Best', render: r => formatScore(r.best_share) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Top groups</h2>
        <MiniTable
          rows={data.top_groups || []}
          empty="No groups in window."
          columns={[
            { key: 'name', label: 'Group', render: r => <GroupLink id={r.group_id} name={r.name} /> },
            { key: 'plays', label: 'Plays' },
            { key: 'best', label: 'Best', render: r => formatScore(r.best) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Tournaments</h2>
        <MiniTable
          rows={data.tournaments || []}
          empty="No company tournaments."
          columns={[
            { key: 'name', label: 'Name', render: r => <TournamentLink id={r.id} name={r.name} /> },
            { key: 'type', label: 'Type' },
            { key: 'plays', label: 'Plays' },
          ]}
        />
      </div>
    </>
  )
}
