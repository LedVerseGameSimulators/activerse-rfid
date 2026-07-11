import { useState } from 'react'
import PlayerSearch from './PlayerSearch'
import PlayerCard from '../components/PlayerCard'
import RegisterPlayer from './RegisterPlayer'
import IssueSession from './IssueSession'
import AdjustSession from './AdjustSession'
import { api } from '../api'

export default function ReceptionDesk() {
  const [mode, setMode] = useState('returning') // new | returning
  const [selected, setSelected] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [showIssue, setShowIssue] = useState(false)
  const [showAdjust, setShowAdjust] = useState(false)

  const loadSession = async (player) => {
    try {
      const sessions = await api('/sessions/active')
      const match = sessions.find(s => s.player_id === player.id)
      setActiveSession(match || null)
    } catch {
      setActiveSession(null)
    }
  }

  const handleSelect = async (player) => {
    setSelected(player)
    await loadSession(player)
  }

  const handleRegistered = async (player) => {
    setMode('returning')
    setSelected(player)
    setActiveSession(null)
  }

  const refresh = async () => {
    if (selected) await loadSession(selected)
  }

  return (
    <div>
      <h1 style={{ marginBottom: '0.5rem' }}>Reception Desk</h1>
      <p style={{ color: '#9aa0a6', marginBottom: '1.5rem', fontSize: 14 }}>
        Step 1: Register new visitors · Step 2 (later): bind card · Step 3 (later): issue session
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: '1.5rem' }}>
        <button
          style={mode === 'new' ? tabActive : tab}
          onClick={() => { setMode('new'); setSelected(null) }}
        >
          New Visitor
        </button>
        <button
          style={mode === 'returning' ? tabActive : tab}
          onClick={() => setMode('returning')}
        >
          Returning Visitor
        </button>
      </div>

      {mode === 'new' && (
        <RegisterPlayer onDone={handleRegistered} />
      )}

      {mode === 'returning' && (
        <>
          <PlayerSearch onSelect={handleSelect} />
          {selected && (
            <div style={{ marginTop: '1.5rem' }}>
              <PlayerCard
                player={selected}
                activeSession={activeSession}
                onIssue={() => setShowIssue(true)}
                onAdjust={() => setShowAdjust(true)}
              />
            </div>
          )}
        </>
      )}

      {showIssue && selected && (
        <IssueSession
          player={selected}
          onDone={() => { setShowIssue(false); refresh() }}
          onCancel={() => setShowIssue(false)}
        />
      )}
      {showAdjust && activeSession && (
        <AdjustSession
          session={activeSession}
          onDone={() => { setShowAdjust(false); refresh() }}
          onCancel={() => setShowAdjust(false)}
        />
      )}
    </div>
  )
}

const tab = { padding: '0.5rem 1rem', background: '#1a1d27', color: '#9aa0a6', border: '1px solid #2a2d3a', borderRadius: 6, cursor: 'pointer' }
const tabActive = { ...tab, background: '#3b5bdb', color: '#fff', borderColor: '#3b5bdb' }
