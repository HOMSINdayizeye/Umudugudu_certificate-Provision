import { useEffect, useState } from 'react'
import { api } from '../api.js'
import LocationSelect from './LocationSelect.jsx'
import Spinner from './Spinner.jsx'

const LEVELS = ['province', 'district', 'sector', 'cell', 'village']
const EMPTY_LOC = { province: '', district: '', sector: '', cell: '', village: '' }
const EMPTY_FORM = { title: '', description: '', contact_requested: false }

// Own path down to the level above the leader's own, so only the peer area remains to choose
function startLoc(home, level) {
  const s = home ? String(home) : ''
  const loc = { province: s.slice(0, 1), district: s.slice(0, 2), sector: s.slice(0, 4), cell: s.slice(0, 6), village: s.slice(0, 8) }
  for (const l of LEVELS.slice(LEVELS.indexOf(level))) loc[l] = ''
  return loc
}

const when = (iso) => `${new Date(iso).toLocaleDateString()} ${new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`

// Same-level leaders ask each other for information; the leader asked replies and decides which contact details to share
export default function LeaderInquiries({ user, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [form, setForm] = useState(EMPTY_FORM)
  const [loc, setLoc] = useState(EMPTY_LOC)
  const [busy, setBusy] = useState('')
  const [composing, setComposing] = useState(false)
  const isAdmin = user?.is_admin_role || user?.is_superuser

  async function load() {
    setLoading(true)
    try {
      const d = await api.listLeaderInquiries()
      setData(d)
      if (d.can_create) setLoc((l) => (LEVELS.some((k) => l[k]) ? l : startLoc(d.home, d.level)))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const level = data?.level
  const target = level ? loc[level] : ''

  async function send(e) {
    e.preventDefault()
    setError(''); setNotice(''); setBusy('send')
    try {
      if (!target) throw new Error(`Choose the ${level} whose leader you are asking.`)
      await api.createLeaderInquiry({ ...form, to_location: Number(target) })
      setNotice('Inquiry sent. You will be notified when the leader replies.')
      setForm(EMPTY_FORM)
      setLoc(startLoc(data.home, data.level))
      setComposing(false)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function act(id, payload, key) {
    setError(''); setNotice(''); setBusy(key)
    try {
      await api.updateLeaderInquiry(id, payload)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function withdraw(inq) {
    if (!window.confirm('Withdraw this inquiry?')) return
    setError('')
    try {
      await api.deleteLeaderInquiry(inq.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading && !data) return <Spinner label="Loading inquiries…" />

  return (
    <div>
      <div className="inq-head">
        <div>
          <h2 className="card-title" style={{ margin: 0 }}>Leader inquiries</h2>
          <p className="muted small" style={{ margin: '0.2rem 0 0' }}>
            {data?.can_create
              ? `Ask the ${user.role_display?.toLowerCase()} of another ${level} for information. They reply here and choose whether to share their contact details.`
              : 'Questions leaders at the same level send each other.'}
          </p>
        </div>
        <div className="btn-row">
          {data?.can_create && !composing && <button type="button" className="btn btn-small" onClick={() => setComposing(true)}>+ New inquiry</button>}
          {onClose && <button type="button" className="btn btn-small btn-outline-dark" onClick={onClose}>Close</button>}
        </div>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {composing && data?.can_create && (
        <form className="card" onSubmit={send} style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title">New inquiry to another {level}'s {user.role_display?.toLowerCase()}</h2>
          <div className="form-group">
            <label>Which {level}? <span className="muted small" style={{ textTransform: 'none', letterSpacing: 0 }}>(your own is {data.home_name})</span></label>
            <LocationSelect value={loc} onChange={setLoc} progressive upTo={level} />
          </div>
          <div className="form-group">
            <label>Title</label>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={200} placeholder="e.g. Transferred citizen's records" />
          </div>
          <div className="form-group">
            <label>What do you need?</label>
            <textarea rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required placeholder="Describe the information you are asking for." />
          </div>
          <div className="form-group checkbox-row">
            <input type="checkbox" id="inq-contact" checked={form.contact_requested} onChange={(e) => setForm({ ...form, contact_requested: e.target.checked })} />
            <label htmlFor="inq-contact" style={{ margin: 0 }}>Also request their contact details for a call</label>
          </div>
          <div className="btn-row">
            <button className="btn" disabled={!!busy}>{busy === 'send' ? 'Sending…' : 'Send inquiry'}</button>
            <button type="button" className="btn btn-outline-dark" onClick={() => setComposing(false)}>Cancel</button>
          </div>
        </form>
      )}

      <div className="two-col">
        <div className="card">
          <h2 className="card-title">{isAdmin && !data?.can_create ? 'All inquiries' : 'Inquiries to me'} {data?.pending_count > 0 && <span className="badge badge-pending badge-inline">{data.pending_count} waiting</span>}</h2>
          {data?.received?.length === 0 ? <p className="muted">No one has asked you anything yet.</p> : (
            <div className="notice-list">
              {data?.received?.map((q) => <ReceivedInquiry key={q.id} q={q} busy={busy} onAct={act} canAnswer={!isAdmin || data?.can_create} />)}
            </div>
          )}
        </div>
        <div className="card">
          <h2 className="card-title">My inquiries</h2>
          {data?.sent?.length === 0 ? <p className="muted">You have not asked anything yet.</p> : (
            <div className="notice-list">
              {data?.sent?.map((q) => <SentInquiry key={q.id} q={q} busy={busy} onAct={act} onWithdraw={withdraw} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ContactBadge({ q }) {
  if (q.contact_status === 'none') return null
  const cls = { pending: 'badge-pending', shared: 'badge-approved', declined: 'badge-denied' }[q.contact_status]
  return <span className={`badge ${cls}`}>Contact {q.contact_status_display.toLowerCase()}</span>
}

function ReceivedInquiry({ q, busy, onAct, canAnswer }) {
  const [reply, setReply] = useState('')
  const [share, setShare] = useState({ share_phone: true, share_email: true })
  return (
    <article className="notice">
      <div className="notice-head" style={{ cursor: 'default' }}>
        <div>
          <div className="notice-title">{q.title}</div>
          <div className="muted small">From {q.from_user_name} · {q.role_display} of {q.from_location_name} · {when(q.created_at)}</div>
        </div>
        <span className="notice-meta">
          <ContactBadge q={q} />
          <span className={`badge ${q.reply ? 'badge-approved' : 'badge-pending'}`}>{q.reply ? 'Answered' : 'Awaiting reply'}</span>
        </span>
      </div>
      <div className="notice-body">
        {q.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}
        {q.reply ? (
          <div className="inq-reply"><strong>Your reply</strong> <span className="muted small">· {q.answered_by_name}, {when(q.replied_at)}</span>{q.reply.split('\n').map((line, i) => <p key={i}>{line}</p>)}</div>
        ) : canAnswer && (
          <div className="form-group" style={{ marginTop: '0.6rem' }}>
            <label>Reply</label>
            <textarea rows={3} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write the information they asked for." />
            <div className="btn-row" style={{ marginTop: '0.5rem' }}>
              <button type="button" className="btn btn-small" disabled={!reply.trim() || !!busy} onClick={() => onAct(q.id, { reply }, `reply-${q.id}`)}>
                {busy === `reply-${q.id}` ? 'Sending…' : 'Send reply'}
              </button>
            </div>
          </div>
        )}
        {q.contact_status === 'pending' && canAnswer && (
          <div className="inq-contact-box">
            <strong>They ask for your contact details for a call.</strong>
            <div className="btn-row" style={{ margin: '0.5rem 0' }}>
              <label className="checkbox-row"><input type="checkbox" checked={share.share_phone} onChange={(e) => setShare({ ...share, share_phone: e.target.checked })} /> Phone number</label>
              <label className="checkbox-row"><input type="checkbox" checked={share.share_email} onChange={(e) => setShare({ ...share, share_email: e.target.checked })} /> Email</label>
            </div>
            <div className="btn-row">
              <button type="button" className="btn btn-small" disabled={!!busy || !(share.share_phone || share.share_email)} onClick={() => onAct(q.id, { contact: 'share', ...share }, `share-${q.id}`)}>
                {busy === `share-${q.id}` ? 'Sharing…' : 'Share selected'}
              </button>
              <button type="button" className="btn btn-small btn-outline-dark" disabled={!!busy} onClick={() => onAct(q.id, { contact: 'decline' }, `decline-${q.id}`)}>Decline</button>
            </div>
          </div>
        )}
        {q.contact_status === 'shared' && <p className="muted small">You shared {[q.share_phone && 'your phone number', q.share_email && 'your email'].filter(Boolean).join(' and ')}.</p>}
        {q.contact_status === 'declined' && <p className="muted small">You declined to share contact details.</p>}
      </div>
    </article>
  )
}

function SentInquiry({ q, busy, onAct, onWithdraw }) {
  return (
    <article className="notice">
      <div className="notice-head" style={{ cursor: 'default' }}>
        <div>
          <div className="notice-title">{q.title}</div>
          <div className="muted small">To the {q.role_display.toLowerCase()} of {q.to_location_name} · {when(q.created_at)}</div>
        </div>
        <span className="notice-meta">
          <ContactBadge q={q} />
          <span className={`badge ${q.reply ? 'badge-approved' : 'badge-pending'}`}>{q.reply ? 'Answered' : 'Awaiting reply'}</span>
        </span>
      </div>
      <div className="notice-body">
        {q.description.split('\n').map((line, i) => <p key={i}>{line}</p>)}
        {q.reply && (
          <div className="inq-reply"><strong>Reply</strong> <span className="muted small">· {q.answered_by_name}, {when(q.replied_at)}</span>{q.reply.split('\n').map((line, i) => <p key={i}>{line}</p>)}</div>
        )}
        {q.contact && (
          <div className="inq-contact-box">
            <strong>{q.contact.name} shared:</strong>
            {q.contact.phone && <div>📞 <a href={`tel:${q.contact.phone}`}>{q.contact.phone}</a></div>}
            {q.contact.email && <div>✉️ <a href={`mailto:${q.contact.email}`}>{q.contact.email}</a></div>}
          </div>
        )}
        {q.contact_status === 'declined' && <p className="muted small">The leader declined to share contact details.</p>}
        <div className="btn-row" style={{ marginTop: '0.5rem' }}>
          {q.contact_status === 'none' && (
            <button type="button" className="btn btn-small btn-outline-dark" disabled={!!busy} onClick={() => onAct(q.id, { contact_requested: true }, `ask-${q.id}`)}>
              {busy === `ask-${q.id}` ? 'Requesting…' : 'Request contact for a call'}
            </button>
          )}
          {!q.reply && <button type="button" className="btn btn-small btn-ghost" onClick={() => onWithdraw(q)}>Withdraw</button>}
        </div>
      </div>
    </article>
  )
}
