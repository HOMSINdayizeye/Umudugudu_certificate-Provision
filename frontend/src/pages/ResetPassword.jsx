import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import PasswordField, { passwordIsStrong } from '../components/PasswordField.jsx'
import PasswordInput from '../components/PasswordInput.jsx'

// Forgot password: 1) who are you → a 6-digit code is emailed (or texted) to the account, 2) code + new password.
// The email's link opens this page with ?identifier=&code= already filled in.
export default function ResetPassword() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const fromLink = !!(params.get('identifier') && params.get('code'))
  const [step, setStep] = useState(fromLink ? 2 : 1)
  const [identifier, setIdentifier] = useState(params.get('identifier') || '')
  const [code, setCode] = useState(params.get('code') || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [sent, setSent] = useState(null)       // {channel, sent_to, resend_in, can_use_email, can_use_sms, debug_code?}
  const [resendIn, setResendIn] = useState(0)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (resendIn <= 0) return undefined
    const t = setTimeout(() => setResendIn((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [resendIn])

  async function requestCode(e, channel) {
    e?.preventDefault?.()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const res = await api.requestPasswordReset(identifier.trim(), channel)
      setSent(res)
      setMessage(res.detail)
      setResendIn(res.resend_in || 60)
      setStep(2)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function confirmCode(e) {
    e.preventDefault()
    setError('')
    if (!passwordIsStrong(password)) {
      setError('Please choose a strong password that meets all the requirements.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      const res = await api.confirmPasswordReset({ identifier: identifier.trim(), code: code.trim(), new_password: password })
      setMessage(res.detail)
      setStep(3)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const otherChannel = sent?.channel === 'email' ? (sent.can_use_sms ? 'sms' : null) : (sent?.can_use_email ? 'email' : null)

  return (
    <div className="card auth-card">
      <h1>Reset your password</h1>
      {error && <div className="alert alert-error">{error}</div>}
      {message && step !== 1 && <div className="alert alert-success">{message}</div>}

      {step === 1 && (
        <form onSubmit={requestCode}>
          <p className="muted small">Enter your username, email or phone number. We will email a 6-digit code to the address on your account (by SMS if the account has no email).</p>
          <div className="form-group">
            <label>Username, email or phone</label>
            <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} required autoFocus />
          </div>
          <button className="btn" disabled={busy || !identifier.trim()}>{busy ? 'Sending code…' : 'Send me a code'}</button>
          <p className="muted small" style={{ marginTop: '1rem' }}><Link to="/login">Back to login</Link></p>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={confirmCode}>
          {sent?.debug_code && (
            <div className="info-strip"><span>Development mode: Brevo is not configured, your code is <strong>{sent.debug_code}</strong>.</span></div>
          )}
          {fromLink && !sent && <p className="muted small">Your code from the email is filled in. Choose a new password below.</p>}
          <div className="form-group">
            <label>6-digit code from the {sent?.channel === 'sms' ? 'SMS' : 'email'}</label>
            <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
                   pattern="\d{6}" maxLength={6} placeholder="123456" required autoFocus={!fromLink} style={{ letterSpacing: '0.3em', fontWeight: 700 }} />
            <div className="field-hint muted">
              The code works for 10 minutes.{' '}
              {resendIn > 0
                ? `You can ask for a new one in ${resendIn} s.`
                : <>
                    <button type="button" className="link-btn" onClick={(e) => requestCode(e, sent?.channel)} disabled={busy}>Send a new code</button>
                    {otherChannel && <> · <button type="button" className="link-btn" onClick={(e) => requestCode(e, otherChannel)} disabled={busy}>Send it by {otherChannel === 'sms' ? 'SMS' : 'email'} instead</button></>}
                  </>}
            </div>
          </div>
          <PasswordField label="New password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className="form-group">
            <label>Confirm new password</label>
            <PasswordInput value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
            {confirm && confirm !== password && <div className="field-hint field-hint-error">Passwords do not match.</div>}
          </div>
          <button className="btn" disabled={busy || code.length !== 6}>{busy ? 'Changing password…' : 'Change password'}</button>
          <p className="muted small" style={{ marginTop: '1rem' }}>
            <button type="button" className="link-btn" onClick={() => { setStep(1); setSent(null); setMessage(''); setError('') }}>Use another account</button>
            {' · '}<Link to="/login">Back to login</Link>
          </p>
        </form>
      )}

      {step === 3 && (
        <div>
          <p>Your password is changed. Every device that was signed in has been signed out.</p>
          <button className="btn" onClick={() => navigate('/login')}>Go to login</button>
        </div>
      )}
    </div>
  )
}
