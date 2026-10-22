import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

const td = { padding: '0.5rem' }
const btn = { padding: '0.45rem 0.9rem', background: '#3b5bdb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }
const input = { padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #2a2d3a', background: '#0f1117', color: '#e8eaed' }

const WALK_IN = '__walk_in__'

export default function GroupsList() {
  const [companies, setCompanies] = useState([])
  const [companyId, setCompanyId] = useState('')
  const [rows, setRows] = useState([])
  const [name, setName] = useState('')
  const [createCompanyId, setCreateCompanyId] = useState('')
  const [error, setError] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)

  const load = async () => {
    try {
      const cos = await api('/companies')
      setCompanies(cos)
      const params = new URLSearchParams()
      if (companyId === WALK_IN) params.set('walk_in_only', 'true')
      else if (companyId) params.set('company_id', companyId)
      if (includeArchived) params.set('include_archived', 'true')
      const qs = params.toString()
      setRows(await api(`/groups${qs ? `?${qs}` : ''}`))
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [companyId, includeArchived])

  const create = async (e) => {
    e.preventDefault()
    try {
      await api('/groups', {
        method: 'POST',
        body: JSON.stringify({
          company_id: createCompanyId ? Number(createCompanyId) : null,
          name,
        }),
      })
      setName('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>Groups</h1>
      {error && <p style={{ color: '#ff6b6b' }}>{error}</p>}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ color: '#9aa0a6', marginRight: 8 }}>Filter company</label>
        <select style={input} value={companyId} onChange={e => setCompanyId(e.target.value)}>
          <option value="">All</option>
          <option value={WALK_IN}>Walk-in (no company)</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <label style={{ color: '#9aa0a6', marginLeft: 12 }}>
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={e => setIncludeArchived(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Show archived
        </label>
      </div>
      <form onSubmit={create} style={{ display: 'flex', gap: 8, marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <select style={input} value={createCompanyId} onChange={e => setCreateCompanyId(e.target.value)}>
          <option value="">No company (walk-in)</option>
          {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input style={input} placeholder="Group name" value={name} onChange={e => setName(e.target.value)} required />
        <button style={btn} type="submit">Create group</button>
      </form>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
            {['Group', 'Company', 'Members', 'Leader', 'Status'].map(h => (
              <th key={h} style={{ ...td, color: '#9aa0a6', fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(g => (
            <tr key={g.id} style={{ borderBottom: '1px solid #1a1d27' }}>
              <td style={td}><Link to={`/groups/${g.id}`} style={{ color: '#74c0fc' }}>{g.name}</Link></td>
              <td style={td}>{g.company_name || <span style={{ color: '#9aa0a6' }}>Walk-in</span>}</td>
              <td style={td}>{g.member_count ?? 0}</td>
              <td style={td}>{g.leader_player_id || '—'}</td>
              <td style={td}>{g.archived_at ? 'Archived' : (g.kind === 'solo' ? 'Solo' : 'Active')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && !error && <p style={{ color: '#9aa0a6' }}>No groups yet.</p>}
    </div>
  )
}
