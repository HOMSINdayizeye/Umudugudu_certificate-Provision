import { useEffect, useState } from 'react'
import { api, getToken, setSession } from '../api.js'
import PasswordField, { passwordIsStrong } from '../components/PasswordField.jsx'

// The signed-in user's own account: details they may edit, and a password change
export default function Profile({ user, onUpdate }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', phone: '' })
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwNotice, setPwNotice] = useState('')
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (user) setForm({ first_name: user.first_name || '', last_name: user.last_name || '', email: user.email || '', phone: user.phone || '' })
  }, [user])

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function saveProfile(e) {
    e.preventDefault()
    setError(''); setNotice(''); setBusy('profile')
    try {
      const updated = await api.updateMe(form)
      setSession(getToken(), updated)
      onUpdate?.(updated)
      setNotice('Profile updated.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function savePassword(e) {
    e.preventDefault()
    setPwError(''); setPwNotice('')
    if (!passwordIsStrong(pw.new_password)) { setPwError('Please choose a strong password that meets all the requirements.'); return }
    if (pw.new_password !== pw.confirm) { setPwError('The new passwords do not match.'); return }
    setBusy('password')
    try {
      const res = await api.changePassword({ current_password: pw.current_password, new_password: pw.new_password })
      setPwNotice(res.detail)
      setPw({ current_password: '', new_password: '', confirm: '' })
    } catch (err) {
      setPwError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (!user) return <p className="muted">Loading…</p>

  return (
    <div>
      <div className="page-head"><h1>My Profile</h1></div>

      <div className="two-col">
        <div>
          <div className="card">
            <h2 className="card-title">Account</h2>
            <dl className="detail-grid">
              <dt>Username</dt><dd>{user.username}</dd>
              <dt>Role</dt><dd>{user.role_display}</dd>
              {user.village_name && (<><dt>Village</dt><dd>{user.village_name}</dd></>)}
              {user.isibo && (<><dt>Isibo</dt><dd>{user.isibo}</dd></>)}
              <dt>Name on letters</dt><dd>{user.display_name}</dd>
            </dl>
            <p className="muted small" style={{ marginBottom: 0 }}>Username, role and location are set by the administrator. Ask them if these need to change.</p>
          </div>

          <form className="card" style={{ marginTop: '1rem' }} onSubmit={saveProfile}>
            <h2 className="card-title">Contact details</h2>
            {error && <div className="alert alert-error">{error}</div>}
            {notice && <div className="alert alert-success">{notice}</div>}
            <div className="form-row">
              <div className="form-group">
                <label>First name</label>
                <input value={form.first_name} onChange={set('first_name')} required />
              </div>
              <div className="form-group">
                <label>Last name (surname)</label>
                <input value={form.last_name} onChange={set('last_name')} required />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={form.email} onChange={set('email')} required />
              </div>
              <div className="form-group">
                <label>Phone</label>
                <input value={form.phone} onChange={set('phone')} placeholder="+250 7xx xxx xxx" />
              </div>
            </div>
            {user.role !== 'citizen' && <p className="muted small">Your name and phone are printed on the letters you sign.</p>}
            <button className="btn" disabled={busy === 'profile'}>{busy === 'profile' ? 'Saving…' : 'Save Changes'}</button>
          </form>
        </div>

        <form className="card" onSubmit={savePassword}>
          <h2 className="card-title">Change password</h2>
          {pwError && <div className="alert alert-error">{pwError}</div>}
          {pwNotice && <div className="alert alert-success">{pwNotice}</div>}
          <div className="form-group">
            <label>Current password</label>
            <input type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required autoComplete="current-password" />
          </div>
          <PasswordField value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          <div className="form-group">
            <label>Confirm new password</label>
            <input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} required autoComplete="new-password" />
          </div>
          <button className="btn" disabled={busy === 'password'}>{busy === 'password' ? 'Changing…' : 'Change Password'}</button>
        </form>
      </div>
    </div>
  )
}
