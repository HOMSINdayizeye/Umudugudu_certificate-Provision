import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Pagination from '../components/Pagination.jsx'
import ExportButtons from '../components/ExportButtons.jsx'

const PAGE_SIZE = 5

export default function ManageEligibility() {
  const [users, setUsers] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('all') // all | eligible | not
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.listUsers().then(setUsers).catch((err) => setError(err.message))
  }, [])

  // Back to the first page whenever the filters change
  useEffect(() => { setPage(1) }, [q, only])

  async function toggle(user) {
    setError('')
    setMessage('')
    try {
      const updated = await api.setEligibility(user.id, !user.is_eligible)
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)))
      setMessage(`${updated.username} is now ${updated.is_eligible ? 'eligible' : 'not eligible'}.`)
    } catch (err) {
      setError(err.message)
    }
  }

  const needle = q.trim().toLowerCase()
  const visible = (users || [])
    .filter((u) => only === 'all' || (only === 'eligible') === !!u.is_eligible)
    .filter((u) => !needle || [u.username, u.first_name, u.last_name, u.email].join(' ').toLowerCase().includes(needle))
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const current = Math.min(page, totalPages)
  const pageUsers = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)

  return (
    <div>
      <div className="page-head"><h1>Manage Eligibility</h1></div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <div className="card">
        <div className="filter-row date-filter">
          <div className="form-group" style={{ flex: '2 1 240px', maxWidth: 'none' }}>
            <label>Search</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Username, name or email" />
          </div>
          <div className="form-group">
            <label>Show</label>
            <select value={only} onChange={(e) => setOnly(e.target.value)}>
              <option value="all">All users</option>
              <option value="eligible">Eligible only</option>
              <option value="not">Not eligible only</option>
            </select>
          </div>
        </div>

        {users === null ? (
          <p className="muted">Loading…</p>
        ) : visible.length === 0 ? (
          <p className="muted">No users match.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title="Users and eligibility"
              columns={['#', 'Username', 'Name', 'Email', 'Role', 'Village', 'Eligible']}
              rows={visible.map((u, i) => [i + 1, u.username, `${u.first_name} ${u.last_name}`.trim(), u.email, u.role_display, u.village_name || '', u.is_eligible ? 'Yes' : 'No'])}
            />
            <table className="table">
              <thead>
                <tr><th>#</th><th>Username</th><th>Name</th><th>Email</th><th>Role</th><th>Eligible</th><th></th></tr>
              </thead>
              <tbody>
                {pageUsers.map((u, idx) => (
                  <tr key={u.id}>
                    <td>{(current - 1) * PAGE_SIZE + idx + 1}</td>
                    <td>{u.username}</td>
                    <td>{u.first_name} {u.last_name}</td>
                    <td>{u.email}</td>
                    <td className="muted small">{u.role_display}</td>
                    <td>
                      <span className={`badge ${u.is_eligible ? 'badge-approved' : 'badge-pending'}`}>{u.is_eligible ? 'Yes' : 'No'}</span>
                    </td>
                    <td className="actions-cell">
                      <button className={`btn btn-small ${u.is_eligible ? 'btn-outline-dark' : ''}`} onClick={() => toggle(u)}>
                        {u.is_eligible ? 'Revoke' : 'Mark eligible'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination page={current} totalPages={totalPages} total={visible.length} label="user" onChange={setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
