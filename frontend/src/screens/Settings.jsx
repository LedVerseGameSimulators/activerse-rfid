import { useState } from 'react'
import { api } from '../api'

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
    </div>
  )
}

const label = { display: 'block', marginBottom: 4, color: '#9aa0a6', fontSize: 13, marginTop: 12 }
const input = { width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btn = { marginTop: '1rem', padding: '0.6rem 1.25rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
