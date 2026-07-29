import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

const td = { padding: '0.5rem' }
const btn = { padding: '0.45rem 0.9rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const input = { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }

export default function CompaniesList() {
  const [rows, setRows] = useState([])
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setRows(await api('/companies'))
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    try {
      await api('/companies', { method: 'POST', body: JSON.stringify({ name, notes }) })
      setName('')
      setNotes('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (c) => {
    if (!confirm(`Delete company "${c.name}"? Groups will be removed; players are kept.`)) return
    try {
      await api(`/companies/${c.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>Companies</h1>
      {error && <p style={{ color: '#ff6b6b' }}>{error}</p>}
      <form onSubmit={create} style={{ display: 'flex', gap: 8, marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <input style={input} placeholder="Company name" value={name} onChange={e => setName(e.target.value)} required />
        <input style={input} placeholder="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)} />
        <button style={btn} type="submit">Create</button>
      </form>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
            {['Name', 'Groups', 'Notes', ''].map(h => (
              <th key={h} style={{ ...td, color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.id} style={{ borderBottom: '1px solid #1a1d27' }}>
              <td style={td}><Link to={`/companies/${c.id}`} style={{ color: '#74c0fc' }}>{c.name}</Link></td>
              <td style={td}>{c.group_count ?? 0}</td>
              <td style={td}>{c.notes || '—'}</td>
              <td style={td}>
                <button style={{ ...btn, background: '#ff6b6b' }} onClick={() => remove(c)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && !error && <p style={{ color: '#9aa0a6' }}>No companies yet.</p>}
    </div>
  )
}
