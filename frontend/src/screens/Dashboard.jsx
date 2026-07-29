import { useState, useEffect } from 'react'
import GameHealthTile from '../components/GameHealthTile'
import LeaderboardTable from '../components/LeaderboardTable'
import { api } from '../api'

export default function Dashboard() {
  const [health, setHealth] = useState([])
  const [leaderboard, setLeaderboard] = useState([])
  const [stats, setStats] = useState(null)
  const [game, setGame] = useState('all')
  const [period, setPeriod] = useState('alltime')
  const [board, setBoard] = useState('individual')

  const load = async () => {
    try {
      const [h, lb, st] = await Promise.all([
        api('/dashboard/health'),
        api(`/dashboard/leaderboard?game=${game}&period=${period}&limit=20&board=${board}`),
        api('/dashboard/stats'),
      ])
      setHealth(h)
      setLeaderboard(lb)
      setStats(st)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => { load() }, [game, period, board])

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>
      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Game Health</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
          {health.map(g => (
            <GameHealthTile key={g.game} game={g.game} status={g.status} lastChecked={g.last_checked} />
          ))}
        </div>
      </section>
      {stats && (
        <section style={{ marginBottom: '2rem', display: 'flex', gap: '2rem' }}>
          <Stat label="Games Today" value={stats.games_today} />
          <Stat label="Games This Month" value={stats.games_month} />
          <Stat label="Unique Players Today" value={stats.unique_players_today} />
        </section>
      )}
      <section>
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {['individual', 'team'].map(b => (
              <button
                key={b}
                style={board === b ? boardActive : boardBtn}
                onClick={() => setBoard(b)}
              >
                {b === 'individual' ? 'Individual' : 'Team'}
              </button>
            ))}
          </div>
          <select style={select} value={game} onChange={e => setGame(e.target.value)}>
            <option value="all">All Games</option>
            <option value="hoops">Hoops</option>
            <option value="laser">Laser Trap</option>
            <option value="climb">Climb</option>
            <option value="grid">Floor Is Lava</option>
            <option value="led_hex">LED Hexagon</option>
          </select>
          <select style={select} value={period} onChange={e => setPeriod(e.target.value)}>
            <option value="today">Today</option>
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="alltime">All Time</option>
          </select>
          <button style={btn} onClick={load}>Refresh</button>
        </div>
        <LeaderboardTable rows={leaderboard} />
      </section>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ background: '#1a1d27', padding: '1rem 1.5rem', borderRadius: 12 }}>
      <div style={{ color: '#9aa0a6', fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{value}</div>
    </div>
  )
}

const select = { padding: '0.5rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const boardBtn = { padding: '0.5rem 1rem', background: '#1a1d27', color: '#9aa0a6', border: '1px solid #2a2d3a', borderRadius: 6, cursor: 'pointer' }
const boardActive = { ...boardBtn, background: '#3b5bdb', color: '#fff', borderColor: '#3b5bdb' }
