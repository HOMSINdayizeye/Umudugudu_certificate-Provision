import { useEffect, useState } from 'react'
import { api } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'

const emptyForm = { first_name: '', last_name: '', email: '', phone: '', national_id: '', age: '', isibo: '' }

// Isibo leader's citizen registry: add citizens and edit their information.
// Citizens always land in the leader's own village (shown read-only).
export default function Citizens({ user }) {
  const [citizens, setCitizens] = useState([])
  const [form, setForm] = useState({ ...emptyForm, isibo: user?.isibo || '' })
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })
  const [editing, setEditing] = useState(null) // citizen being edited, or null
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  // Admin accounts without an assigned village must pick where the citizen lives
  const needsVillagePicker = !user?.village && (user?.is_admin_role || user?.is_superuser)

  async function load() {
    try {
      const data = await api.listCitizens()
      setCitizens(data.citizens)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value })
  }

  async function handleAdd(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (needsVillagePicker && !loc.village) {
      setError('Please select the citizen’s village.')
      return
    }
    setBusy(true)
    try {
      const payload = { ...form, age: Number(form.age) }
      if (needsVillagePicker) payload.village = loc.village
      const created = await api.addCitizen(payload)
      setMessage(`Citizen "${created.name}" added.`)
      setForm({ ...emptyForm, isibo: user?.isibo || '' })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleEditSave(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const updated = await api.updateCitizen(editing.id, { ...editing, age: Number(editing.age) })
      setMessage(`Citizen "${updated.name}" updated.`)
      setEditing(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Citizens {user?.isibo ? `— Isibo ${user.isibo}` : ''}</h1>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <form className="card" onSubmit={handleAdd} style={{ marginBottom: '1.5rem' }}>
        <div className="section-title">Add a citizen</div>

        {user?.village ? (
          <div className="form-group">
            <label>Village</label>
            <input value={user.village_name || `Village ${user.village}`} disabled />
            <div className="field-hint muted">Citizens you add belong to your village.</div>
          </div>
        ) : needsVillagePicker ? (
          <>
            <div className="section-title" style={{ fontSize: '0.95rem' }}>Citizen's village</div>
            <LocationSelect value={loc} onChange={setLoc} />
          </>
        ) : null}

        <div className="form-row">
          <div className="form-group">
            <label>First name</label>
            <input value={form.first_name} onChange={set('first_name')} required />
          </div>
          <div className="form-group">
            <label>Last name</label>
            <input value={form.last_name} onChange={set('last_name')} required />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>ID number</label>
            <input value={form.national_id} onChange={set('national_id')} maxLength={16} required />
          </div>
          <div className="form-group">
            <label>Age</label>
            <input type="number" min="1" max="130" value={form.age} onChange={set('age')} required />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Isibo name</label>
            <input value={form.isibo} onChange={set('isibo')} placeholder="Isibo within the village" />
          </div>
          <div className="form-group">
            <label>Phone number (optional)</label>
            <input value={form.phone} onChange={set('phone')} maxLength={20} />
          </div>
        </div>
        <div className="form-group">
          <label>Email (optional)</label>
          <input type="email" value={form.email} onChange={set('email')} />
        </div>
        <button className="btn" disabled={busy}>{busy ? 'Adding…' : 'Add Citizen'}</button>
      </form>

      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>Registered citizens ({citizens.length})</div>
        {citizens.length === 0 ? (
          <p className="muted">No citizens registered yet. Use the form above to add one.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Isibo</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>ID number</th>
                  <th>Age</th>
                  <th>Village</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {citizens.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.isibo || '—'}</td>
                    <td>{c.phone || '—'}</td>
                    <td>{c.email || '—'}</td>
                    <td>{c.national_id}</td>
                    <td>{c.age || '—'}</td>
                    <td>{c.village_name}</td>
                    <td>
                      <button className="btn btn-small" onClick={() => setEditing({ ...c })}>Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <div className="modal-overlay" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit citizen</h2>
            <form onSubmit={handleEditSave}>
              <div className="form-row">
                <div className="form-group">
                  <label>First name</label>
                  <input value={editing.first_name}
                         onChange={(e) => setEditing({ ...editing, first_name: e.target.value })} required />
                </div>
                <div className="form-group">
                  <label>Last name</label>
                  <input value={editing.last_name}
                         onChange={(e) => setEditing({ ...editing, last_name: e.target.value })} required />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>ID number</label>
                  <input value={editing.national_id}
                         onChange={(e) => setEditing({ ...editing, national_id: e.target.value })} maxLength={16} required />
                </div>
                <div className="form-group">
                  <label>Age</label>
                  <input type="number" min="1" max="130" value={editing.age}
                         onChange={(e) => setEditing({ ...editing, age: e.target.value })} required />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Isibo name</label>
                  <input value={editing.isibo}
                         onChange={(e) => setEditing({ ...editing, isibo: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Phone number (optional)</label>
                  <input value={editing.phone}
                         onChange={(e) => setEditing({ ...editing, phone: e.target.value })} maxLength={20} />
                </div>
              </div>
              <div className="form-group">
                <label>Email (optional)</label>
                <input type="email" value={editing.email}
                       onChange={(e) => setEditing({ ...editing, email: e.target.value })} />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save Changes'}</button>
                <button type="button" className="btn btn-outline-dark" onClick={() => setEditing(null)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
