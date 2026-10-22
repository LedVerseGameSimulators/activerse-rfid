import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatTournamentWindow } from '../leaderboardQuery'

const td = { padding: '0.5rem' }
const btn = { padding: '0.45rem 0.9rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnMuted = { ...btn, background: '#1a1d27', color: '#9aa0a6', border: '1px solid #2a2d3a' }
const btnDanger = { ...btn, background: '#ff6b6b' }
const input = { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const select = { ...input }

const emptyForm = () => ({
  name: '',
  type: 'solo',
  scope: 'global',
  company_id: '',
  starts_at: '',
  ends_at: '',
  status: 'active',
})

export default function TournamentsAdmin() {
  const [rows, setRows] = useState([])
  const [companies, setCompanies] = useState([])
  const [error, setError] = useState('')
  const [form, setForm] = useState(emptyForm())
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState('')

  const load = async () => {
    try {
      const [t, cos] = await Promise.all([api('/tournaments'), api('/companies')])
      setRows(t)
      setCompanies(cos)
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [])

  const companyName = id => companies.find(c => c.id === id)?.name || (id ? `#${id}` : '—')

  const create = async e => {
    e.preventDefault()
    try {
      const body = {
        name: form.name,
        type: form.type,
        scope: form.scope,
        status: form.status,
        starts_at: form.starts_at || null,
        ends_at: form.ends_at || null,
        company_id: form.scope === 'company' ? Number(form.company_id) : null,
      }
      await api('/tournaments', { method: 'POST', body: JSON.stringify(body) })
      setForm(emptyForm())
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const startEdit = t => {
    setEditingId(t.id)
    setEditForm({
      name: t.name,
      starts_at: t.starts_at || '',
      ends_at: t.ends_at || '',
      status: t.status,
    })
    setError('')
  }

  const saveEdit = async t => {
    if (t.is_active_global && (editForm.starts_at !== (t.starts_at || '') || editForm.ends_at !== (t.ends_at || ''))) {
      if (!confirm('This tournament is the active global default. Changing its window will change live leaderboards immediately. Continue?')) {
        return
      }
    }
    try {
      await api(`/tournaments/${t.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editForm.name,
          starts_at: editForm.starts_at || null,
          ends_at: editForm.ends_at || null,
          status: editForm.status,
        }),
      })
      setEditingId(null)
      setEditForm(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const activate = async t => {
    try {
      await api(`/tournaments/${t.id}/activate-global`, {
        method: 'POST',
        body: JSON.stringify({ which: t.type }),
      })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const archiveToggle = async t => {
    const next = t.status === 'archived' ? 'active' : 'archived'
    try {
      await api(`/tournaments/${t.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: next }),
      })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const remove = async t => {
    if (!confirm(`Delete tournament "${t.name}"? This cannot be undone.`)) return
    try {
      await api(`/tournaments/${t.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const runPreview = async t => {
    setPreviewError('')
    try {
      const data = await api(`/tournaments/${t.id}/leaderboard?limit=20`)
      setPreview({ tournament: t, data })
    } catch (err) {
      setPreviewError(err.message)
      setPreview(null)
    }
  }

  const deleteDisabledReason = t => {
    if (t.system_key) return 'Legacy system tournaments cannot be deleted'
    if (t.is_active_global) return 'Activate another global tournament before delete'
    return ''
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>Tournaments</h1>
      {error && <p style={{ color: '#ff6b6b', marginBottom: 12 }}>{error}</p>}

      <form onSubmit={create} style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: '1.5rem', alignItems: 'flex-end' }}>
        <input style={input} placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required maxLength={80} />
        <select style={select} value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>
          <option value="solo">Solo</option>
          <option value="team">Team</option>
        </select>
        <select style={select} value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value, company_id: '' })}>
          <option value="global">Global</option>
          <option value="company">Company</option>
        </select>
        {form.scope === 'company' && (
          <select style={select} value={form.company_id} onChange={e => setForm({ ...form, company_id: e.target.value })} required>
            <option value="">Company…</option>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          Starts
          <input type="date" style={{ ...input, display: 'block', marginTop: 4 }} value={form.starts_at} onChange={e => setForm({ ...form, starts_at: e.target.value })} />
        </label>
        <label style={{ color: '#9aa0a6', fontSize: 13 }}>
          Ends
          <input type="date" style={{ ...input, display: 'block', marginTop: 4 }} value={form.ends_at} onChange={e => setForm({ ...form, ends_at: e.target.value })} />
        </label>
        <select style={select} value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        <button style={btn} type="submit">Create</button>
      </form>

      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1.5rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
            {['Name', 'Type', 'Scope', 'Window', 'Status', 'Active global', 'Actions'].map(h => (
              <th key={h} style={{ ...td, color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(t => (
            <tr key={t.id} style={{ borderBottom: '1px solid #1a1d27', verticalAlign: 'top' }}>
              <td style={td}>
                {editingId === t.id ? (
                  <input style={input} value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
                ) : (
                  <strong>{t.name}</strong>
                )}
                {t.system_key && <div style={{ fontSize: 11, color: '#9aa0a6' }}>system</div>}
              </td>
              <td style={td}>{t.type}</td>
              <td style={td}>
                {t.scope === 'global' ? 'Global' : companyName(t.company_id)}
              </td>
              <td style={td}>
                {editingId === t.id ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <input type="date" style={input} value={editForm.starts_at} onChange={e => setEditForm({ ...editForm, starts_at: e.target.value })} />
                    <input type="date" style={input} value={editForm.ends_at} onChange={e => setEditForm({ ...editForm, ends_at: e.target.value })} />
                  </div>
                ) : (
                  formatTournamentWindow(t)
                )}
              </td>
              <td style={td}>
                {editingId === t.id ? (
                  <select style={select} value={editForm.status} onChange={e => setEditForm({ ...editForm, status: e.target.value })}>
                    <option value="draft">draft</option>
                    <option value="active">active</option>
                    <option value="archived">archived</option>
                  </select>
                ) : (
                  t.status
                )}
              </td>
              <td style={td}>
                {t.is_active_global ? (
                  <span style={{ background: '#2b8a3e', color: '#fff', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                    ACTIVE {t.type}
                  </span>
                ) : '—'}
              </td>
              <td style={td}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {editingId === t.id ? (
                    <>
                      <button style={btn} type="button" onClick={() => saveEdit(t)}>Save</button>
                      <button style={btnMuted} type="button" onClick={() => { setEditingId(null); setEditForm(null) }}>Cancel</button>
                    </>
                  ) : (
                    <button style={btnMuted} type="button" onClick={() => startEdit(t)}>Edit</button>
                  )}
                  {t.scope === 'global' && t.status === 'active' && !t.is_active_global && (
                    <button style={btn} type="button" onClick={() => activate(t)} title={`Make active global ${t.type}`}>
                      Make active global
                    </button>
                  )}
                  <button style={btnMuted} type="button" onClick={() => archiveToggle(t)}>
                    {t.status === 'archived' ? 'Restore' : 'Archive'}
                  </button>
                  <button style={btnMuted} type="button" onClick={() => runPreview(t)}>Preview</button>
                  <button
                    style={deleteDisabledReason(t) ? { ...btnDanger, opacity: 0.45, cursor: 'not-allowed' } : btnDanger}
                    type="button"
                    disabled={!!deleteDisabledReason(t)}
                    title={deleteDisabledReason(t) || 'Delete tournament'}
                    onClick={() => !deleteDisabledReason(t) && remove(t)}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {rows.length === 0 && !error && <p style={{ color: '#9aa0a6' }}>No tournaments yet.</p>}

      {previewError && <p style={{ color: '#ff6b6b' }}>{previewError}</p>}
      {preview && (
        <section style={{ background: '#1a1d27', padding: '1rem', borderRadius: 12 }}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: 8 }}>
            Preview — {preview.tournament.name} ({formatTournamentWindow(preview.tournament)})
          </h2>
          <p style={{ color: '#9aa0a6', fontSize: 13, marginBottom: 12 }}>
            {preview.data.total} plays in window · board {preview.data.board}
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2d3a' }}>
                {['Rank', 'Name', 'Score', 'Game', 'When'].map(h => (
                  <th key={h} style={{ ...td, color: '#9aa0a6', textAlign: 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(preview.data.rows || []).map(r => (
                <tr key={r.id || r.rank} style={{ borderBottom: '1px solid #0f1117' }}>
                  <td style={td}>{r.rank}</td>
                  <td style={td}>{r.player_name || r.group_name || r.card_id || '—'}</td>
                  <td style={td}>{r.score}</td>
                  <td style={td}>{r.game}</td>
                  <td style={td}>{r.played_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(preview.data.rows || []).length === 0 && (
            <p style={{ color: '#9aa0a6' }}>No plays in this tournament window.</p>
          )}
          <button style={{ ...btnMuted, marginTop: 12 }} type="button" onClick={() => setPreview(null)}>Close preview</button>
        </section>
      )}
    </div>
  )
}
