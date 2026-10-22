import { Link } from 'react-router-dom'
import SessionRoster from './SessionRoster'

export default function PlayerCard({ player, activeSession, onStartVisit, onAdjust, onBindCard, onTopUp, onRosterChanged }) {
  if (!player) return null

  const hasCard = Boolean(player.card_id)
  const creditBalance = player.credit_balance ?? 0
  const onTeamGroup = Boolean(player.has_team_group)

  return (
    <div style={cardStyle}>
      <h2 style={{ marginBottom: '0.5rem' }}>{player.name}</h2>
      <p style={muted}>Phone: {player.phone}</p>
      {player.email && <p style={muted}>Email: {player.email}</p>}
      {player.age != null && <p style={muted}>Age: {player.age}</p>}
      {(player.company_id || player.group_names || player.group_name) && (
        <p style={{ marginTop: 6 }}>
          {player.company_id && <span style={badge}>{player.company_name}</span>}
          {(player.group_names || player.group_name) && (
            <span style={{ ...badge, color: '#74c0fc' }}>
              {player.group_names || player.group_name}
            </span>
          )}
        </p>
      )}

      <div style={{
        marginTop: '1rem', padding: '0.75rem 1rem', borderRadius: 8,
        background: creditBalance > 0 ? '#12261a' : '#2a1616',
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 13, color: '#9aa0a6' }}>Credit balance</span>
        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: creditBalance > 0 ? '#51cf66' : '#ff6b6b' }}>
          {creditBalance} min
        </span>
      </div>

      <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#0f1117', borderRadius: 8 }}>
        <p style={{ fontSize: 13, color: '#9aa0a6', marginBottom: 8 }}>Onboarding status</p>
        <StatusLine done label="Registered" detail={player.phone} />
        <StatusLine done={hasCard} label="RFID card bound" detail={hasCard ? player.card_id : 'Go to Players → Bind Card'} />
        <StatusLine done={Boolean(activeSession)} label="Visit active" detail={activeSession ? `${activeSession.minutes_remaining} min left` : 'Start Visit after card is bound'} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: '1rem' }}>
        <button style={btnSm} onClick={() => onBindCard(player)}>
          {hasCard ? 'Rebind Card' : 'Bind Card'}
        </button>
        <button style={{ ...btnSm, background: '#2f9e44' }} onClick={() => onTopUp(player)}>
          Top Up
        </button>
      </div>

      {activeSession && (
        <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#1a2a1a', borderRadius: 8 }}>
          <p style={{ color: activeSession.minutes_remaining < 5 ? '#ff6b6b' : '#51cf66', fontWeight: 600 }}>
            Active session — {activeSession.minutes_remaining} min remaining
          </p>
          <p style={muted}>Expires: {activeSession.expiry_at}</p>
          <button style={{ ...btnSm, marginTop: 8 }} onClick={() => onAdjust(activeSession)}>
            Adjust Session
          </button>
          <SessionRoster sessionId={activeSession.id} onChanged={onRosterChanged} />
        </div>
      )}

      {hasCard && !activeSession && onTeamGroup && (
        <p style={{ ...muted, marginTop: '1rem', color: '#fcc419' }}>
          On a team — use Start Visit on the team group (or solo group for individual play).
          Members do not scan at kiosks; only the visit leader&apos;s card works.
        </p>
      )}

      {hasCard && !activeSession && (
        <div style={{ display: 'flex', gap: 8, marginTop: '1rem', flexWrap: 'wrap' }}>
          <button style={{ ...btnSm, background: '#2f9e44' }} onClick={() => onStartVisit(player)}>
            Start Visit
          </button>
          {player.solo_group_id && (
            <Link to={`/groups/${player.solo_group_id}`} style={{ ...btnSm, textDecoration: 'none', background: '#495057' }}>
              Open solo group
            </Link>
          )}
        </div>
      )}

      {!hasCard && (
        <p style={{ ...muted, marginTop: '1rem', color: '#fcc419' }}>
          Bind an RFID card before starting a visit.
        </p>
      )}
    </div>
  )
}

function StatusLine({ done, label, detail }) {
  return (
    <p style={{ fontSize: 14, marginBottom: 6, color: done ? '#51cf66' : '#9aa0a6' }}>
      {done ? '✓' : '○'} {label}
      {detail && <span style={{ color: '#6c757d', marginLeft: 8 }}>{detail}</span>}
    </p>
  )
}

const cardStyle = { background: '#1a1d27', borderRadius: 12, padding: '1.25rem', border: '1px solid #2a2d3a' }
const muted = { color: '#9aa0a6', fontSize: 14, marginTop: 4 }
const btnSm = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const badge = { display: 'inline-block', fontSize: 12, padding: '2px 8px', borderRadius: 999, background: '#0f1117', color: '#9aa0a6', marginRight: 6 }
