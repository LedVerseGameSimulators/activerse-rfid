import { Link } from 'react-router-dom'
import { linkStyle } from './statsTheme'

export function PlayerLink({ id, name, fallback }) {
  if (!id) return <span>{fallback || name || '—'}</span>
  const label = name || fallback || `#${id}`
  return <Link to={`/stats/player/${id}`} style={linkStyle}>{label}</Link>
}

export function GroupLink({ id, name }) {
  if (!id) return <span>{name || '—'}</span>
  return <Link to={`/stats/group/${id}`} style={linkStyle}>{name || `#${id}`}</Link>
}

export function SessionLink({ id, label }) {
  if (!id) return <span>—</span>
  return <Link to={`/stats/session/${id}`} style={linkStyle}>{label || `Session #${id}`}</Link>
}

export function CompanyLink({ id, name }) {
  if (!id) return <span>{name || '—'}</span>
  return <Link to={`/stats/company/${id}`} style={linkStyle}>{name || `#${id}`}</Link>
}

export function TournamentLink({ id, name }) {
  if (!id) return <span>{name || '—'}</span>
  return <Link to={`/stats/tournament/${id}`} style={linkStyle}>{name || `#${id}`}</Link>
}

export function GameLink({ gameKey, label }) {
  if (!gameKey) return <span>—</span>
  return <Link to={`/stats/game/${gameKey}`} style={linkStyle}>{label || gameKey}</Link>
}
