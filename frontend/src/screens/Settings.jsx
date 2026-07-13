import { useState, useEffect } from 'react'
import { api } from '../api'

function GlobalSettings() {
  const [settings, setSettings] = useState({})
  const [saved, setSaved] = useState(false)

  useEffect(() => { api('/settings').then(setSettings) }, [])

  const save = async () => {
    await api('/settings', { method: 'PUT', body: JSON.stringify(settings) })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const set = (k, v) => setSettings(s => ({ ...s, [k]: v }))

  return (
    <div style={{ background: '#1a1d27', padding: '1.5rem', borderRadius: 12, maxWidth: 400, marginTop: '1.5rem' }}>
      <h3 style={{ marginBottom: '1rem' }}>Credit Ratios</h3>
      <label style={label}>Money per minute</label>
      <input style={input} type="number" value={settings.money_per_minute || ''} onChange={e => set('money_per_minute', e.target.value)} />
      <label style={label}>Min top-up (minutes)</label>
      <input style={input} type="number" value={settings.min_topup_minutes || ''} onChange={e => set('min_topup_minutes', e.target.value)} />
      <label style={label}>Max top-up (minutes)</label>
      <input style={input} type="number" value={settings.max_topup_minutes || ''} onChange={e => set('max_topup_minutes', e.target.value)} />
      <button style={btn} onClick={save}>Save</button>
      {saved && <p style={{ color: '#51cf66', marginTop: 8 }}>Saved.</p>}
    </div>
  )
}

function GameSettingsPush() {
  const GAMES = [
    { key: 'hoops', label: 'Hoops' }, { key: 'laser', label: 'Laser Trap' },
    { key: 'climb', label: 'Climb' }, { key: 'grid', label: 'Floor Is Lava' },
    { key: 'led_hex', label: 'LED Hexagon' },
  ]
  const [game, setGame] = useState('hoops')
  const [difficulty, setDifficulty] = useState('normal')
  const [minutes, setMinutes] = useState(5)
  const [msg, setMsg] = useState('')

  const push = async () => {
    try {
      await api(`/games/${game}/settings`, {
        method: 'PUT',
        body: JSON.stringify({ default_difficulty: difficulty, session_minutes: minutes }),
      })
      setMsg(`Pushed to ${game}.`)
    } catch (e) {
      setMsg(e.message)
    }
  }

  return (
    <div style={{ background: '#1a1d27', padding: '1.5rem', borderRadius: 12, maxWidth: 400, marginTop: '1.5rem' }}>
      <h3 style={{ marginBottom: '1rem' }}>Per-Game Defaults</h3>
      <label style={label}>Game</label>
      <select style={input} value={game} onChange={e => setGame(e.target.value)}>
        {GAMES.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
      </select>
      <label style={label}>Default difficulty</label>
      <select style={input} value={difficulty} onChange={e => setDifficulty(e.target.value)}>
        <option value="easy">Easy</option>
        <option value="normal">Normal</option>
        <option value="hard">Hard</option>
      </select>
      <label style={label}>Session length (minutes)</label>
      <input style={input} type="number" value={minutes} onChange={e => setMinutes(+e.target.value)} min={1} />
      <button style={btn} onClick={push}>Push to Game</button>
      {msg && <p style={{ marginTop: 8, color: '#9aa0a6' }}>{msg}</p>}
    </div>
  )
}

export default function Settings() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    try {
      await api('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      setMsg('Password updated.')
      setPassword('')
    } catch (e) {
      setMsg(e.message)
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Settings</h1>
      <form onSubmit={submit} style={{ background: '#1a1d27', padding: '1.5rem', borderRadius: 12, maxWidth: 400 }}>
        <h3 style={{ marginBottom: '1rem' }}>Admin Account</h3>
        <label style={label}>Username</label>
        <input style={input} value={username} onChange={e => setUsername(e.target.value)} />
        <label style={label}>New Password</label>
        <input style={input} type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        <button type="submit" style={btn}>Save</button>
        {msg && <p style={{ marginTop: '1rem', color: '#51cf66' }}>{msg}</p>}
      </form>
      <p style={{ marginTop: '1.5rem', color: '#9aa0a6', fontSize: 13 }}>
        Game machine URLs and operational config are set in the .env file on this server.
      </p>
      <GlobalSettings />
      <GameSettingsPush />
    </div>
  )
}

const label = { display: 'block', marginBottom: 4, color: '#9aa0a6', fontSize: 13, marginTop: 12 }
const input = { width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { marginTop: '1rem', padding: '0.6rem 1.25rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
