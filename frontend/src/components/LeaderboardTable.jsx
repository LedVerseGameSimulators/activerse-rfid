import { Link } from 'react-router-dom'
import { formatPlayMode } from '../leaderboardQuery'

export default function LeaderboardTable({ rows, board = 'individual', emptyMessage }) {
  if (!rows?.length) {
    return <p style={{ color: '#9aa0a6' }}>{emptyMessage || 'No scores yet.'}</p>
  }

  const showMembers = board === 'team' || rows.some(r => r.member_count != null)

  const headers = ['Rank', board === 'team' ? 'Group / Team' : 'Player', 'Mode', 'Size', 'Group']
  if (showMembers) headers.push('Members')
  headers.push('Game', 'Level', 'Score', 'When')

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
          {headers.map(h => (
            <th key={h} style={{ padding: '0.5rem', color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const rank = r.rank ?? i + 1
          const plainName = board === 'team'
            ? (r.group_name || r.player_name || r.card_id || 'Team')
            : (r.player_name || r.card_id || `#${r.player_id || '?'}`)
          const name = board === 'team'
            ? (r.group_id
              ? <Link to={`/stats/group/${r.group_id}`} style={{ color: '#74c0fc', textDecoration: 'none' }}>{plainName}</Link>
              : plainName)
            : (r.player_id
              ? <Link to={`/stats/player/${r.player_id}`} style={{ color: '#74c0fc', textDecoration: 'none' }}>{plainName}</Link>
              : plainName)
          const size = r.roster_size_at_play ?? r.member_count
          const mode = formatPlayMode(r.play_mode) || '—'
          return (
            <tr key={r.id ?? i} style={{ borderBottom: '1px solid #1a1d27' }}>
              <td style={td}>{rank}</td>
              <td style={td}>{name}</td>
              <td style={td}>{mode}</td>
              <td style={td}>{size != null ? size : '—'}</td>
              <td style={td}>{r.group_name || '—'}</td>
              {showMembers && (
                <td style={td}>{r.member_count != null ? r.member_count : '—'}</td>
              )}
              <td style={td}>{r.game}</td>
              <td style={td}>{r.level}</td>
              <td style={{ ...td, fontWeight: 600 }}>{r.score}</td>
              <td style={{ ...td, color: '#9aa0a6', fontSize: 13 }}>{r.played_at}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

const td = { padding: '0.5rem' }
