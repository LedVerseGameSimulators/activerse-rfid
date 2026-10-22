import { formatPlayMode } from '../../leaderboardQuery'
import { formatMinutes, formatScore } from '../../statsFormat'
import StatTiles from './StatTiles'
import MiniTable from './MiniTable'
import { sectionCard, sectionTitle, muted } from './statsTheme'
import { PlayerLink, GroupLink, CompanyLink } from './EntityLinks'

export default function SessionSheet({ data }) {
  const s = data.session || {}
  const plays = data.plays || {}

  const tiles = [
    { label: 'Status', value: s.status || '—' },
    { label: 'Minutes left', value: s.minutes_remaining != null ? formatMinutes(s.minutes_remaining) : '—' },
    { label: 'Team plays', value: plays.count ?? 0 },
    { label: 'Best team score', value: formatScore(plays.best_team_score) },
    { label: 'Total team score', value: formatScore(plays.total_team_score) },
  ]

  return (
    <>
      <StatTiles tiles={tiles} />
      <div style={sectionCard}>
        <h2 style={sectionTitle}>Session</h2>
        <p style={muted}>
          Payer: <PlayerLink id={s.player_id} name={s.payer_name} fallback={s.card_id} />
          {s.group_id && (
            <> · Group: <GroupLink id={s.group_id} name={s.group_name} /></>
          )}
          {s.company_id && (
            <> · <CompanyLink id={s.company_id} name={s.company_name} /></>
          )}
        </p>
        <p style={muted}>
          Issued {s.issued_at || '—'} · Expires {s.expiry_at || '—'}
          {s.closed_at ? ` · Closed ${s.closed_at}` : ''}
        </p>
        <p style={muted}>Duration booked: {formatMinutes(s.duration_min)}</p>
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Roster timeline</h2>
        <p style={{ ...muted, marginBottom: 8 }}>
          Join times come from play-time ledger (visit start / roster join). Removals are not recorded.
        </p>
        <MiniTable
          rows={data.roster || []}
          empty="No roster members."
          columns={[
            {
              key: 'name',
              label: 'Player',
              render: r => <PlayerLink id={r.player_id} name={r.name} />,
            },
            { key: 'is_payer', label: 'Payer', render: r => (r.is_payer ? 'Yes' : '') },
            { key: 'joined_at', label: 'Joined' },
            { key: 'joined_via', label: 'Via' },
            { key: 'earned_min', label: 'Earned', render: r => formatMinutes(r.earned_min) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Adjustments</h2>
        <MiniTable
          rows={data.adjustments || []}
          empty="No adjustments."
          columns={[
            { key: 'adjusted_at', label: 'When' },
            { key: 'delta_min', label: 'Δ min' },
            { key: 'adjustment_mode', label: 'Mode' },
            { key: 'balance_delta_min', label: 'Balance Δ' },
            { key: 'reason', label: 'Reason' },
            { key: 'adjusted_by', label: 'By' },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Ledger</h2>
        <MiniTable
          rows={data.ledger || []}
          empty="No ledger rows."
          columns={[
            { key: 'earned_at', label: 'When' },
            {
              key: 'player_id',
              label: 'Player',
              render: r => <PlayerLink id={r.player_id} />,
            },
            { key: 'source', label: 'Source' },
            { key: 'minutes', label: 'Minutes', render: r => formatMinutes(r.minutes) },
          ]}
        />
      </div>

      <div style={sectionCard}>
        <h2 style={sectionTitle}>Plays this session</h2>
        <MiniTable
          rows={plays.by_member || []}
          empty="No member shares."
          columns={[
            { key: 'name', label: 'Player', render: r => <PlayerLink id={r.player_id} name={r.name} /> },
            { key: 'plays', label: 'Plays' },
            { key: 'best_share', label: 'Best', render: r => formatScore(r.best_share) },
            { key: 'total_share', label: 'Total', render: r => formatScore(r.total_share) },
          ]}
        />
        <div style={{ marginTop: 12 }}>
          <MiniTable
            rows={plays.rows || []}
            empty="No team plays."
            columns={[
              { key: 'game', label: 'Game' },
              {
                key: 'play_mode',
                label: 'Mode',
                render: r => formatPlayMode(r.play_mode) || '—',
              },
              { key: 'roster_size_at_play', label: 'Size' },
              { key: 'score', label: 'Score', render: r => formatScore(r.score) },
              { key: 'played_at', label: 'When' },
            ]}
          />
        </div>
      </div>
    </>
  )
}
