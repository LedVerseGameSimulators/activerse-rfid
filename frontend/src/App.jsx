import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import ReceptionDesk from './screens/ReceptionDesk'
import PlayerAdmin from './screens/PlayerAdmin'
import Dashboard from './screens/Dashboard'
import Settings from './screens/Settings'
import Login from './screens/Login'

const navStyle = {
  display: 'flex',
  gap: '0.5rem',
  padding: '0.75rem 1.5rem',
  background: '#1a1d27',
  borderBottom: '1px solid #2a2d3a',
}

const linkStyle = ({ isActive }) => ({
  padding: '0.5rem 1rem',
  borderRadius: '6px',
  textDecoration: 'none',
  color: isActive ? '#fff' : '#9aa0a6',
  background: isActive ? '#3b5bdb' : 'transparent',
  fontWeight: isActive ? 600 : 400,
})

function AppShell() {
  return (
    <>
      <nav style={navStyle}>
        <NavLink to="/" style={linkStyle} end>Reception</NavLink>
        <NavLink to="/players" style={linkStyle}>Players</NavLink>
        <NavLink to="/dashboard" style={linkStyle}>Dashboard</NavLink>
        <NavLink to="/settings" style={linkStyle}>Settings</NavLink>
      </nav>
      <main style={{ padding: '1.5rem', maxWidth: 1200, margin: '0 auto' }}>
        <Routes>
          <Route path="/" element={<ReceptionDesk />} />
          <Route path="/players" element={<PlayerAdmin />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(() => sessionStorage.getItem('rfid_auth') === '1')

  if (!authed) {
    return <Login onLogin={() => { sessionStorage.setItem('rfid_auth', '1'); setAuthed(true) }} />
  }

  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
