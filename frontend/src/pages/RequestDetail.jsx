import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api.js'
import { canActOn } from './Dashboard.jsx'

export default function RequestDetail({ user }) {
  const { id } = useParams()
  const [req, setReq] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      setReq(await api.getRequest(id))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [id])

  async function act(action) {
    setError('')
    try {
      setReq(await api.actOnRequest(id, action))
    } catch (err) {
      setError(err.message)
    }
  }

  async function download() {
    setError('')
    try {
      const blob = await api.downloadCertificate(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `certificate_${id}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  if (error && !req) return <div className="alert alert-error">{error}</div>
  if (!req) return <p className="muted">Loading…</p>

  return (
    <div>
      <div className="page-head">
        <h1>Request #{req.id}</h1>
        <Link to="/" className="btn btn-small">Back to Dashboard</Link>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <dl className="detail-grid">
          <dt>Type</dt><dd>{req.cert_type_display}</dd>
          <dt>Status</dt><dd><span className={`badge badge-${req.status}`}>{req.status_display}</span></dd>
          <dt>Submitted</dt><dd>{new Date(req.created_at).toLocaleString()}</dd>
          <dt>Requested by</dt><dd>{req.user.first_name} {req.user.last_name} ({req.user.email})</dd>
          {req.other_description && (<><dt>Description</dt><dd>{req.other_description}</dd></>)}
          {req.location_code && (<><dt>Location code</dt><dd>{req.location_code}</dd></>)}
          {req.admin_message && (<><dt>Admin message</dt><dd>{req.admin_message}</dd></>)}
        </dl>

        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {req.status === 'approved' && (
            <button className="btn" onClick={download}>Download Certificate (.docx)</button>
          )}
          {canActOn(user, req) && (
            <>
              <button className="btn" onClick={() => act('approve')}>Approve</button>
              <button className="btn btn-danger" onClick={() => act('deny')}>Deny</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
