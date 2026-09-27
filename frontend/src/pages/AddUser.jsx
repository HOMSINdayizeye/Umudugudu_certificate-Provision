import { useEffect, useState } from 'react'
import { api } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'
import PasswordField, { passwordIsStrong } from '../components/PasswordField.jsx'
import PasswordInput from '../components/PasswordInput.jsx'
import Spinner from '../components/Spinner.jsx'
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

const LEVELS = ['province', 'district', 'sector', 'cell', 'village']

const emptyForm = {
  first_name: '', last_name: '', username: '', email: '', phone: '',
  password: '', confirm: '', role: 'citizen', isibo: '',
}
const emptyLoc = { province: '', district: '', sector: '', cell: '', village: '' }

// Split an 8-digit village id into the ids the cascading selector expects
function locFromVillage(village) {
  const s = village ? String(village) : ''
  return { province: s.slice(0, 1), district: s.slice(0, 2), sector: s.slice(0, 4), cell: s.slice(0, 6), village: s.slice(0, 8) }
}

// Deepest location level chosen so far, e.g. a cell code when no village is picked yet
function deepestCode(loc) {
  for (const level of [...LEVELS].reverse()) if (loc[level]) return loc[level]
  return ''
}

function suggestUsername(first, last) {
  return `${(first || '').trim().slice(0, 1)}${(last || '').trim()}`.toLowerCase().replace(/[^a-z0-9]/g, '')
}

export default function AddUser() {
  const [form, setForm] = useState(emptyForm)
  const [loc, setLoc] = useState(emptyLoc)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  // Optional start from the citizen registry: filter by area and name, then take the citizen's details into the form
  const [pickOpen, setPickOpen] = useState(false)
  const [pickLoc, setPickLoc] = useState(emptyLoc)
  const [pickQ, setPickQ] = useState('')
  const [pick, setPick] = useState({ count: 0, citizens: [] })
  const [pickBusy, setPickBusy] = useState(false)
  const [source, setSource] = useState(null)
  // While true the location section shows the chosen citizen's village instead of the selector
  const [locFromSource, setLocFromSource] = useState(false)

  const depth = LOCATION_DEPTH[form.role] || 'village'
  const pickCode = deepestCode(pickLoc)

  useEffect(() => {
    if (!pickOpen) return undefined
    if (!pickCode && pickQ.trim().length < 2) { setPick({ count: 0, citizens: [] }); return undefined }
    const t = setTimeout(async () => {
      setPickBusy(true)
      try {
        setPick(await api.pickCitizens({ location: pickCode, q: pickQ.trim() }))
      } catch (err) {
        setError(err.message)
      } finally {
        setPickBusy(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [pickOpen, pickCode, pickQ])

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value })
  }

  function applyCitizen(c) {
    setForm((f) => ({
      ...f, first_name: c.first_name, last_name: c.last_name, email: c.email || f.email, phone: c.phone || f.phone,
      isibo: c.isibo || f.isibo, username: f.username || suggestUsername(c.first_name, c.last_name),
    }))
    setLoc(locFromVillage(c.village))
    setLocFromSource(true)
    setSource(c)
    setPickOpen(false)
    setError('')
  }

  function clearSource() {
    setSource(null)
    setLocFromSource(false)
    setForm((f) => ({ ...f, first_name: '', last_name: '', email: '', phone: '', isibo: '', username: '' }))
    setLoc(emptyLoc)
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
      // Levels below the role's depth stay empty (a cell leader picked from a citizen keeps only the cell)
      const keep = LEVELS.slice(0, LEVELS.indexOf(depth) + 1)
      for (const level of LEVELS) payload[level] = keep.includes(level) && loc[level] ? loc[level] : null
      const created = await api.createUser(payload)
      setMessage(`User "${created.username}" created as ${created.role_display}.`)
      setForm(emptyForm)
      setLoc(emptyLoc)
      setSource(null)
      setLocFromSource(false)
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

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="section-title" style={{ marginTop: 0 }}>Start from a registered citizen <span className="muted small" style={{ textTransform: 'none', letterSpacing: 0 }}>(optional)</span></div>
        {source ? (
          <div className="pick-source">
            <span>
              <span className="pick-name">{source.name}</span>
              <span className="muted small"> · ID {source.national_id} · {source.location_path}{source.isibo ? ` · Isibo ${source.isibo}` : ''}</span>
            </span>
            <span className="btn-row">
              <button type="button" className="link-btn" onClick={() => setPickOpen(true)}>Pick another</button>
              <button type="button" className="link-btn" onClick={clearSource}>Clear</button>
            </span>
          </div>
        ) : (
          <p className="muted small" style={{ marginTop: 0 }}>Filter the citizen registry by area, choose the person, and their name, contact, isibo and village fill the form below.</p>
        )}
        {!pickOpen && !source && <button type="button" className="btn btn-small btn-outline-dark" onClick={() => setPickOpen(true)}>Find a citizen</button>}
        {pickOpen && (
          <>
            <LocationSelect value={pickLoc} onChange={setPickLoc} progressive />
            <div className="form-group" style={{ marginTop: '0.75rem' }}>
              <label>Search by name, ID or phone</label>
              <input value={pickQ} onChange={(e) => setPickQ(e.target.value)} placeholder={pickCode ? 'Narrow the list (optional)' : 'Type at least 2 letters, or choose an area above'} />
            </div>
            {pickBusy ? <Spinner label="Searching…" /> : (pickCode || pickQ.trim().length >= 2) && (
              pick.citizens.length === 0 ? <p className="muted small">No living citizens match.</p> : (
                <>
                  <ul className="pick-results">
                    {pick.citizens.map((c) => (
                      <li key={c.id}>
                        <span>
                          <span className="pick-name">{c.name}</span>
                          {c.has_account && <span className="badge badge-pending badge-inline">Has account</span>}
                          <div className="muted small">ID {c.national_id}{c.phone ? ` · ${c.phone}` : ''}{c.email ? ` · ${c.email}` : ''} · {c.location_path}{c.isibo ? ` · Isibo ${c.isibo}` : ''}</div>
                        </span>
                        <button type="button" className="btn btn-small" onClick={() => applyCitizen(c)}>Use</button>
                      </li>
                    ))}
                  </ul>
                  {pick.count > pick.citizens.length && <p className="muted small">Showing {pick.citizens.length} of {pick.count}; narrow the area or search to see the rest.</p>}
                </>
              )
            )}
            <div className="btn-row" style={{ marginTop: '0.75rem' }}>
              <button type="button" className="link-btn" onClick={() => setPickOpen(false)}>Close</button>
            </div>
          </>
        )}
      </div>

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
            {locFromSource && source ? (
              <div className="loc-summary">
                <span>{source.location_path}{depth !== 'village' && <span className="muted small"> · only the {depth} is kept for this role</span>}</span>
                <button type="button" className="link-btn" onClick={() => { setLocFromSource(false); setLoc(emptyLoc) }}>Change</button>
              </div>
            ) : (
              <>
                <p className="muted small" style={{ marginTop: 0 }}>Pick the province first; each next level appears once the one above it is chosen.</p>
                <LocationSelect value={loc} onChange={setLoc} progressive upTo={depth === 'sector' ? 'sector' : depth === 'cell' ? 'cell' : 'village'} />
              </>
            )}
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
