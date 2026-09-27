import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Spinner from './Spinner.jsx'

const EMPTY = { title: '', body: '' }

// Sector leader → cell leaders of the sector, cell leader → village leaders of the cell.
// Every leader of the area is ticked by default; unticking one leaves them out of the notice.
export default function LeaderNotices({ user }) {
  const [data, setData] = useState({ can_create: false, notices: [], recipients: [] })
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY)
  const [excluded, setExcluded] = useState([])
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(null)

  async function load() {
    setLoading(true)
    try {
      setData(await api.listLeaderNotices())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const recipients = data.recipients || []
  const isMine = (n) => n.created_by === user?.id
  const isAdmin = user?.is_admin_role || user?.is_superuser
  const mine = data.notices.filter(isMine)
  const received = data.notices.filter((n) => !isMine(n))
  const sending = recipients.length - excluded.length

  function toggle(id) {
    setExcluded((x) => (x.includes(id) ? x.filter((i) => i !== id) : [...x, id]))
  }

  function startEdit(n) {
    setEditingId(n.id)
    setForm({ title: n.title, body: n.body })
    setExcluded(n.excluded || [])
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function reset() {
    setEditingId(null)
    setForm(EMPTY)
    setExcluded([])
  }

  async function save(e) {
    e.preventDefault()
    setError(''); setNotice(''); setBusy(true)
    try {
      if (!editingId && recipients.length && sending === 0) throw new Error('Tick at least one leader to send the notice to.')
      const payload = { ...form, excluded }
      if (editingId) {
        await api.updateLeaderNotice(editingId, payload)
        setNotice('Notice updated.')
      } else {
        await api.createLeaderNotice(payload)
        setNotice(`Notice sent to ${sending} leader${sending === 1 ? '' : 's'}.`)
      }
      reset()
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(n) {
    if (!window.confirm('Delete this notice?')) return
    setError('')
    try {
      await api.deleteLeaderNotice(n.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const when = (n) => `${new Date(n.created_at).toLocaleDateString()} ${new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`

  function NoticeList({ items, own }) {
    if (items.length === 0) return <p className="muted">No notices yet.</p>
    return (
      <div className="notice-list">
        {items.map((n) => {
          const expanded = open === n.id
          return (
            <article className="notice" key={n.id}>
              <div className="notice-head" onClick={() => setOpen(expanded ? null : n.id)}>
                <div>
                  <div className="notice-title">{n.title}</div>
                  <div className="muted small">
                    {own ? `To ${n.audience_display.toLowerCase()} of ${n.area_name || n.area_code}` : `From ${n.created_by_name} · ${n.created_by_role}${n.area_name ? ` of ${n.area_name}` : ''}`}
                    {' · '}{when(n)}
                  </div>
                </div>
                <span className="notice-meta">
                  {(own || isAdmin) && <span className="badge badge-kind">{n.recipient_count} recipient{n.recipient_count === 1 ? '' : 's'}</span>}
                  <span className="muted small">{expanded ? '▲' : '▼'}</span>
                </span>
              </div>
              {expanded && (
                <div className="notice-body">
                  {n.body.split('\n').map((line, i) => <p key={i}>{line}</p>)}
                  {(own || isAdmin) && n.excluded_names?.length > 0 && (
                    <p className="muted small">Not sent to: {n.excluded_names.join(', ')}</p>
                  )}
                  {(own || isAdmin) && (
                    <div className="btn-row">
                      <button className="btn btn-small btn-ghost" onClick={() => startEdit(n)}>Edit</button>
                      <button className="btn btn-small btn-danger" onClick={() => remove(n)}>Delete</button>
                    </div>
                  )}
                </div>
              )}
            </article>
          )
        })}
      </div>
    )
  }

  if (loading) return <Spinner label="Loading notices…" />

  return (
    <div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      {data.can_create && (
        <div className="two-col" style={{ marginBottom: '1.5rem' }}>
          <form className="card" onSubmit={save}>
            <h2 className="card-title">{editingId ? `Edit notice #${editingId}` : `New notice to the ${data.audience_display?.toLowerCase()} of ${data.area_name || 'your area'}`}</h2>
            <div className="form-group">
              <label>Title</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={200} placeholder="e.g. Monthly leaders' meeting on Friday" />
            </div>
            <div className="form-group">
              <label>Message</label>
              <textarea rows={6} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} required placeholder="Write the notice. One paragraph per line." />
            </div>
            <div className="btn-row">
              <button className="btn" disabled={busy}>{busy ? 'Saving…' : editingId ? 'Save changes' : `Send to ${sending} leader${sending === 1 ? '' : 's'}`}</button>
              {editingId && <button type="button" className="btn btn-outline-dark" onClick={reset}>Cancel</button>}
            </div>
          </form>

          <div className="card">
            <h2 className="card-title">Recipients</h2>
            <p className="muted small" style={{ marginTop: 0 }}>
              All {data.audience_display?.toLowerCase()} of {data.area_name || 'your area'} receive the notice. Untick anyone to leave them out.
            </p>
            {recipients.length === 0 ? (
              <p className="muted">No {data.audience_display?.toLowerCase()} have accounts in {data.area_name || 'your area'} yet.</p>
            ) : (
              <>
                <div className="btn-row" style={{ marginBottom: '0.6rem' }}>
                  <button type="button" className="link-btn" onClick={() => setExcluded([])}>Select all</button>
                  <button type="button" className="link-btn" onClick={() => setExcluded(recipients.map((r) => r.id))}>Clear all</button>
                </div>
                <ul className="recipient-list">
                  {recipients.map((r) => (
                    <li key={r.id} className={excluded.includes(r.id) ? 'recipient-off' : ''}>
                      <label>
                        <input type="checkbox" checked={!excluded.includes(r.id)} onChange={() => toggle(r.id)} />
                        <span>
                          <span className="recipient-name">{r.display_name}</span>
                          <span className="muted small"> · {r.location_name}</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}

      {data.can_create && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title">Notices I sent</h2>
          <NoticeList items={mine} own />
        </div>
      )}

      {(received.length > 0 || !data.can_create) && (
        <div className="card">
          <h2 className="card-title">{isAdmin ? 'All leader notices' : 'Notices from my leaders'}</h2>
          <NoticeList items={received} own={false} />
        </div>
      )}
    </div>
  )
}
