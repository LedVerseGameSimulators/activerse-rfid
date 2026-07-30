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
  const [board, setBoard] = useState('individual')
  const [companyId, setCompanyId] = useState('')
  const [groupId, setGroupId] = useState('')
  const [companies, setCompanies] = useState([])
  const [groups, setGroups] = useState([])
  const [rows, setRows] = useState([])

  const load = async () => {
    const companyQ = companyId ? `&company_id=${companyId}` : ''
    const groupQ = groupId ? `&group_id=${groupId}` : ''
    const [data, cos] = await Promise.all([
      api(`/dashboard/leaderboard?game=${game}&period=${period}&limit=20&board=${board}${companyQ}${groupQ}`),
      api('/companies'),
    ])
    setRows(data)
    setCompanies(cos)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [game, period, board, companyId, groupId])

  useEffect(() => {
    setGroupId('')
    if (!companyId) { setGroups([]); return }
    api(`/groups?company_id=${companyId}`).then(setGroups).catch(() => setGroups([]))
  }, [companyId])

  return (
    <div style={page}>
      <h1 style={title}>Leaderboard</h1>
      <div style={filters}>
        {['individual', 'team'].map(b => (
          <button key={b} style={board === b ? tabActive : tab} onClick={() => setBoard(b)}>
            {b === 'individual' ? 'Individual' : 'Team'}
          </button>
        ))}
        <select
          style={{ ...tab, background: companyId ? '#3b5bdb' : '#1a1d27', color: '#fff' }}
          value={companyId}
          onChange={e => setCompanyId(e.target.value)}
        >
          <option value="">All companies</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {companyId && groups.length > 0 && (
          <select
            style={{ ...tab, background: groupId ? '#3b5bdb' : '#1a1d27', color: '#fff' }}
            value={groupId}
            onChange={e => setGroupId(e.target.value)}
          >
            <option value="">All teams</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        )}
        <div style={{ width: 12 }} />
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
        {rows.map((r, i) => {
          const memberNames = Array.isArray(r.members)
            ? r.members.map(m => m.name || `#${m.player_id}`).filter(Boolean).join(', ')
            : ''
          const titleText = board === 'team'
            ? (r.player_name || memberNames || r.card_id || 'Team')
            : (r.player_name || r.card_id || 'Guest')
          const meta = [
            r.game,
            r.level,
            board === 'team' && r.member_count != null ? `${r.member_count} members` : null,
          ].filter(Boolean).join(' · ')
          return (
            <div key={i} style={row}>
              <div style={rank}>{i + 1}</div>
              <div style={{ flex: 1 }}>
                <div style={playerName}>{titleText}</div>
                {board === 'team' && memberNames && memberNames !== titleText && (
                  <div style={memberLine}>{memberNames}</div>
                )}
                <div style={gameLine}>{meta}</div>
              </div>
              <div style={scoreVal}>{r.score}</div>
            </div>
          )
        })}
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
const memberLine = { fontSize: 13, color: '#c1c6ce', marginTop: 2 }
const gameLine = { fontSize: 13, color: '#9aa0a6' }
const scoreVal = { fontSize: '1.75rem', fontWeight: 700 }
