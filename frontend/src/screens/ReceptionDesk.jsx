import { useState, useEffect } from 'react'
import PlayerSearch from './PlayerSearch'
import PlayerCard from '../components/PlayerCard'
import RegisterPlayer from './RegisterPlayer'
import IssueSession from './IssueSession'
import AdjustSession from './AdjustSession'
import BindCard from './BindCard'
import TopUp from './TopUp'
import { api } from '../api'

export default function ReceptionDesk() {
  const [mode, setMode] = useState('returning') // new | returning
  const [selected, setSelected] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [showIssue, setShowIssue] = useState(false)
  const [showAdjust, setShowAdjust] = useState(false)
  const [showBind, setShowBind] = useState(false)
  const [showTopUp, setShowTopUp] = useState(false)
  const [settings, setSettings] = useState(null)

  useEffect(() => {
    api('/settings').then(setSettings).catch(() => setSettings({}))
  }, [])

  const loadSession = async (player) => {
    try {
      const sessions = await api('/sessions/active')
      // Match payer OR roster member so teammates see the open team session
      const match = sessions.find(s =>
        s.player_id === player.id ||
        (Array.isArray(s.roster) && s.roster.some(m => m.player_id === player.id))
      )
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

  const refreshPlayer = async () => {
    if (!selected) return
    try {
      const updated = await api(`/players/${selected.id}`)
      setSelected(updated)
      await loadSession(updated)
    } catch {
      await refresh()
    }
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
                onBindCard={() => setShowBind(true)}
                onTopUp={() => setShowTopUp(true)}
                onRosterChanged={() => refresh()}
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
      {showBind && selected && (
        <BindCard
          player={selected}
          onDone={() => { setShowBind(false); refreshPlayer() }}
        />
      )}
      {showTopUp && selected && (
        <TopUp
          player={selected}
          moneyPerMinute={settings?.money_per_minute}
          onDone={() => { setShowTopUp(false); refreshPlayer() }}
          onCancel={() => setShowTopUp(false)}
        />
      )}
    </div>
  )
}

const tab = { padding: '0.5rem 1rem', background: '#1a1d27', color: '#9aa0a6', border: '1px solid #2a2d3a', borderRadius: 6, cursor: 'pointer' }
const tabActive = { ...tab, background: '#3b5bdb', color: '#fff', borderColor: '#3b5bdb' }
