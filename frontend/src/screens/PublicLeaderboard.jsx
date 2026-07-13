import { useState, useEffect } from 'react'
import { api } from '../api'

const GAMES = [
  { key: 'all', label: 'All Games' }, { key: 'hoops', label: 'Hoops' },
  { key: 'laser', label: 'Laser Trap' }, { key: 'climb', label: 'Climb' },
  { key: 'grid', label: 'Floor Is Lava' }, { key: 'led_hex', label: 'LED Hexagon' },
]

export default function PublicLeaderboard() {
  const [game, setGame] = useState('all')
  const [period, setPeriod] = useState('today')
  const [rows, setRows] = useState([])

  const load = async () => {
    const data = await api(`/dashboard/leaderboard?game=${game}&period=${period}&limit=20`)
    setRows(data)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)   // auto-refresh for a lobby screen
    return () => clearInterval(t)
  }, [game, period])

  return (
    <div style={page}>
      <h1 style={title}>🏆 Leaderboard</h1>
      <div style={filters}>
        {GAMES.map(g => (
          <button key={g.key} style={game === g.key ? tabActive : tab} onClick={() => setGame(g.key)}>
            {g.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        {['today', 'week', 'month', 'alltime'].map(p => (
          <button key={p} style={period === p ? tabActive : tab} onClick={() => setPeriod(p)}>
            {p === 'alltime' ? 'All Time' : p[0].toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>
      <div style={rankGrid}>
        {rows.map((r, i) => (
          <div key={i} style={row}>
            <div style={rank}>{i + 1}</div>
            <div style={{ flex: 1 }}>
              <div style={playerName}>{r.player_name || r.card_id || 'Guest'}</div>
              <div style={gameLine}>{r.game} · {r.level}</div>
            </div>
            <div style={scoreVal}>{r.score}</div>
          </div>
        ))}
        {rows.length === 0 && <p style={{ color: '#9aa0a6', textAlign: 'center' }}>No scores yet.</p>}
      </div>
    </div>
  )
}

const page = { minHeight: '100vh', background: '#06060c', color: '#e8eaed', padding: '2rem', fontFamily: 'system-ui, sans-serif' }
const title = { fontSize: '2.5rem', textAlign: 'center', marginBottom: '1.5rem' }
const filters = { display: 'flex', gap: 8, marginBottom: '2rem', flexWrap: 'wrap' }
const tab = { padding: '0.5rem 1rem', background: '#1a1d27', color: '#9aa0a6', border: '1px solid #2a2d3a', borderRadius: 8, cursor: 'pointer' }
const tabActive = { ...tab, background: '#3b5bdb', color: '#fff', borderColor: '#3b5bdb' }
const rankGrid = { maxWidth: 700, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 8 }
const row = { display: 'flex', alignItems: 'center', gap: 16, background: '#1a1d27', padding: '1rem 1.5rem', borderRadius: 12 }
const rank = { fontSize: '1.5rem', fontWeight: 700, color: '#3b5bdb', width: 40 }
const playerName = { fontSize: '1.1rem', fontWeight: 600 }
const gameLine = { fontSize: 13, color: '#9aa0a6' }
const scoreVal = { fontSize: '1.75rem', fontWeight: 700 }
