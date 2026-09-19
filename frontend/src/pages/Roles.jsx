import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Spinner from '../components/Spinner.jsx'

// Admin: what each role is allowed to do. Ticks are saved per role; individual users can still be
// given or refused single permissions from the Users page.
export default function Roles() {
  const [data, setData] = useState(null)
  const [role, setRole] = useState('isibo_leader')
  const [draft, setDraft] = useState(null) // permission keys being edited for the selected role
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.permissionCatalog().then(setData).catch((err) => setError(err.message))
  }, [])

  const current = data?.roles.find((r) => r.role === role)
  // Start a fresh draft whenever the selected role (or freshly loaded data) changes
  useEffect(() => { setDraft(current ? [...current.permissions] : null) }, [role, data])

  const dirty = !!current && !!draft && (draft.length !== current.permissions.length
    || draft.some((k) => !current.permissions.includes(k)))

  function toggle(key) {
    setDraft((d) => (d.includes(key) ? d.filter((k) => k !== key) : [...d, key]))
  }

  function toggleGroup(group, on) {
    const keys = group.actions.map((a) => a.key)
    setDraft((d) => (on ? [...new Set([...d, ...keys])] : d.filter((k) => !keys.includes(k))))
  }

  async function save() {
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const res = await api.setRolePermissions(role, draft)
      setData((d) => ({ ...d, roles: res.roles }))
      setMessage(`Permissions saved for ${current.label}.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const res = await api.resetRolePermissions(role)
      setData((d) => ({ ...d, roles: res.roles }))
      setMessage(`${current.label} is back to the default permissions.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="page-head"><h1>Roles &amp; Permissions</h1></div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {!data ? (
        <div className="card"><Spinner label="Loading roles…" /></div>
      ) : (
        <div className="roles-layout">
          <div className="card role-list">
            <div className="section-title" style={{ marginTop: 0 }}>Roles</div>
            {data.roles.map((r) => (
              <button
                key={r.role}
                type="button"
                className={`role-item ${r.role === role ? 'role-item-active' : ''}`}
                onClick={() => setRole(r.role)}
              >
                <span className="role-name">{r.label}</span>
                <span className="muted small">
                  {r.users} user{r.users === 1 ? '' : 's'} · {r.locked ? 'all' : r.permissions.length} permission{r.permissions.length === 1 && !r.locked ? '' : 's'}
                  {r.customized && !r.locked ? ' · edited' : ''}
                </span>
              </button>
            ))}
          </div>

          {current && draft && (
            <div className="card">
              <div className="page-head" style={{ marginBottom: '0.5rem' }}>
                <h2 style={{ margin: 0 }}>{current.label}</h2>
                {current.customized && !current.locked && (
                  <span className="muted small">
                    Edited {current.updated_at ? new Date(current.updated_at).toLocaleDateString() : ''}{current.updated_by ? ` by ${current.updated_by}` : ''}
                  </span>
                )}
              </div>

              {current.locked ? (
                <div className="info-strip">Administrators always hold every permission. This role cannot be changed.</div>
              ) : (
                <p className="muted small" style={{ marginTop: 0 }}>
                  Tick what every {current.label.toLowerCase()} may do. Leaders still act only inside their own area.
                  Untick to revoke. Individual users can be adjusted from the Users page.
                </p>
              )}

              {data.catalog.map((group) => {
                const keys = group.actions.map((a) => a.key)
                const onCount = keys.filter((k) => draft.includes(k)).length
                return (
                  <div key={group.resource} className="perm-group">
                    <div className="perm-group-head">
                      <span className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>{group.label}</span>
                      {!current.locked && (
                        <button type="button" className="link-btn small" onClick={() => toggleGroup(group, onCount < keys.length)}>
                          {onCount < keys.length ? 'Allow all' : 'Revoke all'}
                        </button>
                      )}
                    </div>
                    {group.actions.map((a) => {
                      const on = current.locked || draft.includes(a.key)
                      const isDefault = current.defaults.includes(a.key)
                      return (
                        <label key={a.key} className={`perm-row ${on ? 'perm-on' : ''}`}>
                          <input type="checkbox" checked={on} disabled={current.locked} onChange={() => toggle(a.key)} />
                          <span className="perm-text">
                            <span className="perm-desc">{a.description}</span>
                            <span className="muted small perm-key">{a.key}{isDefault ? ' · default' : ''}</span>
                          </span>
                        </label>
                      )
                    })}
                  </div>
                )
              })}

              {!current.locked && (
                <div className="btn-row" style={{ marginTop: '1.25rem' }}>
                  <button className="btn" disabled={busy || !dirty} onClick={save}>{busy ? 'Saving…' : 'Save Permissions'}</button>
                  {dirty && (
                    <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => setDraft([...current.permissions])}>Discard changes</button>
                  )}
                  {current.customized && (
                    <button type="button" className="btn btn-outline-dark" disabled={busy} onClick={reset}>Reset to defaults</button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
