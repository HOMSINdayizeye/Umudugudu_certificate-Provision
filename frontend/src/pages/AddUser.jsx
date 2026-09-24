import { useState } from 'react'
import { api } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'
import PasswordField, { passwordIsStrong } from '../components/PasswordField.jsx'
import PasswordInput from '../components/PasswordInput.jsx'
import { phoneInputProps } from '../phone.js'

// Every account role the system knows, in the order shown in dropdowns (also used by the Users page filter)
export const ROLES = [
  { value: 'citizen', label: 'Citizen' },
  { value: 'isibo_leader', label: 'Isibo Leader' },
  { value: 'village_leader', label: 'Village Leader' },
  { value: 'cell_leader', label: 'Cell Leader' },
  { value: 'sector_leader', label: 'Sector Leader' },
  { value: 'cell_youth_leader', label: 'Cell Youth Leader' },
  { value: 'sector_youth_leader', label: 'Sector Youth Leader' },
  { value: 'security_volunteer', label: 'Security Volunteer' },
  { value: 'cleaning_volunteer', label: 'Cleaning Service Volunteer' },
  { value: 'system_admin', label: 'System Admin' },
]

// Phone format lives in phone.js; re-exported because the Users page imports it from here
export { PHONE_PATTERN, PHONE_HINT } from '../phone.js'

// How deep the location must be selected for each role (also used when editing a user)
export const LOCATION_DEPTH = {
  sector_leader: 'sector',
  cell_leader: 'cell',
  sector_youth_leader: 'sector',
  cell_youth_leader: 'cell',
  system_admin: 'village',
}

// Heading of the location section for roles whose authority is a whole cell or sector
export const AUTHORITY_LABEL = {
  sector_leader: 'Sector of authority',
  cell_leader: 'Cell of authority',
  sector_youth_leader: 'Sector of authority (youth)',
  cell_youth_leader: 'Cell of authority (youth)',
}

const emptyForm = {
  first_name: '', last_name: '', username: '', email: '', phone: '',
  password: '', confirm: '', role: 'citizen', isibo: '',
}
const emptyLoc = { province: '', district: '', sector: '', cell: '', village: '' }

export default function AddUser() {
  const [form, setForm] = useState(emptyForm)
  const [loc, setLoc] = useState(emptyLoc)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const depth = LOCATION_DEPTH[form.role] || 'village'

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!passwordIsStrong(form.password)) {
      setError('Please choose a strong password that meets all the requirements.')
      return
    }
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    if (form.role !== 'system_admin' && !loc[depth]) {
      setError(`Please select the location down to the ${depth} for this role.`)
      return
    }
    setLoading(true)
    try {
      const { confirm, ...payload } = form
      payload.province = loc.province || null
      payload.district = loc.district || null
      payload.sector = loc.sector || null
      payload.cell = loc.cell || null
      payload.village = loc.village || null
      const created = await api.createUser(payload)
      setMessage(`User "${created.username}" created as ${created.role_display}.`)
      setForm(emptyForm)
      setLoc(emptyLoc)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-head"><h1>Add User</h1></div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <form className="card" onSubmit={handleSubmit}>
        <div className="section-title">Role</div>
        <div className="form-group">
          <label>User role</label>
          <select value={form.role} onChange={set('role')}>
            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>

        <div className="section-title">Personal information</div>
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
        <div className="form-group">
          <label>Phone (optional)</label>
          <input {...phoneInputProps} value={form.phone} onChange={set('phone')} placeholder="0791234567 or 250791234567" />
          <div className="field-hint muted">{phoneInputProps.title}</div>
        </div>

        {form.role !== 'system_admin' && (
          <>
            <div className="section-title">
              {AUTHORITY_LABEL[form.role] || 'Location'}
            </div>
            <p className="muted small" style={{ marginTop: 0 }}>Pick the province first; each next level appears once the one above it is chosen.</p>
            <LocationSelect value={loc} onChange={setLoc} progressive upTo={depth === 'sector' ? 'sector' : depth === 'cell' ? 'cell' : 'village'} />
            {(form.role === 'isibo_leader' || form.role === 'citizen') && (
              <div className="form-group">
                <label>Isibo {form.role === 'isibo_leader' ? '(the isibo they lead)' : '(optional)'}</label>
                <input value={form.isibo} onChange={set('isibo')} required={form.role === 'isibo_leader'} placeholder="e.g. Amahoro" />
              </div>
            )}
          </>
        )}

        <div className="section-title">Account security</div>
        <PasswordField value={form.password} onChange={set('password')} />
        <div className="form-group">
          <label>Confirm password</label>
          <PasswordInput value={form.confirm} onChange={set('confirm')} required autoComplete="new-password" placeholder="Repeat the password" />
        </div>

        <button className="btn" disabled={loading}>{loading ? 'Creating…' : 'Create User'}</button>
      </form>
    </div>
  )
}
