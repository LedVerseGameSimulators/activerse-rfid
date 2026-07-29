import SessionRoster from './SessionRoster'

export default function PlayerCard({ player, activeSession, onIssue, onAdjust, onBindCard, onTopUp, onRosterChanged }) {
  if (!player) return null

  const hasCard = Boolean(player.card_id)
  const creditBalance = player.credit_balance ?? 0

  return (
    <div style={cardStyle}>
      <h2 style={{ marginBottom: '0.5rem' }}>{player.name}</h2>
      <p style={muted}>Phone: {player.phone}</p>
      {player.email && <p style={muted}>Email: {player.email}</p>}
      {player.age != null && <p style={muted}>Age: {player.age}</p>}

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
        <StatusLine done={Boolean(activeSession)} label="Session issued" detail={activeSession ? `${activeSession.minutes_remaining} min left` : 'After card is bound'} />
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

      {hasCard && !activeSession && (
        <button style={{ ...btnSm, marginTop: '1rem' }} onClick={() => onIssue(player)}>
          Issue Session
        </button>
      )}

      {!hasCard && (
        <p style={{ ...muted, marginTop: '1rem', color: '#fcc419' }}>
          Next: open Players tab to bind an RFID card before issuing a session.
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
