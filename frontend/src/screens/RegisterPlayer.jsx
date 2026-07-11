import { useState } from 'react'
import { api } from '../api'

export default function RegisterPlayer({ onDone }) {
  const [form, setForm] = useState({ name: '', phone: '', email: '', age: '', public: true })
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setSuccess(null)
    try {
      const player = await api('/players', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          phone: form.phone,
          email: form.email || null,
          age: form.age ? +form.age : null,
          public: form.public,
        }),
      })
      setSuccess(player)
      onDone(player)
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return (
    <form onSubmit={submit} style={{ background: '#1a1d27', padding: '1.25rem', borderRadius: 12, marginBottom: '1.5rem' }}>
      <h3 style={{ marginBottom: '0.25rem' }}>Register New Player</h3>
      <p style={{ color: '#9aa0a6', fontSize: 13, marginBottom: '1rem' }}>
        Phone number is the unique ID. No card or session needed yet.
      </p>
      <div style={grid}>
        <Field label="Name *" value={form.name} onChange={v => set('name', v)} required />
        <Field label="Phone *" value={form.phone} onChange={v => set('phone', v)} required />
        <Field label="Email" value={form.email} onChange={v => set('email', v)} />
        <Field label="Age" value={form.age} onChange={v => set('age', v)} type="number" />
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
        <input type="checkbox" checked={form.public} onChange={e => set('public', e.target.checked)} />
        Show on public leaderboard
      </label>
      <button type="submit" style={btn} disabled={loading}>{loading ? '...' : 'Register'}</button>
    </form>
  )
}

function Field({ label, value, onChange, type = 'text', required }) {
  return (
    <div>
      <label style={{ fontSize: 13, color: '#9aa0a6' }}>{label}</label>
      <input style={input} value={value} onChange={e => onChange(e.target.value)} type={type} required={required} />
    </div>
  )
}

const grid = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }
const input = { width: '100%', padding: '0.5rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed', marginTop: 4 }
const btn = { marginTop: '1rem', padding: '0.6rem 1.25rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
