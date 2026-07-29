export default function LeaderboardTable({ rows }) {
  if (!rows?.length) return <p style={{ color: '#9aa0a6' }}>No scores yet.</p>

  const showMembers = rows.some(r => r.member_count != null)

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
          {['Rank', 'Player', ...(showMembers ? ['Members'] : []), 'Game', 'Level', 'Score', 'When'].map(h => (
            <th key={h} style={{ padding: '0.5rem', color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderBottom: '1px solid #1a1d27' }}>
            <td style={td}>{i + 1}</td>
            <td style={td}>{r.player_name || r.card_id || 'Anonymous'}</td>
            {showMembers && (
              <td style={td}>{r.member_count != null ? r.member_count : '—'}</td>
            )}
            <td style={td}>{r.game}</td>
            <td style={td}>{r.level}</td>
            <td style={{ ...td, fontWeight: 600 }}>{r.score}</td>
            <td style={{ ...td, color: '#9aa0a6', fontSize: 13 }}>{r.played_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const td = { padding: '0.5rem' }
