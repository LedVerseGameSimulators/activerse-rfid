import { useState } from 'react'
import { api } from '../api'

export default function BindCard({ player, onDone }) {
  const [cardId, setCardId] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api(`/players/${player.id}/bind-card`, {
        method: 'POST',
        body: JSON.stringify({ card_id: cardId }),
      })
      onDone()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ background: '#1a1d27', padding: '1rem', borderRadius: 8, marginTop: '1rem' }}>
      <h4>Bind RFID Card — {player.name}</h4>
      <p style={{ color: '#9aa0a6', fontSize: 13, margin: '0.5rem 0' }}>
        Scan card or type card ID (HID keyboard mode)
      </p>
      <input
        style={input}
        value={cardId}
        onChange={e => setCardId(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit(e)}
        placeholder="CARD001..."
        autoFocus
      />
      <button type="submit" style={btn} disabled={loading}>{loading ? '...' : 'Bind Card'}</button>
    </form>
  )
}

const input = { width: '100%', padding: '0.6rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed', marginBottom: 8 }
const btn = { padding: '0.5rem 1rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
