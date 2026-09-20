import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getUser, can } from '../api.js'
import ExportButtons from '../components/ExportButtons.jsx'
import Pagination from '../components/Pagination.jsx'
import Spinner from '../components/Spinner.jsx'
import LocationSelect from '../components/LocationSelect.jsx'
import { passwordIsStrong } from '../components/PasswordField.jsx'
import { ROLES, LOCATION_DEPTH, PHONE_PATTERN, PHONE_HINT } from './AddUser.jsx'

// Users come from the server five per page; scrolling past the end (or the page buttons) turns the page
const PAGE_SIZE = 5

const fmt = (d) => (d ? new Date(d).toLocaleDateString() : '—')

// System admin: every account in the system with its role and place, searched and filtered on the server.
export default function Users() {
  const [users, setUsers] = useState(null)
  const [count, setCount] = useState(0) // matches for the current search/role
  const [total, setTotal] = useState(0) // every account in the system
  const [counts, setCounts] = useState({}) // users per role
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [q, setQ] = useState('')
  const [role, setRole] = useState('all')
  const [selected, setSelected] = useState(null)
  const [catalog, setCatalog] = useState(null) // permission catalog, loaded once for the pop-up
  const requestId = useRef(0) // ignore responses of searches the user has already moved past
  const lastFlip = useRef(0) // time of the last scroll-triggered page change

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  useEffect(() => {
    if (can(getUser(), 'permissions:users')) {
      api.permissionCatalog().then((d) => setCatalog(d.catalog)).catch(() => {})
    }
  }, [])

  // Each page replaces the one before it: only five users are ever on screen
  async function fetchPage(pageNumber) {
    const id = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const data = await api.listUsers({ q: q.trim(), role, limit: PAGE_SIZE, offset: (pageNumber - 1) * PAGE_SIZE })
      if (id !== requestId.current) return
      setUsers(data.results)
      setCount(data.count)
      setTotal(data.total)
      setCounts(data.role_counts || {})
    } catch (err) {
      if (id === requestId.current) setError(err.message)
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }

  // New search or role: wait a moment for typing to settle, then start again from the first page
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchPage(1) }, q ? 300 : 0)
    return () => clearTimeout(t)
  }, [q, role])

  function goTo(n) {
    if (n < 1 || n > totalPages || n === page || loading) return
    setPage(n)
    fetchPage(n)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Scrolling past the bottom of the list turns to the next page; scrolling up from the top goes back one
  useEffect(() => {
    function onWheel(e) {
      if (loading || selected) return
      const now = Date.now()
      if (now - lastFlip.current < 800) return
      const root = document.documentElement
      const atBottom = window.innerHeight + window.scrollY >= root.scrollHeight - 4
      const atTop = window.scrollY <= 0
      if (e.deltaY > 0 && atBottom && page < totalPages) {
        lastFlip.current = now
        goTo(page + 1)
      } else if (e.deltaY < 0 && atTop && page > 1) {
        lastFlip.current = now
        goTo(page - 1)
      }
    }
    window.addEventListener('wheel', onWheel, { passive: true })
    return () => window.removeEventListener('wheel', onWheel)
  }, [loading, selected, page, totalPages])

  const visible = users || []

  return (
    <div>
      <div className="page-head">
        <h1>All Users{users ? ` (${total})` : ''}</h1>
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
              title={`Users${role !== 'all' ? ` — ${ROLES.find((r) => r.value === role)?.label}` : ''} (page ${page} of ${totalPages})`}
              columns={['#', 'Username', 'Name', 'Email', 'Phone', 'Role', 'Place', 'Isibo', 'Eligible', 'Joined']}
              rows={visible.map((u, i) => [i + 1, u.username, `${u.first_name} ${u.last_name}`.trim(), u.email, u.phone || '',
                u.role_display, u.location_name || '', u.isibo || '', u.is_eligible ? 'Yes' : 'No', fmt(u.date_joined)])}
            />
            <table className="table">
              <thead>
                <tr><th>#</th><th>Username</th><th>Name</th><th>Role</th><th>Place</th><th>Contact</th><th></th></tr>
              </thead>
              <tbody>
                {visible.map((u, idx) => (
                  <tr key={u.id} className="row-clickable" onClick={() => setSelected(u)}>
                    <td>{(page - 1) * PAGE_SIZE + idx + 1}</td>
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
            <Pagination page={page} totalPages={totalPages} total={count} label="user" onChange={goTo} />
            <div className="muted small" style={{ textAlign: 'center', padding: '0.5rem 0' }}>
              {loading ? <Spinner label="Loading page…" />
                : totalPages > 1
                  ? (page < totalPages ? 'Scroll down for the next page' : 'Last page') + (page > 1 ? ' · scroll up for the previous one' : '')
                  : `All ${count} user${count === 1 ? '' : 's'} shown`}
            </div>
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
            setMessage(text)
            // Refill the page from the server so it shows five again (or step back if the last page emptied)
            const lastPage = Math.max(1, Math.ceil((count - 1) / PAGE_SIZE))
            const target = Math.min(page, lastPage)
            setPage(target)
            fetchPage(target)
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
  // The permission list is long, so it stays hidden behind one button until the admin wants it
  const [showPerms, setShowPerms] = useState(false)
  const [editing, setEditing] = useState(false)

  // Same rules as the server: the permission, never yourself, admins only by admins, superusers only by superusers
  const meAdmin = me?.is_superuser || me?.is_admin_role
  const outranks = (!user.is_superuser || me?.is_superuser) && (!(user.is_superuser || user.is_admin_role) || meAdmin)
  const canDelete = me && can(me, 'delete:users') && user.id !== me.id && outranks
  const canEdit = me && can(me, 'edit:users') && outranks
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
        {editing ? (
          <EditUserForm
            user={user}
            isSelf={user.id === me?.id}
            onCancel={() => setEditing(false)}
            onSaved={(u) => { setEditing(false); setSaved('Account details updated.'); onUpdated(u) }}
          />
        ) : (
        <>
        {error && <div className="alert alert-error">{error}</div>}
        {saved && <div className="field-hint field-hint-ok">{saved}</div>}
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
            ) : !showPerms ? (
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-small btn-outline-dark" onClick={() => setShowPerms(true)}>
                  Manage permissions
                </button>
                <span className="muted small">
                  {user.permissions.length} allowed
                  {user.permission_grants.length + user.permission_denies.length > 0
                    ? ` · ${user.permission_grants.length} granted, ${user.permission_denies.length} revoked beyond the role`
                    : ' · all from the role'}
                </span>
              </div>
            ) : (
              <>
                <button type="button" className="link-btn small" style={{ marginBottom: '0.5rem' }} onClick={() => setShowPerms(false)}>
                  Hide permissions
                </button>
                <p className="muted small" style={{ marginTop: 0 }}>
                  Ticked = allowed. Grey ones come from the {user.role_display} role; tick to give this user more, untick to take a role permission away.
                </p>
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
            {canEdit && (
              <button className="btn btn-small" onClick={() => { setError(''); setSaved(''); setEditing(true) }}>Edit user</button>
            )}
            {can(me, 'eligibility:users') && <Link to="/eligibility" className="btn btn-small btn-outline-dark">Manage eligibility</Link>}
            {canDelete && (
              <button className="btn btn-small btn-danger" onClick={() => setConfirming(true)}>Delete user</button>
            )}
            <button className="btn btn-small btn-ghost" onClick={onClose}>Close</button>
          </div>
        )}
        </>
        )}
      </div>
    </div>
  )
}

// Admin edits an account: identity, contact, role, place, active flag, and an optional password reset.
function EditUserForm({ user, isSelf, onCancel, onSaved }) {
  const [form, setForm] = useState({
    first_name: user.first_name || '', last_name: user.last_name || '', username: user.username || '',
    email: user.email || '', phone: user.phone || '', role: user.role, isibo: user.isibo || '',
    is_active: user.is_active, password: '', confirm: '',
  })
  // The place is kept as-is unless the admin chooses a new one from the province down
  const [changingPlace, setChangingPlace] = useState(false)
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const depth = LOCATION_DEPTH[form.role] || 'village'
  const roleChanged = form.role !== user.role
  const hasPlace = !!user[depth]
  const needsPlace = form.role !== 'system_admin' && (changingPlace || !hasPlace)
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (form.password && !passwordIsStrong(form.password)) {
      setError('The new password must have 8+ characters with upper and lower case letters, a number and a special character.')
      return
    }
    if (form.password && form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    if (needsPlace && !loc[depth]) {
      setError(`Select the location down to the ${depth} for this role.`)
      return
    }
    setBusy(true)
    try {
      const { confirm, password, ...payload } = form
      if (password) payload.password = password
      if (needsPlace) {
        for (const level of ['province', 'district', 'sector', 'cell', 'village']) payload[level] = loc[level] || null
      }
      if (isSelf) {
        delete payload.role
        delete payload.is_active
      }
      onSaved(await api.updateUser(user.id, payload))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="section-title" style={{ marginTop: 0 }}>Account</div>
      <div className="form-row">
        <div className="form-group">
          <label>First name</label>
          <input value={form.first_name} onChange={set('first_name')} required placeholder="e.g. Jean" />
        </div>
        <div className="form-group">
          <label>Last name</label>
          <input value={form.last_name} onChange={set('last_name')} required placeholder="e.g. Mugisha" />
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Username</label>
          <input value={form.username} onChange={set('username')} required placeholder="e.g. jmugisha" />
        </div>
        <div className="form-group">
          <label>Email</label>
          <input type="email" value={form.email} onChange={set('email')} required placeholder="name@example.com" />
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Phone</label>
          <input type="tel" value={form.phone} onChange={set('phone')} placeholder="250791234567"
                 pattern={PHONE_PATTERN} title={PHONE_HINT} inputMode="numeric" maxLength={12} />
          <div className="field-hint muted">{PHONE_HINT}</div>
        </div>
        <div className="form-group">
          <label>Role</label>
          <select value={form.role} onChange={set('role')} disabled={isSelf}>
            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          {isSelf && <div className="field-hint muted">You cannot change your own role.</div>}
        </div>
      </div>
      {!isSelf && (
        <label className="perm-row" style={{ marginBottom: '0.5rem' }}>
          <input type="checkbox" checked={form.is_active} onChange={set('is_active')} />
          <span className="perm-text"><span className="perm-desc">Account is active (unticked users cannot sign in)</span></span>
        </label>
      )}

      {form.role !== 'system_admin' && (
        <>
          <div className="section-title">
            {form.role === 'sector_leader' ? 'Sector of authority' : form.role === 'cell_leader' ? 'Cell of authority' : 'Location'}
          </div>
          {!needsPlace ? (
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span>{user.location_name || '—'}</span>
              <button type="button" className="link-btn small" onClick={() => setChangingPlace(true)}>change place</button>
            </div>
          ) : (
            <>
              <p className="muted small" style={{ marginTop: 0 }}>
                {roleChanged && !hasPlace ? `This role needs a ${depth}. ` : ''}Pick the province first; each next level appears once the one above it is chosen.
              </p>
              <LocationSelect value={loc} onChange={setLoc} progressive upTo={depth} />
              {hasPlace && (
                <button type="button" className="link-btn small" onClick={() => { setChangingPlace(false); setLoc({ province: '', district: '', sector: '', cell: '', village: '' }) }}>
                  keep current place
                </button>
              )}
            </>
          )}
          {(form.role === 'isibo_leader' || form.role === 'citizen') && (
            <div className="form-group" style={{ marginTop: '0.75rem' }}>
              <label>Isibo {form.role === 'isibo_leader' ? '(the isibo they lead)' : '(optional)'}</label>
              <input value={form.isibo} onChange={set('isibo')} required={form.role === 'isibo_leader'} placeholder="e.g. Amahoro" />
            </div>
          )}
        </>
      )}

      <div className="section-title">Reset password (optional)</div>
      <p className="muted small" style={{ marginTop: 0 }}>Leave blank to keep the current password.</p>
      <div className="form-row">
        <div className="form-group">
          <label>New password</label>
          <input type="password" value={form.password} onChange={set('password')} autoComplete="new-password" placeholder="Leave blank to keep" />
        </div>
        <div className="form-group">
          <label>Confirm new password</label>
          <input type="password" value={form.confirm} onChange={set('confirm')} autoComplete="new-password" placeholder="Repeat the new password" />
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
        <button className="btn btn-small" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
        <button type="button" className="btn btn-small btn-ghost" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}
