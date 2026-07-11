export default function GameHealthTile({ game, status, lastChecked }) {
  const colors = { running: '#51cf66', idle: '#fcc419', down: '#ff6b6b' }
  const color = colors[status] || colors.down
  return (
    <div style={{ background: '#1a1d27', borderRadius: 12, padding: '1rem', border: `2px solid ${color}`, textAlign: 'center' }}>
      <div style={{ fontSize: 13, color: '#9aa0a6', textTransform: 'uppercase' }}>{game}</div>
      <div style={{ fontSize: '1.25rem', fontWeight: 700, color, marginTop: 4 }}>{status}</div>
      {lastChecked && <div style={{ fontSize: 11, color: '#6c757d', marginTop: 4 }}>{lastChecked}</div>}
    </div>
  )
}
