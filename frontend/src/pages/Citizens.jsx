import { useEffect, useState } from 'react'
import { api, can } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'
import ExportButtons from '../components/ExportButtons.jsx'
import CategoryBadge from '../components/CategoryBadge.jsx'
import { TransferBadge } from '../components/TransferCitizenModal.jsx'
import AreaCitizens from './AreaCitizens.jsx'
import { phoneInputProps } from '../phone.js'
import { ID_TYPES, NATIONAL_ID_HINT, PASSPORT_HINT, YOUTH_MIN, YOUTH_MAX, YOUTH_ROLES, ageFromNationalId, categoryOf } from '../citizen.js'

const emptyForm = { first_name: '', last_name: '', email: '', phone: '', id_type: 'national_id', national_id: '', age: '', isibo: '' }
const AREA_LEADERS = ['village_leader', 'cell_leader', 'sector_leader', ...YOUTH_ROLES]

// Isibo leader's citizen registry: add citizens and edit their information.
// Citizens always land in the leader's own village (shown read-only).
// Village/cell/sector leaders get a read-only view of every citizen in their area instead.
export default function Citizens({ user }) {
  if (AREA_LEADERS.includes(user?.role)) return <AreaCitizens user={user} />
  return <IsiboCitizens user={user} />
}

// Identity document and age: a national ID fills the age from its birth year, a passport needs the age typed
export function IdentityFields({ value, onChange }) {
  const idType = value.id_type || 'national_id'
  const national = idType === 'national_id'
  const derived = national ? ageFromNationalId(value.national_id) : null
  const age = derived ?? value.age
  const category = age !== '' && age != null ? categoryOf(age) : null

  function setType(e) {
    const id_type = e.target.value
    const a = id_type === 'national_id' ? ageFromNationalId(value.national_id) : null
    onChange({ ...value, id_type, age: a ?? value.age })
  }

  function setNumber(e) {
    const national_id = national ? e.target.value.replace(/\D/g, '') : e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
    const a = national ? ageFromNationalId(national_id) : null
    onChange({ ...value, national_id, age: a ?? value.age })
  }

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>Identity document</label>
          <select value={idType} onChange={setType}>
            {ID_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>{national ? 'ID number' : 'Passport number'}</label>
          <input
            value={value.national_id} onChange={setNumber} required
            maxLength={national ? 16 : 20} inputMode={national ? 'numeric' : 'text'}
            pattern={national ? '[0-9]{16}' : '[A-Za-z0-9]{6,20}'} title={national ? NATIONAL_ID_HINT : PASSPORT_HINT}
            placeholder={national ? 'e.g. 1200280342388011' : 'e.g. PC123456'}
          />
          <div className="field-hint muted">{national ? NATIONAL_ID_HINT : PASSPORT_HINT}</div>
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Age</label>
          <input
            type="number" min="1" max="130" required value={age ?? ''}
            readOnly={derived != null} className={derived != null ? 'input-derived' : ''}
            onChange={(e) => onChange({ ...value, age: e.target.value })}
          />
          <div className="field-hint muted">
            {derived != null ? `Filled from the ID · born ${new Date().getFullYear() - derived}`
              : national ? 'Appears once the 16-digit ID is typed' : 'Type the age shown by the passport'}
          </div>
        </div>
        <div className="form-group">
          <label>Category</label>
          <div className="category-box">
            {category ? <CategoryBadge category={category} /> : <span className="muted small">Set from the age</span>}
            <span className="muted small">Youth: {YOUTH_MIN} to {YOUTH_MAX} years · others are citizens</span>
          </div>
        </div>
      </div>
    </>
  )
}

function IsiboCitizens({ user }) {
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
      setMessage(`Citizen "${created.name}" added as ${created.category_display.toLowerCase()} (age ${created.age}).`)
      setForm({ ...emptyForm, isibo: user?.isibo || '' })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const canAdd = can(user, 'add:citizens')
  const canEdit = can(user, 'edit:citizens')
  const canDelete = can(user, 'delete:citizens')
  const youthCount = citizens.filter((c) => c.category === 'youth').length

  async function handleDelete(c) {
    if (!window.confirm(`Delete ${c.name} (ID ${c.national_id})? Their payment records go with them. This cannot be undone.`)) return
    setError('')
    setMessage('')
    try {
      const res = await api.deleteCitizen(c.id)
      setMessage(res.detail)
      await load()
    } catch (err) {
      setError(err.message)
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

      {canAdd && <form className="card" onSubmit={handleAdd} style={{ marginBottom: '1.5rem' }}>
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
            <LocationSelect value={loc} onChange={setLoc} progressive />
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
        <IdentityFields value={form} onChange={setForm} />
        <div className="form-row">
          <div className="form-group">
            <label>Isibo name</label>
            <input value={form.isibo} onChange={set('isibo')} placeholder="Isibo within the village" />
          </div>
          <div className="form-group">
            <label>Phone number (optional)</label>
            <input {...phoneInputProps} value={form.phone} onChange={set('phone')} placeholder="0791234567 or 250791234567" />
            <div className="field-hint muted">{phoneInputProps.title}</div>
          </div>
        </div>
        <div className="form-group">
          <label>Email (optional)</label>
          <input type="email" value={form.email} onChange={set('email')} />
        </div>
        <button className="btn" disabled={busy}>{busy ? 'Adding…' : 'Add Citizen'}</button>
      </form>}

      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>
          Registered citizens ({citizens.length})
          {citizens.length > 0 && <span className="muted" style={{ marginLeft: '0.6rem', fontWeight: 500, letterSpacing: 0, textTransform: 'none' }}>{youthCount} youth · {citizens.length - youthCount} citizens</span>}
        </div>
        {citizens.length === 0 ? (
          <p className="muted">No citizens registered yet.{canAdd ? ' Use the form above to add one.' : ''}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <ExportButtons
              title="Registered citizens"
              columns={['Name', 'Isibo', 'Phone', 'Email', 'Document', 'ID number', 'Age', 'Category', 'Village', 'Transferred from']}
              rows={citizens.map((c) => [c.name, c.isibo || '', c.phone || '', c.email || '', c.id_type_display || '', c.national_id, c.age,
                c.category_display || '', c.village_name || '', c.transferred_from_village_name || ''])}
            />
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Isibo</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>ID number</th>
                  <th>Age</th>
                  <th>Category</th>
                  <th>Village</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {citizens.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}<TransferBadge citizen={c} /></td>
                    <td>{c.isibo || '—'}</td>
                    <td>{c.phone || '—'}</td>
                    <td>{c.email || '—'}</td>
                    <td>{c.national_id}{c.id_type === 'passport' && <div className="muted small">Passport</div>}</td>
                    <td>{c.age || '—'}</td>
                    <td><CategoryBadge category={c.category} /></td>
                    <td>{c.village_name}</td>
                    <td className="actions-cell">
                      {canEdit && <button className="btn btn-small" onClick={() => setEditing({ ...c })}>Edit</button>}
                      {canDelete && <button className="btn btn-small btn-danger" onClick={() => handleDelete(c)}>Delete</button>}
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
              <IdentityFields value={editing} onChange={setEditing} />
              <div className="form-row">
                <div className="form-group">
                  <label>Isibo name</label>
                  <input value={editing.isibo}
                         onChange={(e) => setEditing({ ...editing, isibo: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Phone number (optional)</label>
                  <input {...phoneInputProps} value={editing.phone}
                         onChange={(e) => setEditing({ ...editing, phone: e.target.value })} />
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
