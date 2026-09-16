import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, saveBlob } from '../api.js'
import { canActOn } from './Dashboard.jsx'

// Human labels for the applicant details stored on the request
const LABELS = {
  full_name: 'Full name', gender: 'Gender', national_id: 'National ID', id_number: 'ID / Passport number',
  id_type: 'ID type', dob: 'Date of birth', father_name: "Father's name", mother_name: "Mother's name",
  id_issue_district: 'ID issued in district', id_issue_sector: 'ID issued in sector',
  birth_country: 'Country of birth', birth_province: 'Province of birth', birth_district: 'District of birth',
  birth_sector: 'Sector of birth', birth_cell: 'Cell of birth', birth_village: 'Village of birth',
  occupation_type: 'Applicant is', school: 'School', department: 'Department', year_of_study: 'Year of study',
  occupation: 'Occupation', purpose: 'Purpose', resident_since: 'Resident since', nationality: 'Nationality',
  registration_number: 'Registration number', institution: 'Institution', incident_date: 'Incident date',
  incident_time: 'Incident time', incident_location: 'Incident location', device_type: 'Device type',
  brand: 'Brand', model: 'Model', serial_number: 'Serial number', processor: 'Processor', ram: 'RAM',
  storage: 'Storage', color: 'Colour', other_description: 'Other details', reported_to: 'Reported to',
  reported_to_police: 'Reported to police', activities: 'Community activities', subject: 'Subject',
}

const ATTACHMENT_KINDS = [
  ['national_id', 'National ID / Passport'],
  ['student_card', 'Student Card'],
  ['proof', 'Proof / Supporting Document'],
  ['photo', 'Photo'],
  ['other', 'Other'],
]

const VALUE_LABELS = {
  gender: { male: 'Male', female: 'Female' },
  id_type: { national_id: 'National ID', passport: 'Passport' },
  occupation_type: { student: 'Student', worker: 'Worker / other' },
}

function formatValue(key, value) {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (key === 'witnesses') return null
  return VALUE_LABELS[key]?.[value] ?? String(value)
}

