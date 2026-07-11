import { useState } from 'react'
import { api } from '../api'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const res = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      if (res.success) onLogin()
      else setError('Invalid credentials')
    } catch {
      setError('Login failed')
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <form onSubmit={handleSubmit} style={{ background: '#1a1d27', padding: '2rem', borderRadius: 12, width: 360 }}>
        <h1 style={{ marginBottom: '1.5rem', fontSize: '1.5rem' }}>Activerse RFID</h1>
        {error && <p style={{ color: '#ff6b6b', marginBottom: '1rem' }}>{error}</p>}
        <label style={labelStyle}>Username</label>
        <input style={inputStyle} value={username} onChange={e => setUsername(e.target.value)} />
        <label style={labelStyle}>Password</label>
        <input style={inputStyle} type="password" value={password} onChange={e => setPassword(e.target.value)} />
        <button type="submit" style={btnStyle}>Login</button>
      </form>
    </div>
  )
}

const labelStyle = { display: 'block', marginBottom: 4, color: '#9aa0a6', fontSize: 13 }
const inputStyle = { width: '100%', padding: '0.6rem', marginBottom: '1rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const btnStyle = { width: '100%', padding: '0.75rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }
