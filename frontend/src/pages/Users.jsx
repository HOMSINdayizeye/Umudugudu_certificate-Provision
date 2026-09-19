import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getUser, can } from '../api.js'
import Pagination from '../components/Pagination.jsx'
import ExportButtons from '../components/ExportButtons.jsx'
import Spinner from '../components/Spinner.jsx'
import { ROLES } from './AddUser.jsx'

const PAGE_SIZE = 10

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')

// System admin: every account in the system with its role and place, searchable and filterable by role.
export default function Users() {
  const [users, setUsers] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [q, setQ] = useState('')
  const [role, setRole] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [catalog, setCatalog] = useState(null) // permission catalog, loaded once for the pop-up

  useEffect(() => {
    api.listUsers().then(setUsers).catch((err) => setError(err.message))
    if (can(getUser(), 'permissions:users')) {
      api.permissionCatalog().then((d) => setCatalog(d.catalog)).catch(() => {})
    }
  }, [])

  useEffect(() => { setPage(1) }, [q, role])

  // All defined roles, each with how many users currently hold it
  const counts = (users || []).reduce((acc, u) => ({ ...acc, [u.role]: (acc[u.role] || 0) + 1 }), {})
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
        {can(getUser(), 'add:users') && <Link to="/add-user" className="btn btn-small">+ Add User</Link>}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

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
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label} ({counts[r.value] || 0})</option>
              ))}
            </select>
          </div>
        </div>

        {users === null ? (
          <Spinner label="Loading users…" />
        ) : visible.length === 0 ? (
          <p className="muted">
            {role !== 'all' && !counts[role]
              ? <>No {ROLES.find((r) => r.value === role)?.label.toLowerCase()} account exists yet. <Link to="/add-user">Add one</Link>.</>
              : 'No users match.'}
          </p>
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
        <UserModal
          user={selected}
          catalog={catalog}
          onClose={() => setSelected(null)}
          onUpdated={(u) => {
            setSelected(u)
            setUsers((list) => list.map((x) => (x.id === u.id ? u : x)))
          }}
          onDeleted={(u, text) => {
            setSelected(null)
            setUsers((list) => list.filter((x) => x.id !== u.id))
            setMessage(text)
          }}
        />
      )}
    </div>
  )
}

function UserModal({ user, catalog, onClose, onUpdated, onDeleted }) {
  const me = getUser()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  // Same rules as the server: the permission, never yourself, admins only by admins, superusers only by superusers
  const meAdmin = me?.is_superuser || me?.is_admin_role
  const canDelete = me && can(me, 'delete:users') && user.id !== me.id
    && (!user.is_superuser || me.is_superuser) && (!(user.is_superuser || user.is_admin_role) || meAdmin)
  const canManagePerms = can(me, 'permissions:users') && !!catalog

  // Tick or untick one permission for this user: stored as a grant (outside the role) or a deny (inside it)
  async function togglePerm(key) {
    const inRole = user.role_permissions.includes(key)
    const has = user.permissions.includes(key)
    let grants = user.permission_grants.filter((k) => k !== key)
    let denies = user.permission_denies.filter((k) => k !== key)
    if (has && inRole) denies = [...denies, key]
    if (!has && !inRole) grants = [...grants, key]
    setError('')
    setSaved('')
    setBusy(true)
    try {
      const updated = await api.setUserPermissions(user.id, grants, denies)
      onUpdated(updated)
      setSaved(`${has ? 'Revoked' : 'Granted'} ${key}.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function resetPerms() {
    setError('')
    setBusy(true)
    try {
      onUpdated(await api.setUserPermissions(user.id, [], []))
      setSaved('Back to the role’s permissions.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setError('')
    setBusy(true)
    try {
      const res = await api.deleteUser(user.id)
      onDeleted(user, res.detail)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{user.first_name} {user.last_name}</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <dl className="detail-grid">
          <dt>Username</dt><dd>{user.username}</dd>
          <dt>Role</dt><dd>{user.role_display}</dd>
          <dt>Email</dt><dd>{user.email || '—'}</dd>
          <dt>Phone</dt><dd>{user.phone || '—'}</dd>
          <dt>Place</dt><dd>{user.location_name || '—'}</dd>
          <dt>Isibo</dt><dd>{user.isibo || '—'}</dd>
          <dt>Eligible</dt><dd>{user.is_eligible ? 'Yes' : 'No'}</dd>
          <dt>Active</dt><dd>{user.is_active ? 'Yes' : 'No'}</dd>
          <dt>Joined</dt><dd>{fmt(user.date_joined)}</dd>
          <dt>Last login</dt><dd>{fmt(user.last_login)}</dd>
        </dl>

        {canManagePerms && (
          <>
            <div className="section-title">Permissions</div>
            {user.is_superuser || user.is_admin_role ? (
              <p className="muted small" style={{ margin: 0 }}>Administrators always hold every permission.</p>
            ) : (
              <>
                <p className="muted small" style={{ marginTop: 0 }}>
                  Ticked = allowed. Grey ones come from the {user.role_display} role; tick to give this user more, untick to take a role permission away.
                </p>
                {saved && <div className="field-hint field-hint-ok">{saved}</div>}
                {catalog.map((group) => (
                  <div key={group.resource} className="perm-group" style={{ marginTop: '0.75rem' }}>
                    <div className="perm-group-head"><strong className="small">{group.label}</strong></div>
                    {group.actions.map((a) => {
                      const has = user.permissions.includes(a.key)
                      const granted = user.permission_grants.includes(a.key)
                      const revoked = user.permission_denies.includes(a.key)
                      return (
                        <label key={a.key} className={`perm-row ${has ? 'perm-on' : ''}`}>
                          <input type="checkbox" checked={has} disabled={busy} onChange={() => togglePerm(a.key)} />
                          <span className="perm-text">
                            <span className="perm-desc">{a.description}</span>
                            <span className="muted small perm-key">{a.key}</span>
                          </span>
                          {granted ? <span className="perm-state perm-state-granted">granted</span>
                            : revoked ? <span className="perm-state perm-state-revoked">revoked</span>
                            : has ? <span className="perm-state perm-state-role">from role</span> : null}
                        </label>
                      )
                    })}
                  </div>
                ))}
                {(user.permission_grants.length > 0 || user.permission_denies.length > 0) && (
                  <button type="button" className="link-btn small" style={{ marginTop: '0.5rem' }} disabled={busy} onClick={resetPerms}>
                    Remove all overrides for this user
                  </button>
                )}
              </>
            )}
          </>
        )}

        {confirming ? (
          <div className="alert alert-error" style={{ marginTop: '1rem' }}>
            <strong>Delete {user.username}?</strong> Their account, certificate requests and notifications will be removed
            permanently. This cannot be undone.
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
              <button className="btn btn-small btn-danger" disabled={busy} onClick={remove}>
                {busy ? 'Deleting…' : 'Yes, delete this user'}
              </button>
              <button className="btn btn-small btn-ghost" disabled={busy} onClick={() => setConfirming(false)}>Keep</button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            {can(me, 'eligibility:users') && <Link to="/eligibility" className="btn btn-small btn-outline-dark">Manage eligibility</Link>}
            {canDelete && (
              <button className="btn btn-small btn-danger" onClick={() => setConfirming(true)}>Delete user</button>
            )}
            <button className="btn btn-small" onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </div>
  )
}
