import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, setSession } from '../api.js'
import PasswordInput from '../components/PasswordInput.jsx'

export default function Login({ onLogin }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await api.login(form)
      setSession(data.token, data.user)
      onLogin(data.user)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card auth-card">
      <h1>Login</h1>
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Username or Email</label>
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
            autoFocus
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <PasswordInput
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            autoComplete="current-password"
          />
        </div>
        <button className="btn" disabled={loading}>{loading ? 'Logging in…' : 'Login'}</button>
        <p className="muted small" style={{ marginTop: '1rem', marginBottom: 0 }}>
          <Link to="/reset-password">Forgot your password?</Link> A code will be sent to your email.
        </p>
      </form>
    </div>
  )
}
