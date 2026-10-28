import { useEffect, useState } from 'react'
import { api } from '../api.js'
import PasswordInput from '../components/PasswordInput.jsx'
import Spinner from '../components/Spinner.jsx'
import { phoneInputProps } from '../phone.js'

const ENV_LABEL = {
  BREVO_API_KEY: 'API key', BREVO_EMAIL_SENDER: 'sender email', BREVO_EMAIL_SENDER_NAME: 'sender name', BREVO_SMS_SENDER: 'SMS sender',
}

// System admin: the Brevo key and senders used for password-reset emails and SMS, with test buttons
export default function MessagingSettings({ user }) {
  const [status, setStatus] = useState(null)
  const [form, setForm] = useState({ api_key: '', email_sender: '', email_sender_name: '', sms_sender: '' })
  const [testEmail, setTestEmail] = useState(user?.email || '')
  const [testPhone, setTestPhone] = useState(user?.phone || '')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function load() {
    try {
      const s = await api.messagingSettings()
      setStatus(s)
      setForm((f) => ({ ...f, email_sender: s.email_sender || '', email_sender_name: s.email_sender_name || '', sms_sender: s.sms_sender || '' }))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  async function run(key, fn) {
    setError('')
    setMessage('')
    setBusy(key)
    try {
      const res = await fn()
      setMessage(res.detail)
      if (key === 'save' || key === 'remove') {
        setForm((f) => ({ ...f, api_key: '' }))
        await load()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const save = (e) => { e.preventDefault(); run('save', () => api.saveMessagingSettings(form)) }
  const remove = () => {
    if (window.confirm('Remove the Brevo settings stored in the app? Password resets stop working until they are entered again (environment variables are not affected).')) {
      run('remove', () => api.deleteMessagingSettings())
    }
  }
  const testMail = (e) => { e.preventDefault(); run('email', () => api.sendTestMessage('email', testEmail.trim())) }
  const testSms = (e) => { e.preventDefault(); run('sms', () => api.sendTestMessage('sms', testPhone.trim())) }

  const env = status?.env_overrides || []

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Messaging settings</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            Password-reset codes are emailed (or texted) through Brevo. Enter the API key and sender from your Brevo account here.
          </p>
        </div>
        {status && (
          <span className={`badge ${status.email_ready ? 'badge-approved' : status.enabled ? 'badge-pending' : 'badge-denied'}`}>
            {status.email_ready ? `Email ready · key ${status.key_hint}` : status.enabled ? `Key ${status.key_hint} saved · sender email missing` : 'Not configured'}
          </span>
        )}
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {!status ? <div className="card"><Spinner label="Loading…" /></div> : (
        <div className="add-user-layout">
          <form className="card" onSubmit={save}>
            <div className="section-title" style={{ marginTop: 0 }}>Brevo account</div>
            <ol className="muted small" style={{ paddingLeft: '1.2rem', margin: '0 0 1rem' }}>
              <li>Sign in at <a href="https://app.brevo.com" target="_blank" rel="noreferrer">app.brevo.com</a> → your name (top right) → <strong>SMTP &amp; API</strong> → <strong>API Keys</strong> → <strong>Generate a new API key</strong>. Copy it (starts with <code>xkeysib-</code>); Brevo shows it only once.</li>
              <li>Under <strong>Senders &amp; IP</strong> → <strong>Senders</strong>, add and verify the address the emails will come from, then type that exact address below.</li>
              <li>For SMS, also buy SMS credits under Transactional → SMS.</li>
            </ol>
            {env.length > 0 && (
              <div className="info-strip"><span>Set by the server environment (overrides what is saved here): {env.map((k) => `${k} (${ENV_LABEL[k] || k})`).join(', ')}.</span></div>
            )}
            <div className="form-group">
              <label>API key</label>
              <PasswordInput value={form.api_key} onChange={set('api_key')} placeholder={status.enabled ? `Keep current key ${status.key_hint}, or paste a new one` : 'xkeysib-…'} autoComplete="off" />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Sender email (verified in Brevo)</label>
                <input type="email" value={form.email_sender} onChange={set('email_sender')} placeholder="no-reply@kigalicity.gov.rw" />
              </div>
              <div className="form-group">
                <label>Sender name</label>
                <input value={form.email_sender_name} onChange={set('email_sender_name')} maxLength={60} placeholder="Certify" />
              </div>
            </div>
            <div className="form-group">
              <label>SMS sender (optional)</label>
              <input value={form.sms_sender} onChange={set('sms_sender')} maxLength={11} placeholder="Certify" />
              <div className="field-hint muted">1 to 11 letters or digits, no spaces. Used only when an account has no email.</div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button className="btn" disabled={!!busy}>{busy === 'save' ? 'Saving…' : 'Save'}</button>
              {status.source === 'database' && <button type="button" className="btn btn-ghost" disabled={!!busy} onClick={remove}>Remove stored settings</button>}
            </div>
            {status.updated_at && <p className="muted small" style={{ marginBottom: 0 }}>Last saved {new Date(status.updated_at).toLocaleString()}{status.updated_by ? ` by ${status.updated_by}` : ''}.</p>}
          </form>

          <div>
            <form className="card" onSubmit={testMail} style={{ marginBottom: '1rem' }}>
              <div className="section-title" style={{ marginTop: 0 }}>Send a test email</div>
              <div className="form-group">
                <label>To</label>
                <input type="email" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} required />
              </div>
              <button className="btn btn-outline" disabled={!!busy || !status.email_ready}>{busy === 'email' ? 'Sending…' : 'Send test email'}</button>
              {!status.email_ready && <div className="field-hint muted">Save the API key and a verified sender email first.</div>}
            </form>
            <form className="card" onSubmit={testSms}>
              <div className="section-title" style={{ marginTop: 0 }}>Send a test SMS</div>
              <div className="form-group">
                <label>Phone number</label>
                <input {...phoneInputProps} value={testPhone} onChange={(e) => setTestPhone(e.target.value)} placeholder="0791234567" required />
              </div>
              <button className="btn btn-outline" disabled={!!busy || !status.sms_ready}>{busy === 'sms' ? 'Sending…' : 'Send test SMS'}</button>
              <div className="field-hint muted">Uses one SMS credit.</div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
