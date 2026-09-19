import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import Pagination from '../components/Pagination.jsx'
import ExportButtons from '../components/ExportButtons.jsx'
import Spinner from '../components/Spinner.jsx'

const PAGE_SIZE = 10

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')

// System admin: every account in the system with its role and place, searchable and filterable by role.
export default function Users() {
  const [users, setUsers] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [role, setRole] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    api.listUsers().then(setUsers).catch((err) => setError(err.message))
  }, [])

  useEffect(() => { setPage(1) }, [q, role])

  const roles = [...new Map((users || []).map((u) => [u.role, u.role_display])).entries()]
  const needle = q.trim().toLowerCase()
  const visible = (users || [])
    .filter((u) => role === 'all' || u.role === role)
    .filter((u) => !needle || [u.username, u.first_name, u.last_name, u.email, u.phone, u.location_name, u.isibo]
      .join(' ').toLowerCase().includes(needle))
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageUsers = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      <div className="page-head">
        <h1>All Users{users ? ` (${users.length})` : ''}</h1>
        <Link to="/add-user" className="btn btn-small">+ Add User</Link>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <div className="filter-row date-filter">
          <div className="form-group" style={{ flex: '2 1 240px', maxWidth: 'none' }}>
            <label>Search</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Username, name, email, phone or place" />
          </div>
          <div className="form-group">
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="all">All roles</option>
              {roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>

        {users === null ? (
          <Spinner label="Loading users…" />
        ) : visible.length === 0 ? (
          <p className="muted">No users match.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title="All users"
              columns={['#', 'Username', 'Name', 'Email', 'Phone', 'Role', 'Place', 'Isibo', 'Eligible', 'Joined']}
              rows={visible.map((u, i) => [i + 1, u.username, `${u.first_name} ${u.last_name}`.trim(), u.email, u.phone || '',
                u.role_display, u.location_name || '', u.isibo || '', u.is_eligible ? 'Yes' : 'No', fmt(u.date_joined)])}
            />
            <table className="table">
              <thead>
                <tr><th>#</th><th>Username</th><th>Name</th><th>Role</th><th>Place</th><th>Contact</th><th></th></tr>
              </thead>
              <tbody>
                {pageUsers.map((u, idx) => (
                  <tr key={u.id} className="row-clickable" onClick={() => setSelected(u)}>
                    <td>{(current - 1) * PAGE_SIZE + idx + 1}</td>
                    <td>{u.username}</td>
                    <td>{u.first_name} {u.last_name}</td>
                    <td><span className="badge badge-kind">{u.role_display}</span></td>
                    <td>{u.location_name || '—'}{u.isibo ? <span className="muted small"> · isibo {u.isibo}</span> : null}</td>
                    <td className="small">{u.email}{u.phone ? <><br />{u.phone}</> : null}</td>
                    <td className="actions-cell">
                      <button className="btn btn-small" onClick={(e) => { e.stopPropagation(); setSelected(u) }}>View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="user" onChange={setPage} />
          </div>
        )}
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{selected.first_name} {selected.last_name}</h2>
            <dl className="detail-grid">
              <dt>Username</dt><dd>{selected.username}</dd>
              <dt>Role</dt><dd>{selected.role_display}</dd>
              <dt>Email</dt><dd>{selected.email || '—'}</dd>
              <dt>Phone</dt><dd>{selected.phone || '—'}</dd>
              <dt>Place</dt><dd>{selected.location_name || '—'}</dd>
              <dt>Isibo</dt><dd>{selected.isibo || '—'}</dd>
              <dt>Eligible</dt><dd>{selected.is_eligible ? 'Yes' : 'No'}</dd>
              <dt>Active</dt><dd>{selected.is_active ? 'Yes' : 'No'}</dd>
              <dt>Joined</dt><dd>{fmt(selected.date_joined)}</dd>
              <dt>Last login</dt><dd>{fmt(selected.last_login)}</dd>
            </dl>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <Link to="/eligibility" className="btn btn-small btn-outline-dark">Manage eligibility</Link>
              <button className="btn btn-small" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
