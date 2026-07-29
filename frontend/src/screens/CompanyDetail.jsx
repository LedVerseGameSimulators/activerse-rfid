import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api, apiForm, templateUrl } from '../api'

const td = { padding: '0.5rem' }
const btn = { padding: '0.45rem 0.9rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const input = { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }
const card = { background: '#1a1d27', borderRadius: 12, padding: '1rem', border: '1px solid #2a2d3a', marginBottom: '1rem' }

export default function CompanyDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [company, setCompany] = useState(null)
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [groupName, setGroupName] = useState('')
  const [error, setError] = useState('')
  const [importReport, setImportReport] = useState(null)

  const load = async () => {
    try {
      const c = await api(`/companies/${id}`)
      setCompany(c)
      setName(c.name)
      setNotes(c.notes || '')
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [id])

  const save = async (e) => {
    e.preventDefault()
    try {
      await api(`/companies/${id}`, { method: 'PUT', body: JSON.stringify({ name, notes }) })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const createGroup = async (e) => {
    e.preventDefault()
    try {
      const g = await api('/groups', {
        method: 'POST',
        body: JSON.stringify({ company_id: Number(id), name: groupName }),
      })
      setGroupName('')
      nav(`/groups/${g.id}`)
    } catch (err) {
      setError(err.message)
    }
  }

  const onImport = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    try {
      setImportReport(await apiForm('/import/excel', fd))
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async () => {
    if (!confirm(`Delete company "${company?.name}"?`)) return
    try {
      await api(`/companies/${id}`, { method: 'DELETE' })
      nav('/companies')
    } catch (err) {
      alert(err.message)
    }
  }

  if (!company && !error) return <p style={{ color: '#9aa0a6' }}>Loading…</p>

  return (
    <div>
      <p><Link to="/companies" style={{ color: '#74c0fc' }}>← Companies</Link></p>
      <h1 style={{ marginBottom: '1rem' }}>{company?.name || 'Company'}</h1>
      {error && <p style={{ color: '#ff6b6b' }}>{error}</p>}

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Edit</h2>
        <form onSubmit={save} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input style={input} value={name} onChange={e => setName(e.target.value)} />
          <input style={input} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes" />
          <button style={btn} type="submit">Save</button>
          <button style={{ ...btn, background: '#ff6b6b' }} type="button" onClick={remove}>Delete company</button>
        </form>
      </div>

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Excel import</h2>
        <p style={{ color: '#9aa0a6', fontSize: 13 }}>
          Columns: company_name, group_name, player_name, phone, is_team_leader, email, age
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <a href={templateUrl()} style={{ ...btn, textDecoration: 'none', display: 'inline-block' }}>Download template</a>
          <input type="file" accept=".xlsx" onChange={onImport} />
        </div>
        {importReport && (
          <pre style={{ marginTop: 12, fontSize: 12, color: '#c1c2c5', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(importReport, null, 2)}
          </pre>
        )}
      </div>

      <div style={card}>
        <h2 style={{ fontSize: '1rem', marginBottom: 8 }}>Groups</h2>
        <form onSubmit={createGroup} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input style={input} placeholder="New group name" value={groupName} onChange={e => setGroupName(e.target.value)} required />
          <button style={btn} type="submit">Add group</button>
        </form>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
              <th style={{ ...td, color: '#9aa0a6' }}>Name</th>
              <th style={{ ...td, color: '#9aa0a6' }}>Members</th>
            </tr>
          </thead>
          <tbody>
            {(company?.groups || []).map(g => (
              <tr key={g.id} style={{ borderBottom: '1px solid #1a1d27' }}>
                <td style={td}><Link to={`/groups/${g.id}`} style={{ color: '#74c0fc' }}>{g.name}</Link></td>
                <td style={td}>{g.member_count ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