export default function RequestDetail({ user }) {
  const { id } = useParams()
  const [req, setReq] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')
  const [uploadKind, setUploadKind] = useState('proof')

  async function load() {
    try {
      setReq(await api.getRequest(id))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [id])

  async function act(action) {
    if (action === 'deny' && !message.trim() && !window.confirm('Deny without giving the applicant a reason?')) return
    setError(''); setNotice(''); setBusy(action)
    try {
      setReq(await api.actOnRequest(id, action, message))
      setMessage('')
      setNotice(action === 'approve' ? 'Approved. The letter has been generated and is ready to download.' : 'Request denied.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function download(regenerate = false, format = 'docx') {
    setError(''); setBusy('download')
    try {
      saveBlob(await api.downloadCertificate(id, { regenerate, format }))
      if (regenerate) await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function downloadAttachment(att) {
    setError('')
    try {
      saveBlob(await api.downloadAttachment(att.id))
    } catch (err) {
      setError(err.message)
    }
  }

  async function removeAttachment(att) {
    if (!window.confirm(`Remove ${att.original_name}?`)) return
    setError('')
    try {
      await api.deleteAttachment(att.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function upload(e) {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    if (!files.length) return
    setError(''); setBusy('upload')
    try {
      await api.uploadAttachments(id, uploadKind, files)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (error && !req) return <div className="alert alert-error">{error}</div>
  if (!req) return <p className="muted">Loading…</p>

  const isOwner = req.user.id === user?.id
  const isAdmin = user?.is_admin_role || user?.is_superuser
  const isLeader = ['village_leader', 'cell_leader', 'sector_leader'].includes(user?.role)
  const canAct = canActOn(user, req)
  const canUpload = (isOwner && req.status === 'pending') || isAdmin
  const details = req.details || {}
  const witnesses = (details.witnesses || []).filter((w) => w && (w.name || '').trim())

  return (
    <div>
      <div className="page-head">
        <h1>Request #{req.id} · {req.cert_type_display}</h1>
        <Link to="/" className="btn btn-small">Back to Dashboard</Link>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="two-col">
        <div className="card">
          <h2 className="card-title">Application</h2>
          <dl className="detail-grid">
            <dt>Status</dt><dd><span className={`badge badge-${req.status}`}>{req.status_display}</span></dd>
            <dt>Submitted</dt><dd>{new Date(req.created_at).toLocaleString()}</dd>
            <dt>Applicant account</dt><dd>{req.user.first_name} {req.user.last_name} ({req.user.email})</dd>
            {req.village_name && (<><dt>Village</dt><dd>{req.village_name}</dd></>)}
            {req.other_description && (<><dt>Description</dt><dd>{req.other_description}</dd></>)}
            {Object.entries(details).map(([key, value]) => {
              const text = formatValue(key, value)
              if (!text || text.trim() === '') return null
              return (<span key={key} className="detail-pair"><dt>{LABELS[key] || key}</dt><dd>{text}</dd></span>)
            })}
            {witnesses.length > 0 && (
              <>
                <dt>People informed</dt>
                <dd>{witnesses.map((w, i) => <div key={i}>{w.name}{w.phone ? ` (${w.phone})` : ''}</div>)}</dd>
              </>
            )}
            {req.approved_by_name && (<><dt>Approved by</dt><dd>{req.approved_by_name} on {new Date(req.approved_at).toLocaleDateString()}</dd></>)}
            {req.admin_message && (<><dt>Message from leader</dt><dd>{req.admin_message}</dd></>)}
          </dl>
        </div>

        <div>
          <div className="card">
            <h2 className="card-title">Supporting documents</h2>
            {req.attachments.length === 0 ? (
              <p className="muted small">No documents attached.</p>
            ) : (
              <ul className="file-list">
                {req.attachments.map((att) => (
                  <li key={att.id}>
                    <span className="badge badge-kind">{att.kind_display}</span>
                    <button type="button" className="link-btn file-name" onClick={() => downloadAttachment(att)}>{att.original_name}</button>
                    <span className="muted small">{(att.size / 1024).toFixed(0)} KB</span>
                    {canUpload && <button type="button" className="link-btn danger" onClick={() => removeAttachment(att)}>remove</button>}
                  </li>
                ))}
              </ul>
            )}
            {canUpload && (
              <div className="form-row" style={{ marginTop: '0.75rem' }}>
                <div className="form-group">
                  <label>Document type</label>
                  <select value={uploadKind} onChange={(e) => setUploadKind(e.target.value)}>
                    {ATTACHMENT_KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Add file(s)</label>
                  <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" onChange={upload} disabled={busy === 'upload'} />
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: '1rem' }}>
            <h2 className="card-title">{canAct ? 'Review' : 'Letter'}</h2>
            {req.status === 'approved' && (
              <div className="btn-row">
                <button className="btn" onClick={() => download(false, 'pdf')} disabled={busy === 'download'}>
                  {busy === 'download' ? 'Preparing…' : 'Download PDF'}
                </button>
                <button className="btn btn-outline-dark" onClick={() => download(false, 'docx')} disabled={busy === 'download'}>
                  Download Word
                </button>
                {(isLeader || isAdmin) && (
                  <button className="btn btn-outline-dark" onClick={() => download(true)} disabled={busy === 'download'} title="Rebuild the letter from the current details">
                    Regenerate
                  </button>
                )}
              </div>
            )}
            {req.status === 'pending' && isOwner && (
              <p className="muted small">Your application is waiting for the village leader. You will be able to download the letter here once it is approved.</p>
            )}
            {req.status === 'denied' && <p className="muted small">This request was denied. You may submit a new application with corrected information.</p>}
            {canAct && (
              <>
                <p className="muted small">Check the details and the attached documents. Approving generates the signed letter immediately.</p>
                <div className="form-group">
                  <label>Message to the applicant (optional, required reason if denying)</label>
                  <textarea rows={2} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="e.g. Please upload a clearer copy of your ID." />
                </div>
                <div className="btn-row">
                  <button className="btn" onClick={() => act('approve')} disabled={!!busy}>{busy === 'approve' ? 'Approving…' : 'Approve & Generate Letter'}</button>
                  <button className="btn btn-danger" onClick={() => act('deny')} disabled={!!busy}>Deny</button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
