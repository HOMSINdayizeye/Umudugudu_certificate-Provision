import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, setSession } from '../api.js'
import LocationSelect from '../components/LocationSelect.jsx'
import PasswordField, { passwordIsStrong } from '../components/PasswordField.jsx'

export default function Register({ onRegister }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: '', last_name: '', username: '', email: '',
    password: '', confirm: '', isibo: '',
  })
  const [loc, setLoc] = useState({ province: '', district: '', sector: '', cell: '', village: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!passwordIsStrong(form.password)) {
      setError('Please choose a strong password that meets all the requirements.')
      return
    }
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    if (!loc.village) {
      setError('Please select your full location, down to the village.')
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
      const data = await api.register(payload)
      setSession(data.token, data.user)
      onRegister(data.user)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card register-card">
      <h1>Create your account</h1>
      <p className="muted">Register as a citizen to request certificates from Kigali City.</p>
      {error && <div className="alert alert-error">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="section-title">1 — Personal information</div>
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
            <label>Username</label>
            <input value={form.username} onChange={set('username')} required />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={form.email} onChange={set('email')} required />
          </div>
        </div>

        <div className="section-title">2 — Where you live</div>
        <LocationSelect value={loc} onChange={setLoc} />
        <div className="form-group">
          <label>Isibo (optional)</label>
          <input value={form.isibo} onChange={set('isibo')} placeholder="Name of your isibo within the village" />
        </div>

        <div className="section-title">3 — Account security</div>
        <PasswordField value={form.password} onChange={set('password')} />
        <div className="form-group">
          <label>Confirm password</label>
          <input type="password" value={form.confirm} onChange={set('confirm')} required autoComplete="new-password" />
          {form.confirm && form.confirm !== form.password && (
            <div className="field-hint field-hint-error">Passwords do not match.</div>
          )}
          {form.confirm && form.confirm === form.password && (
            <div className="field-hint field-hint-ok">✔ Passwords match.</div>
          )}
        </div>

        <button className="btn" disabled={loading}>
          {loading ? 'Creating account…' : 'Create Account'}
        </button>
      </form>
      <p className="muted">Already have an account? <Link to="/login">Login</Link></p>
    </div>
  )
}
